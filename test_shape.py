"""Tests for Shape — phases, transactions, budget gates, proof traces, rule DSL."""

import pytest
from shape import (
    Agent, Phase, ToolEffect, RuleAction, TxState,
    PhaseError, BudgetError, RuleViolation, ApprovalRequired, ShapeError,
    parse_rules, BudgetManager, PhaseManager, wrap_tool,
)


# ── Phase state machine ─────────────────────────────────────────────────────

class TestPhaseManager:
    def test_initial_phase(self):
        pm = PhaseManager()
        assert pm.current == Phase.EXPLORE

    def test_valid_transitions(self):
        pm = PhaseManager()
        pm.transition(Phase.DECIDE)
        assert pm.current == Phase.DECIDE
        pm.transition(Phase.COMMIT)
        assert pm.current == Phase.COMMIT
        pm.transition(Phase.DECIDE)
        assert pm.current == Phase.DECIDE

    def test_invalid_transition(self):
        pm = PhaseManager()
        with pytest.raises(PhaseError):
            pm.transition(Phase.COMMIT)  # can't skip DECIDE

    def test_explore_allows_read_only(self):
        pm = PhaseManager()
        assert pm.allows_effect(ToolEffect.READ)
        assert not pm.allows_effect(ToolEffect.REVERSIBLE)
        assert not pm.allows_effect(ToolEffect.IRREVERSIBLE)

    def test_commit_allows_all(self):
        pm = PhaseManager()
        pm.transition(Phase.DECIDE)
        pm.transition(Phase.COMMIT)
        assert pm.allows_effect(ToolEffect.READ)
        assert pm.allows_effect(ToolEffect.REVERSIBLE)
        assert pm.allows_effect(ToolEffect.IRREVERSIBLE)

    def test_cycle_back(self):
        pm = PhaseManager()
        pm.transition(Phase.DECIDE)
        pm.transition(Phase.EXPLORE)
        assert pm.current == Phase.EXPLORE


# ── Budget manager ───────────────────────────────────────────────────────────

class TestBudgetManager:
    def test_initial_state(self):
        bm = BudgetManager(10.0)
        assert bm.spent == 0.0
        assert bm.pct == 0.0

    def test_record_and_pct(self):
        bm = BudgetManager(10.0)
        bm.record(3.0)
        assert bm.pct == 30.0

    def test_gate_none(self):
        bm = BudgetManager(10.0)
        bm.record(2.0)
        assert bm.check_gate() is None

    def test_gate_degrade(self):
        bm = BudgetManager(10.0)
        bm.record(5.5)
        assert bm.check_gate() == "DEGRADE"

    def test_gate_force_decide(self):
        bm = BudgetManager(10.0)
        bm.record(7.5)
        assert bm.check_gate() == "FORCE_DECIDE"

    def test_gate_stop(self):
        bm = BudgetManager(10.0)
        bm.record(10.0)
        assert bm.check_gate() == "STOP"

    def test_zero_budget(self):
        bm = BudgetManager(0.0)
        assert bm.pct == 0.0


# ── Rule DSL parser ──────────────────────────────────────────────────────────

