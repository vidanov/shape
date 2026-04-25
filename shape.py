"""
Shape — Agent governance: phases + transactions + budget gates + proof traces + rule DSL.

Zero dependencies. Single file. 466 LOC.
Wraps any tool-calling agent with external authority over permission, cost, and atomicity.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional


# ── Enums ────────────────────────────────────────────────────────────────────

class Phase(Enum):
    EXPLORE = "explore"
    DECIDE = "decide"
    COMMIT = "commit"


class ToolEffect(Enum):
    READ = "read"
    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"


class RuleAction(Enum):
    BLOCK = "block"
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    FLAG = "flag"


class TxState(Enum):
    OPEN = "open"
    COMMITTED = "committed"
    ABORTED = "aborted"


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class ProofTrace:
    tool: str
    decision: str  # ALLOWED | BLOCKED | FLAGGED | APPROVAL_REQUIRED
    phase: str
    budget_spent: float
    budget_limit: float
    rules_evaluated: list[dict[str, Any]]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_s: float = 0.0
    tx_id: Optional[str] = None
    result: Any = None
    error: Optional[str] = None


@dataclass
class Rule:
    action: RuleAction
    tool_pattern: str  # "*" or tool name
    conditions: list[tuple[str, str, str]]  # (field, operator, value)

    def matches_tool(self, tool_name: str) -> bool:
        return self.tool_pattern == "*" or self.tool_pattern == tool_name

    def evaluate(self, ctx: dict[str, Any]) -> tuple[bool, str]:
        """Return (condition_met, reason)."""
        for fld, op, val in self.conditions:
            actual = ctx.get(fld)
            if actual is None:
                return False, f"{fld} not available"
            if not _compare(actual, op, val):
                return False, f"{fld} {op} {val} → actual={actual}, not met"
        return True, "all conditions met"


@dataclass
class Transaction:
    tx_id: str
    state: TxState = TxState.OPEN
    buffered: list[dict[str, Any]] = field(default_factory=list)
    compensations: list[Callable] = field(default_factory=list)

    def buffer(self, tool: str, kwargs: dict, result: Any, compensation: Optional[Callable] = None):
        self.buffered.append({"tool": tool, "kwargs": kwargs, "result": result})
        if compensation:
            self.compensations.append(compensation)

    def commit(self):
        self.state = TxState.COMMITTED

    def abort(self):
        self.state = TxState.ABORTED
        for comp in reversed(self.compensations):
            try:
                comp()
            except Exception:
                pass  # best-effort compensation


# ── Rule DSL parser ──────────────────────────────────────────────────────────

_RULE_PATTERN = re.compile(
    r"^(BLOCK|ALLOW|FLAG|REQUIRE\s+APPROVAL\s+FOR)\s+"
    r"(\S+)"
    r"((?:\s+(?:WHEN|AND|UNLESS)\s+.+)*)\s*$",
    re.IGNORECASE,
)

_CONDITION_PATTERN = re.compile(
    r"(?:WHEN|AND|UNLESS)\s+(\w+)\s+(IS NOT|IS|ABOVE|BELOW|OUTSIDE)\s+(.+?)(?=\s+(?:WHEN|AND|UNLESS)\s+|$)",
    re.IGNORECASE,
)


def parse_rules(text: str) -> list[Rule]:
    rules = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _RULE_PATTERN.match(line)
        if not m:
            raise ValueError(f"Cannot parse rule: {line}")
        action_str = m.group(1).upper().strip()
        tool_pattern = m.group(2).strip()
        cond_str = m.group(3).strip() if m.group(3) else ""

        action_map = {
            "BLOCK": RuleAction.BLOCK,
            "ALLOW": RuleAction.ALLOW,
            "FLAG": RuleAction.FLAG,
            "REQUIRE APPROVAL FOR": RuleAction.REQUIRE_APPROVAL,
        }
        action = action_map[action_str]

        conditions = []
        negate_next = False
        for cm in _CONDITION_PATTERN.finditer(cond_str):
            prefix = cm.group(0).strip().split()[0].upper()
            fld = cm.group(1).lower()
            op = cm.group(2).upper()
            val = cm.group(3).strip()
            if prefix == "UNLESS":
                op = _negate_op(op)
            conditions.append((fld, op, val))

        rules.append(Rule(action=action, tool_pattern=tool_pattern, conditions=conditions))
    return rules


def _negate_op(op: str) -> str:
    return {"IS": "IS NOT", "IS NOT": "IS", "ABOVE": "BELOW", "BELOW": "ABOVE", "OUTSIDE": "INSIDE"}.get(op, op)


def _compare(actual: Any, op: str, val: str) -> bool:
    op = op.upper()
    if op == "IS":
        return str(actual).lower() == val.lower()
    if op == "IS NOT":
        return str(actual).lower() != val.lower()
    if op in ("ABOVE", "BELOW"):
        try:
            num_val = float(val.rstrip("%"))
            num_actual = float(actual) if not isinstance(actual, (int, float)) else actual
            return num_actual > num_val if op == "ABOVE" else num_actual < num_val
        except (ValueError, TypeError):
            return False
    if op == "OUTSIDE":
        parts = val.split("-")
        if len(parts) == 2:
            try:
                lo, hi = parts[0].strip(), parts[1].strip()
                now_val = str(actual)
                return now_val < lo or now_val > hi
            except Exception:
                return False
    if op == "INSIDE":
        parts = val.split("-")
        if len(parts) == 2:
            lo, hi = parts[0].strip(), parts[1].strip()
            now_val = str(actual)
            return lo <= now_val <= hi
    return False


# ── Budget manager ───────────────────────────────────────────────────────────

class BudgetManager:
    def __init__(self, limit: float):
        self.limit = limit
        self.spent = 0.0

    @property
    def pct(self) -> float:
        return (self.spent / self.limit * 100) if self.limit > 0 else 0.0

    def record(self, amount: float):
        self.spent += amount

    def check_gate(self) -> Optional[str]:
        """Return action if a budget gate is hit."""
        if self.pct >= 100:
            return "STOP"
        if self.pct >= 75:
            return "FORCE_DECIDE"
        if self.pct >= 50:
            return "DEGRADE"
        return None


# ── Phase state machine ─────────────────────────────────────────────────────

_TRANSITIONS = {
    Phase.EXPLORE: {Phase.DECIDE},
    Phase.DECIDE: {Phase.EXPLORE, Phase.COMMIT},
    Phase.COMMIT: {Phase.DECIDE, Phase.EXPLORE},
}

_PHASE_ALLOWED_EFFECTS = {
    Phase.EXPLORE: {ToolEffect.READ},
    Phase.DECIDE: {ToolEffect.READ},
    Phase.COMMIT: {ToolEffect.READ, ToolEffect.REVERSIBLE, ToolEffect.IRREVERSIBLE},
}


class PhaseManager:
    def __init__(self):
        self.current = Phase.EXPLORE

    def transition(self, target: Phase):
        if target != self.current and target not in _TRANSITIONS[self.current]:
            raise PhaseError(f"Cannot transition {self.current.value} → {target.value}")
        self.current = target

    def allows_effect(self, effect: ToolEffect) -> bool:
        return effect in _PHASE_ALLOWED_EFFECTS[self.current]


# ── Exceptions ───────────────────────────────────────────────────────────────

class ShapeError(Exception):
    pass

class PhaseError(ShapeError):
    pass

class BudgetError(ShapeError):
    pass

class RuleViolation(ShapeError):
    pass

class ApprovalRequired(ShapeError):
    pass


# ── Agent (main API) ─────────────────────────────────────────────────────────

class Agent:
    def __init__(self, name: str, budget: float = 0.0):
        self.name = name
        self.budget = BudgetManager(budget) if budget > 0 else None
        self.phase = PhaseManager()
        self.tools: dict[str, dict] = {}
        self._rules: list[Rule] = []
        self.traces: list[ProofTrace] = []
        self._tx_counter = 0
        self._approval_callback: Optional[Callable[[str, dict], bool]] = None

    def tool(self, name: str, effect: ToolEffect = ToolEffect.READ,
             fn: Optional[Callable] = None, compensation: Optional[Callable] = None):
        self.tools[name] = {"effect": effect, "fn": fn, "compensation": compensation}

    def rules(self, text: str):
        self._rules.extend(parse_rules(text))

    def on_approval(self, callback: Callable[[str, dict], bool]):
        self._approval_callback = callback

    # ── Phase contexts ───────────────────────────────────────────────────

    def explore(self) -> PhaseContext:
        self.phase.transition(Phase.EXPLORE)
        return PhaseContext(self, Phase.EXPLORE)

    def decide(self) -> PhaseContext:
        self.phase.transition(Phase.DECIDE)
        return PhaseContext(self, Phase.DECIDE)

    def commit(self) -> TransactionContext:
        self.phase.transition(Phase.COMMIT)
        self._tx_counter += 1
        tx = Transaction(tx_id=f"T{self._tx_counter}")
        return TransactionContext(self, tx)

    # ── Core evaluation ──────────────────────────────────────────────────

    def _evaluate(self, tool_name: str, kwargs: dict, tx: Optional[Transaction] = None) -> ProofTrace:
        t0 = time.monotonic()
        tool_info = self.tools.get(tool_name)
        if not tool_info:
            raise ShapeError(f"Unknown tool: {tool_name}")

        effect = tool_info["effect"]
        rules_log = []
        decision = "ALLOWED"

        # Phase check
        phase_ok = self.phase.allows_effect(effect)
        rules_log.append({
            "check": "phase",
            "passed": phase_ok,
            "detail": f"Phase {self.phase.current.value} {'allows' if phase_ok else 'blocks'} {effect.value}",
        })
        if not phase_ok:
            decision = "BLOCKED"

        # Budget gate
        budget_gate = None
        if self.budget:
            budget_gate = self.budget.check_gate()
            if budget_gate == "STOP":
                decision = "BLOCKED"
                rules_log.append({"check": "budget", "passed": False, "detail": f"Budget exhausted ({self.budget.pct:.0f}%)"})
            elif budget_gate == "FORCE_DECIDE" and self.phase.current == Phase.COMMIT:
                decision = "BLOCKED"
                rules_log.append({"check": "budget", "passed": False, "detail": f"Budget ≥75% ({self.budget.pct:.0f}%), forcing re-evaluation"})
            else:
                rules_log.append({"check": "budget", "passed": True, "detail": f"{self.budget.pct:.1f}% spent"})

        # Rule evaluation
        if decision == "ALLOWED":
            ctx = self._rule_context(tool_name, effect)
            for rule in self._rules:
                if not rule.matches_tool(tool_name):
                    continue
                met, reason = rule.evaluate(ctx)
                if met:
                    if rule.action == RuleAction.BLOCK:
                        decision = "BLOCKED"
                        rules_log.append({"check": "rule", "passed": False, "detail": f"BLOCK rule matched: {reason}"})
                    elif rule.action == RuleAction.REQUIRE_APPROVAL:
                        decision = "APPROVAL_REQUIRED"
                        rules_log.append({"check": "rule", "passed": False, "detail": f"Approval required: {reason}"})
                    elif rule.action == RuleAction.FLAG:
                        rules_log.append({"check": "rule", "passed": True, "detail": f"FLAG: {reason}"})
                        decision = "FLAGGED"
                    elif rule.action == RuleAction.ALLOW:
                        rules_log.append({"check": "rule", "passed": True, "detail": f"ALLOW rule matched: {reason}"})

        trace = ProofTrace(
            tool=tool_name,
            decision=decision,
            phase=self.phase.current.value,
            budget_spent=self.budget.spent if self.budget else 0.0,
            budget_limit=self.budget.limit if self.budget else 0.0,
            rules_evaluated=rules_log,
            tx_id=tx.tx_id if tx else None,
            duration_s=time.monotonic() - t0,
        )
        return trace

    def _execute(self, tool_name: str, kwargs: dict, tx: Optional[Transaction] = None) -> Any:
        trace = self._evaluate(tool_name, kwargs, tx)

        if trace.decision == "BLOCKED":
            trace.error = "Blocked by governance"
            self.traces.append(trace)
            raise RuleViolation(f"Tool '{tool_name}' blocked: {trace.rules_evaluated}")

        if trace.decision == "APPROVAL_REQUIRED":
            if self._approval_callback and self._approval_callback(tool_name, kwargs):
                trace.decision = "ALLOWED"
            else:
                trace.error = "Approval not granted"
                self.traces.append(trace)
                raise ApprovalRequired(f"Tool '{tool_name}' requires approval")

        # Execute
        tool_info = self.tools[tool_name]
        fn = tool_info["fn"]
        result = fn(**kwargs) if fn else {"tool": tool_name, "kwargs": kwargs, "simulated": True}

        trace.result = result
        trace.duration_s = time.monotonic() - (time.monotonic() - trace.duration_s)

        if tx and tool_info["effect"] != ToolEffect.READ:
            tx.buffer(tool_name, kwargs, result, tool_info.get("compensation"))

        self.traces.append(trace)
        return result

    def _rule_context(self, tool_name: str, effect: ToolEffect) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        ctx = {
            "phase": self.phase.current.value,
            "tool": effect.value,
            "budget": self.budget.pct if self.budget else 0.0,
            "time": now.strftime("%H:%M"),
        }
        return ctx


# ── Context managers ─────────────────────────────────────────────────────────

class PhaseContext:
    def __init__(self, agent: Agent, phase: Phase):
        self.agent = agent
        self.phase = phase

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def call(self, tool_name: str, **kwargs) -> Any:
        return self.agent._execute(tool_name, kwargs)

    def propose(self, **kwargs) -> dict:
        """In DECIDE phase, record a proposal without executing."""
        return {"proposal": kwargs, "phase": self.phase.value, "timestamp": datetime.now(timezone.utc).isoformat()}


class TransactionContext:
    def __init__(self, agent: Agent, tx: Transaction):
        self.agent = agent
        self.tx = tx

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.tx.abort()
            return False
        self.tx.commit()
        return False

    def call(self, tool_name: str, cost: float = 0.0, **kwargs) -> Any:
        if self.agent.budget and cost > 0:
            self.agent.budget.record(cost)
        return self.agent._execute(tool_name, kwargs, self.tx)


# ── Strands / generic integration glue ───────────────────────────────────────

def wrap_tool(agent: Agent, tool_name: str, fn: Callable,
              effect: ToolEffect = ToolEffect.READ,
              compensation: Optional[Callable] = None) -> Callable:
    """Register and return a governed version of any callable."""
    agent.tool(tool_name, effect=effect, fn=fn, compensation=compensation)

    def governed(**kwargs):
        return agent._execute(tool_name, kwargs)

    governed.__name__ = f"governed_{tool_name}"
    return governed
