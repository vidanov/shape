"""
Shape — Manufacturing demo.

Agent reads PLC state, decides on adjustment, commits atomically to PLC + MES.
Run from repo root: python3 examples/manufacturing.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shape import Agent, ToolEffect, TxState


# ── Simulated manufacturing tools ────────────────────────────────────────────

def read_plc(device: str = "line-3", register: str = "speed") -> dict:
    """Read current PLC state (simulated)."""
    return {"device": device, "register": register, "value": 100, "unit": "rpm"}


def write_mes(record: dict = None, **kw) -> dict:
    """Write production record to MES (simulated, reversible)."""
    print(f"  [MES] Writing record: {record}")
    return {"written": True, "id": "MES-2026-04-20-001"}


def delete_mes(record_id: str = "MES-2026-04-20-001") -> dict:
    """Compensate: delete MES record on rollback."""
    print(f"  [MES] COMPENSATING: deleting {record_id}")
    return {"deleted": True}


def write_plc(device: str = "line-3", value: int = 0, **kw) -> dict:
    """Write to PLC (simulated, irreversible)."""
    print(f"  [PLC] Writing {value} to {device}")
    return {"written": True, "device": device, "value": value}


def notify_shift(msg: str = "", **kw) -> dict:
    """Send shift notification (simulated, irreversible)."""
    print(f"  [NOTIFY] {msg}")
    return {"notified": True}


# ── Agent setup ──────────────────────────────────────────────────────────────

agent = Agent("production-adjuster", budget=5.00)

agent.tool("read_plc", effect=ToolEffect.READ, fn=read_plc)
agent.tool("write_mes", effect=ToolEffect.REVERSIBLE, fn=write_mes, compensation=delete_mes)
agent.tool("write_plc", effect=ToolEffect.IRREVERSIBLE, fn=write_plc)
agent.tool("notify_shift", effect=ToolEffect.IRREVERSIBLE, fn=notify_shift)

agent.rules("""
    BLOCK write_plc WHEN phase IS NOT commit
    REQUIRE APPROVAL FOR * WHEN tool IS irreversible
    FLAG * WHEN time OUTSIDE 06:00-22:00
""")

# Auto-approve for demo (in production: human-in-the-loop)
agent.on_approval(lambda tool, kw: True)


# ── Run the lifecycle ────────────────────────────────────────────────────────

print("=" * 60)
print("Shape — Manufacturing Demo")
print("=" * 60)

# EXPLORE
print("\n── EXPLORE ──")
with agent.explore() as ctx:
    state = ctx.call("read_plc", device="line-3", register="speed")
    print(f"  Current state: {state}")

# DECIDE
print("\n── DECIDE ──")
with agent.decide() as ctx:
    plan = ctx.propose(
        adjustment={"speed": 105},
        reason="Production target requires 5% increase",
        confidence=0.92,
    )
    print(f"  Proposal: speed → 105 rpm (confidence: 92%)")

# COMMIT
print("\n── COMMIT (transactional) ──")
with agent.commit() as tx:
    tx.call("write_mes", cost=0.10, record=plan)
    tx.call("write_plc", cost=0.20, device="line-3", value=105)
    tx.call("notify_shift", cost=0.05, msg="Speed adjusted to 105 rpm on line-3")

print(f"\n  Transaction: {tx.tx.state.value}")
print(f"  Budget: ${agent.budget.spent:.2f} / ${agent.budget.limit:.2f} ({agent.budget.pct:.0f}%)")

# PROOF TRACES
print("\n── PROOF TRACES ──")
for i, trace in enumerate(agent.traces):
    status = "✓" if trace.decision in ("ALLOWED", "FLAGGED") else "✗"
    flag = " ⚑" if trace.decision == "FLAGGED" else ""
    tx_info = f" [tx:{trace.tx_id}]" if trace.tx_id else ""
    print(f"  {status} {trace.tool} → {trace.decision}{flag}{tx_info} (phase:{trace.phase}, ${trace.budget_spent:.2f})")
    for rule in trace.rules_evaluated:
        icon = "  ✓" if rule["passed"] else "  ✗"
        print(f"    {icon} {rule['detail']}")

print("\n" + "=" * 60)
print("Done. 4 tool calls, 4 proof traces, 1 transaction, $0.35 spent.")
print("=" * 60)