class TestRuleDSL:
    def test_parse_block(self):
        rules = parse_rules("BLOCK write_plc WHEN phase IS NOT commit")
        assert len(rules) == 1
        assert rules[0].action == RuleAction.BLOCK
        assert rules[0].tool_pattern == "write_plc"
        assert rules[0].conditions == [("phase", "IS NOT", "commit")]

    def test_parse_wildcard(self):
        rules = parse_rules("BLOCK * WHEN budget ABOVE 80%")
        assert rules[0].tool_pattern == "*"
        assert rules[0].conditions == [("budget", "ABOVE", "80%")]

    def test_parse_require_approval(self):
        rules = parse_rules("REQUIRE APPROVAL FOR * WHEN tool IS irreversible")
        assert rules[0].action == RuleAction.REQUIRE_APPROVAL

    def test_parse_flag(self):
        rules = parse_rules("FLAG * WHEN time OUTSIDE 06:00-22:00")
        assert rules[0].action == RuleAction.FLAG

    def test_parse_unless(self):
        rules = parse_rules("BLOCK * WHEN budget ABOVE 80% UNLESS tool IS read")
        r = rules[0]
        assert len(r.conditions) == 2
        # UNLESS negates: IS → IS NOT
        assert r.conditions[1] == ("tool", "IS NOT", "read")

    def test_parse_multiple(self):
        text = """
        BLOCK write_plc WHEN phase IS NOT commit
        FLAG * WHEN time OUTSIDE 06:00-22:00
        """
        rules = parse_rules(text)
        assert len(rules) == 2

    def test_parse_empty_and_comments(self):
        text = """
        # This is a comment
        BLOCK * WHEN budget ABOVE 90%

        """
        rules = parse_rules(text)
        assert len(rules) == 1

    def test_parse_invalid(self):
        with pytest.raises(ValueError):
            parse_rules("INVALID RULE TEXT")

    def test_rule_matches_tool(self):
        rules = parse_rules("BLOCK write_plc WHEN phase IS NOT commit")
        assert rules[0].matches_tool("write_plc")
        assert not rules[0].matches_tool("read_plc")

    def test_wildcard_matches_any(self):
        rules = parse_rules("BLOCK * WHEN budget ABOVE 90%")
        assert rules[0].matches_tool("anything")

    def test_rule_evaluate_is(self):
        rules = parse_rules("BLOCK * WHEN phase IS explore")
        met, _ = rules[0].evaluate({"phase": "explore"})
        assert met

    def test_rule_evaluate_is_not(self):
        rules = parse_rules("BLOCK * WHEN phase IS NOT commit")
        met, _ = rules[0].evaluate({"phase": "explore"})
        assert met
        met2, _ = rules[0].evaluate({"phase": "commit"})
        assert not met2

    def test_rule_evaluate_above(self):
        rules = parse_rules("BLOCK * WHEN budget ABOVE 80%")
        met, _ = rules[0].evaluate({"budget": 85.0})
        assert met
        met2, _ = rules[0].evaluate({"budget": 70.0})
        assert not met2

    def test_rule_evaluate_outside(self):
        rules = parse_rules("FLAG * WHEN time OUTSIDE 06:00-22:00")
        met, _ = rules[0].evaluate({"time": "03:00"})
        assert met
        met2, _ = rules[0].evaluate({"time": "14:00"})
        assert not met2


# ── Agent — tool registration ────────────────────────────────────────────────

class TestAgentTools:
    def test_register_tool(self):
        a = Agent("test")
        a.tool("read_plc", effect=ToolEffect.READ, fn=lambda: {"value": 42})
        assert "read_plc" in a.tools

    def test_unknown_tool_raises(self):
        a = Agent("test")
        a.phase.transition(Phase.DECIDE)
        a.phase.transition(Phase.COMMIT)
        with pytest.raises(ShapeError, match="Unknown tool"):
            a._execute("nonexistent", {})


# ── Agent — phase enforcement ────────────────────────────────────────────────

class TestAgentPhases:
    def _agent_with_tools(self):
        a = Agent("test")
        a.tool("read_plc", effect=ToolEffect.READ, fn=lambda **kw: {"value": 42})
        a.tool("write_plc", effect=ToolEffect.IRREVERSIBLE, fn=lambda **kw: {"ok": True})
        return a

    def test_explore_allows_read(self):
        a = self._agent_with_tools()
        with a.explore() as ctx:
            result = ctx.call("read_plc")
        assert result["value"] == 42

    def test_explore_blocks_write(self):
        a = self._agent_with_tools()
        with a.explore() as ctx:
            with pytest.raises(RuleViolation):
                ctx.call("write_plc")

    def test_decide_propose(self):
        a = self._agent_with_tools()
        with a.decide() as ctx:
            proposal = ctx.propose(speed=105)
        assert proposal["proposal"]["speed"] == 105

    def test_commit_allows_write(self):
        a = self._agent_with_tools()
        a.phase.transition(Phase.DECIDE)
        with a.commit() as tx:
            result = tx.call("write_plc", value=105)
        assert result["ok"]


