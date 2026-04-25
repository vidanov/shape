"""
Shape — Customer service agent demo.

An AI agent that handles refunds: reads order data, decides on action, commits atomically.
Run from repo root: python3 examples/customer_service.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shape import Agent, ToolEffect, TxState


# ── Simulated tools ─────────────────────────────────────────────────────────

def lookup_order(order_id: str = "", **kw) -> dict:
    return {"order_id": order_id, "amount": 89.99, "status": "delivered", "customer": "alice@example.com"}


def check_refund_policy(order_id: str = "", **kw) -> dict:
    return {"eligible": True, "reason": "within 30-day window", "max_refund": 89.99}


def process_refund(order_id: str = "", amount: float = 0, **kw) -> dict:
    print(f"  [PAYMENT] Refunding ${amount:.2f} for order {order_id}")
    return {"refunded": True, "amount": amount, "tx_ref": "REF-20260425-001"}


def undo_refund(tx_ref: str = "REF-20260425-001") -> dict:
    print(f"  [PAYMENT] COMPENSATING: reversing refund {tx_ref}")
    return {"reversed": True}


def update_order_status(order_id: str = "", status: str = "", **kw) -> dict:
    print(f"  [DB] Order {order_id} → {status}")
    return {"updated": True}


def send_email(to: str = "", subject: str = "", **kw) -> dict:
    print(f"  [EMAIL] To: {to} — {subject}")
    return {"sent": True}


# ── Agent setup ──────────────────────────────────────────────────────────────

agent = Agent("refund-agent", budget=2.00)

agent.tool("lookup_order",       effect=ToolEffect.READ,         fn=lookup_order)
agent.tool("check_refund_policy", effect=ToolEffect.READ,        fn=check_refund_policy)
agent.tool("process_refund",     effect=ToolEffect.REVERSIBLE,   fn=process_refund, compensation=undo_refund)
agent.tool("update_order_status", effect=ToolEffect.REVERSIBLE,  fn=update_order_status)
agent.tool("send_email",         effect=ToolEffect.IRREVERSIBLE, fn=send_email)

agent.rules("""
    BLOCK send_email WHEN phase IS NOT commit
    BLOCK * WHEN budget ABOVE 90%
    REQUIRE APPROVAL FOR * WHEN tool IS irreversible
    FLAG * WHEN time OUTSIDE 09:00-17:00
""")

agent.on_approval(lambda tool, kw: True)  # auto-approve for demo


# ── Run ──────────────────────────────────────────────────────────────────────

print("=" * 60)
print("Shape — Customer Service Agent Demo")
print("=" * 60)

# EXPLORE — gather information
print("\n── EXPLORE (read-only) ──")
with agent.explore() as ctx:
    order = ctx.call("lookup_order", order_id="ORD-7891")
    policy = ctx.call("check_refund_policy", order_id="ORD-7891")
    print(f"  Order: ${order['amount']} — {order['status']}")
    print(f"  Policy: {'eligible' if policy['eligible'] else 'not eligible'} ({policy['reason']})")

# DECIDE — evaluate and propose
print("\n── DECIDE (propose, no side effects) ──")
with agent.decide() as ctx:
    plan = ctx.propose(
        action="full_refund",
        order_id="ORD-7891",
        amount=order["amount"],
        reason=policy["reason"],
    )
    print(f"  Proposal: refund ${order['amount']} — {policy['reason']}")

# COMMIT — execute atomically
print("\n── COMMIT (transactional) ──")
with agent.commit() as tx:
    tx.call("process_refund",      cost=0.50, order_id="ORD-7891", amount=89.99)
    tx.call("update_order_status", cost=0.01, order_id="ORD-7891", status="refunded")
    tx.call("send_email",          cost=0.10, to="alice@example.com", subject="Your refund has been processed")

print(f"\n  Transaction: {tx.tx.state.value}")
print(f"  Budget: ${agent.budget.spent:.2f} / ${agent.budget.limit:.2f} ({agent.budget.pct:.0f}%)")

# PROOF TRACES
print("\n── PROOF TRACES ──")
for trace in agent.traces:
    status = "✓" if trace.decision in ("ALLOWED", "FLAGGED") else "✗"
    flag = " ⚑" if trace.decision == "FLAGGED" else ""
    tx_info = f" [tx:{trace.tx_id}]" if trace.tx_id else ""
    print(f"  {status} {trace.tool} → {trace.decision}{flag}{tx_info} ({trace.phase}, ${trace.budget_spent:.2f})")

print(f"\n{'=' * 60}")
print("5 tool calls. 5 proof traces. 1 transaction. $0.61 spent.")
print("If send_email had failed → process_refund would be compensated.")
print("=" * 60)