# ── Agent — transactions ─────────────────────────────────────────────────────

class TestTransactions:
    def test_commit_on_success(self):
        a = Agent("test")
        a.tool("write_mes", effect=ToolEffect.REVERSIBLE, fn=lambda **kw: "ok")
        a.phase.transition(Phase.DECIDE)
        with a.commit() as tx:
            tx.call("write_mes", record="plan")
        assert tx.tx.state == TxState.COMMITTED

    def test_abort_on_exception(self):
        a = Agent("test")
        a.tool("write_mes", effect=ToolEffect.REVERSIBLE, fn=lambda **kw: "ok")
        a.tool("fail_tool", effect=ToolEffect.REVERSIBLE, fn=lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))
        a.phase.transition(Phase.DECIDE)
        with pytest.raises(RuntimeError):
            with a.commit() as tx:
                tx.call("write_mes", record="plan")
                tx.call("fail_tool")
        assert tx.tx.state == TxState.ABORTED

    def test_compensation_called_on_abort(self):
        compensated = []
        a = Agent("test")
        a.tool("write_mes", effect=ToolEffect.REVERSIBLE,
               fn=lambda **kw: "ok",
               compensation=lambda: compensated.append("write_mes"))
        a.phase.transition(Phase.DECIDE)
        with pytest.raises(RuntimeError):
            with a.commit() as tx:
                tx.call("write_mes", record="plan")
                raise RuntimeError("fail")
        assert "write_mes" in compensated

    def test_buffered_effects(self):
        a = Agent("test")
        a.tool("write_mes", effect=ToolEffect.REVERSIBLE, fn=lambda **kw: "ok")
        a.phase.transition(Phase.DECIDE)
        with a.commit() as tx:
            tx.call("write_mes", record="plan")
        assert len(tx.tx.buffered) == 1
        assert tx.tx.buffered[0]["tool"] == "write_mes"

    def test_tx_id_increments(self):
        a = Agent("test")
        a.tool("w", effect=ToolEffect.REVERSIBLE, fn=lambda **kw: "ok")
        a.phase.transition(Phase.DECIDE)
        with a.commit() as tx1:
            tx1.call("w")
        a.phase.transition(Phase.DECIDE)
        with a.commit() as tx2:
            tx2.call("w")
        assert tx1.tx.tx_id == "T1"
        assert tx2.tx.tx_id == "T2"


# ── Agent — budget gates ─────────────────────────────────────────────────────

class TestBudgetGates:
    def test_budget_stop(self):
        a = Agent("test", budget=1.00)
        a.tool("read_plc", effect=ToolEffect.READ, fn=lambda **kw: 42)
        a.budget.record(1.00)
        with a.explore() as ctx:
            with pytest.raises(RuleViolation):
                ctx.call("read_plc")

    def test_budget_force_decide_blocks_commit(self):
        a = Agent("test", budget=10.0)
        a.tool("write_plc", effect=ToolEffect.IRREVERSIBLE, fn=lambda **kw: "ok")
        a.budget.record(7.5)  # 75%
        a.phase.transition(Phase.DECIDE)
        with pytest.raises(RuleViolation):
            with a.commit() as tx:
                tx.call("write_plc")

    def test_budget_tracking_in_tx(self):
        a = Agent("test", budget=10.0)
        a.tool("write_mes", effect=ToolEffect.REVERSIBLE, fn=lambda **kw: "ok")
        a.phase.transition(Phase.DECIDE)
        with a.commit() as tx:
            tx.call("write_mes", cost=2.50)
        assert a.budget.spent == 2.50


# ── Agent — rule enforcement ─────────────────────────────────────────────────

class TestRuleEnforcement:
    def test_block_rule(self):
        a = Agent("test")
        a.tool("write_plc", effect=ToolEffect.IRREVERSIBLE, fn=lambda **kw: "ok")
        a.rules("BLOCK write_plc WHEN phase IS NOT commit")
        a.phase.transition(Phase.DECIDE)
        a.phase.transition(Phase.COMMIT)
        # In commit phase, rule condition "phase IS NOT commit" is false → not blocked
        result = a._execute("write_plc", {})
        assert result == "ok"

    def test_block_rule_triggers(self):
        a = Agent("test")
        a.tool("write_plc", effect=ToolEffect.IRREVERSIBLE, fn=lambda **kw: "ok")
        a.rules("BLOCK write_plc WHEN phase IS NOT commit")
        # In explore phase, write_plc is blocked by phase enforcement anyway
        # Let's test with a read tool and a custom rule
        a.tool("dangerous_read", effect=ToolEffect.READ, fn=lambda **kw: "data")
        a.rules("BLOCK dangerous_read WHEN phase IS explore")
        with a.explore() as ctx:
            with pytest.raises(RuleViolation):
                ctx.call("dangerous_read")

    def test_require_approval_granted(self):
        a = Agent("test")
        a.tool("write_plc", effect=ToolEffect.IRREVERSIBLE, fn=lambda **kw: "ok")
        a.rules("REQUIRE APPROVAL FOR write_plc WHEN tool IS irreversible")
        a.on_approval(lambda tool, kw: True)
        a.phase.transition(Phase.DECIDE)
        a.phase.transition(Phase.COMMIT)
        result = a._execute("write_plc", {})
        assert result == "ok"

    def test_require_approval_denied(self):
        a = Agent("test")
        a.tool("write_plc", effect=ToolEffect.IRREVERSIBLE, fn=lambda **kw: "ok")
        a.rules("REQUIRE APPROVAL FOR write_plc WHEN tool IS irreversible")
        a.on_approval(lambda tool, kw: False)
        a.phase.transition(Phase.DECIDE)
        a.phase.transition(Phase.COMMIT)
        with pytest.raises(ApprovalRequired):
            a._execute("write_plc", {})

    def test_flag_allows_execution(self):
        a = Agent("test")
        a.tool("read_plc", effect=ToolEffect.READ, fn=lambda **kw: 42)
        a.rules("FLAG read_plc WHEN phase IS explore")
        with a.explore() as ctx:
            result = ctx.call("read_plc")
        assert result == 42
        assert a.traces[-1].decision == "FLAGGED"


# ── Proof traces ─────────────────────────────────────────────────────────────

class TestProofTraces:
    def test_trace_recorded(self):
        a = Agent("test", budget=5.0)
        a.tool("read_plc", effect=ToolEffect.READ, fn=lambda **kw: 42)
        with a.explore() as ctx:
            ctx.call("read_plc")
        assert len(a.traces) == 1
        t = a.traces[0]
        assert t.tool == "read_plc"
        assert t.decision in ("ALLOWED", "FLAGGED")
        assert t.phase == "explore"
        assert t.budget_limit == 5.0
        assert t.timestamp

    def test_trace_on_block(self):
        a = Agent("test")
        a.tool("write_plc", effect=ToolEffect.IRREVERSIBLE, fn=lambda **kw: "ok")
        with pytest.raises(RuleViolation):
            with a.explore() as ctx:
                ctx.call("write_plc")
        assert len(a.traces) == 1
        assert a.traces[0].decision == "BLOCKED"

    def test_trace_has_tx_id(self):
        a = Agent("test")
        a.tool("write_mes", effect=ToolEffect.REVERSIBLE, fn=lambda **kw: "ok")
        a.phase.transition(Phase.DECIDE)
        with a.commit() as tx:
            tx.call("write_mes")
        assert a.traces[-1].tx_id == "T1"

    def test_trace_rules_evaluated(self):
        a = Agent("test")
        a.tool("read_plc", effect=ToolEffect.READ, fn=lambda **kw: 42)
        a.rules("FLAG read_plc WHEN phase IS explore")
        with a.explore() as ctx:
            ctx.call("read_plc")
        t = a.traces[-1]
        assert any(r["check"] == "rule" for r in t.rules_evaluated)


# ── Integration: wrap_tool ───────────────────────────────────────────────────

class TestWrapTool:
    def test_wrap_and_call(self):
        a = Agent("test")
        governed_read = wrap_tool(a, "read_sensor", fn=lambda **kw: {"temp": 22}, effect=ToolEffect.READ)
        with a.explore():
            result = governed_read()
        assert result["temp"] == 22

    def test_wrap_blocks_in_wrong_phase(self):
        a = Agent("test")
        governed_write = wrap_tool(a, "write_plc", fn=lambda **kw: "ok", effect=ToolEffect.IRREVERSIBLE)
        with pytest.raises(RuleViolation):
            with a.explore():
                governed_write()


# ── Full integration scenario ────────────────────────────────────────────────

class TestManufacturingScenario:
    """ErgebnisTransaction pattern: read PLC → decide → commit atomically to PLC + MES."""

    def test_full_lifecycle(self):
        compensated = []
        agent = Agent("production-adjuster", budget=5.00)
        agent.tool("read_plc", effect=ToolEffect.READ, fn=lambda **kw: {"speed": 100, "device": kw.get("device")})
        agent.tool("write_mes", effect=ToolEffect.REVERSIBLE,
                   fn=lambda **kw: {"written": True},
                   compensation=lambda: compensated.append("mes"))
        agent.tool("write_plc", effect=ToolEffect.IRREVERSIBLE,
                   fn=lambda **kw: {"written": True})
        agent.tool("notify_shift", effect=ToolEffect.IRREVERSIBLE,
                   fn=lambda **kw: {"notified": True})
        agent.rules("""
            BLOCK write_plc WHEN phase IS NOT commit
            REQUIRE APPROVAL FOR * WHEN tool IS irreversible
        """)
        agent.on_approval(lambda tool, kw: True)

        # EXPLORE
        with agent.explore() as ctx:
            state = ctx.call("read_plc", device="line-3")
        assert state["speed"] == 100

        # DECIDE
        with agent.decide() as ctx:
            plan = ctx.propose(adjustment={"speed": 105})
        assert plan["proposal"]["adjustment"]["speed"] == 105

        # COMMIT
        with agent.commit() as tx:
            tx.call("write_mes", cost=0.10, record=plan)
            tx.call("write_plc", cost=0.20, value=105)
            tx.call("notify_shift", cost=0.05, msg="speed adjusted")

        assert tx.tx.state == TxState.COMMITTED
        assert agent.budget.spent == pytest.approx(0.35)
        assert len(agent.traces) == 4  # 1 read + 3 commit (propose has no trace)

    def test_failed_commit_aborts(self):
        compensated = []
        agent = Agent("test", budget=5.00)
        agent.tool("write_mes", effect=ToolEffect.REVERSIBLE,
                   fn=lambda **kw: "ok",
                   compensation=lambda: compensated.append("mes_undone"))
        agent.tool("write_plc", effect=ToolEffect.IRREVERSIBLE,
                   fn=lambda **kw: (_ for _ in ()).throw(RuntimeError("PLC timeout")))
        agent.phase.transition(Phase.DECIDE)

        with pytest.raises(RuntimeError):
            with agent.commit() as tx:
                tx.call("write_mes", cost=0.10)
                tx.call("write_plc", cost=0.20)

        assert tx.tx.state == TxState.ABORTED
        assert "mes_undone" in compensated
