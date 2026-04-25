# Shape

**Guardrails for AI agents that actually work.**

One file. Zero dependencies. 466 lines of Python.

```
Your agent just mass-emailed 10,000 customers with a hallucinated discount.
It had the tool. It had the permission. Nobody told it to stop.
```

Shape prevents this. It wraps any tool-calling agent with hard governance — not guidelines, not prompts, not vibes.

## The Problem

AI agents are getting tool access: databases, APIs, payment systems, infrastructure. The frameworks that power them (LangGraph, CrewAI, Strands) optimize for *capability*. None of them optimize for *permission*.

What's missing:
- **No lifecycle phases.** Agents can write before they've finished reading.
- **No transactions.** A 3-step action fails halfway — step 1 sticks, steps 2-3 don't.
- **No budget control.** Cost is a metric you check after the damage.
- **No audit trail.** You know *what* happened, not *why it was allowed*.

Shape fills all four gaps.

## Install

```bash
cp shape.py /your/project/
```

That's it. No pip. No dependencies. No config server.

## 60-Second Demo

```python
from shape import Agent, ToolEffect

# Create a governed agent with a $5 budget
agent = Agent("customer-service", budget=5.00)

# Register tools with effect classification
agent.tool("lookup_customer", effect=ToolEffect.READ,         fn=lookup_fn)
agent.tool("update_record",   effect=ToolEffect.REVERSIBLE,   fn=update_fn)
agent.tool("send_email",      effect=ToolEffect.IRREVERSIBLE, fn=email_fn)

# Add rules anyone can read
agent.rules("""
    BLOCK send_email WHEN phase IS NOT commit
    BLOCK * WHEN budget ABOVE 90%
    REQUIRE APPROVAL FOR * WHEN tool IS irreversible
""")

# EXPLORE — read only, safe
with agent.explore() as ctx:
    customer = ctx.call("lookup_customer", id="C-1234")

# DECIDE — evaluate, propose, no side effects
with agent.decide() as ctx:
    plan = ctx.propose(action="send_welcome_email", to=customer["email"])

# COMMIT — transactional, all-or-nothing
with agent.commit() as tx:
    tx.call("update_record", cost=0.01, id="C-1234", status="welcomed")
    tx.call("send_email",    cost=0.10, to=customer["email"], template="welcome")
    # if send_email fails → update_record is compensated automatically
```

**Three phases. One transaction. Full audit trail. The agent can't skip ahead.**

## How It Works

### Phases — control *when* agents can act

```
EXPLORE ──→ DECIDE ──→ COMMIT
   ↑                      │
   └──────────────────────┘
```

| Phase | What's allowed | Purpose |
|-------|---------------|---------|
| **EXPLORE** | Read only | Gather information safely |
| **DECIDE** | Read only | Evaluate options, propose actions |
| **COMMIT** | Read + Write | Execute with transactional protection |

An agent in EXPLORE *cannot* call a write tool. Not "shouldn't" — *cannot*. It raises an exception.

### Effect Classification — know what each tool does

| Effect | Meaning | Example |
|--------|---------|---------|
| `READ` | No side effects | Query DB, read file, call GET endpoint |
| `REVERSIBLE` | Can be undone | Update record (has undo), create draft |
| `IRREVERSIBLE` | Cannot be undone | Send email, charge card, deploy to prod |

### Transactions — protect multi-step actions

```python
with agent.commit() as tx:
    tx.call("charge_card",   cost=0.50, amount=99.00)   # step 1
    tx.call("create_order",  cost=0.01, items=cart)      # step 2
    tx.call("send_receipt",  cost=0.10, to=email)        # step 3
```

If step 2 fails: step 1 is compensated (refund). Step 3 never runs.

Register compensation when defining tools:

```python
agent.tool("charge_card", effect=ToolEffect.REVERSIBLE,
           fn=charge_fn, compensation=lambda: refund())
```

### Budget Gates — cost as a control signal, not a log line

Budget isn't just tracked — it *changes agent behavior* at thresholds:

| Spent | What happens |
|-------|-------------|
| < 50% | Normal operation |
| ≥ 50% | **DEGRADE** — signal to reduce scope |
| ≥ 75% | **FORCE_DECIDE** — blocks COMMIT, forces re-evaluation |
| ≥ 100% | **STOP** — all tool calls blocked |

Your agent doesn't just run out of money. At 75%, it's *forced to stop and think*.

### Rule DSL — governance anyone can read

```
BLOCK send_email WHEN phase IS NOT commit
BLOCK * WHEN budget ABOVE 90%
REQUIRE APPROVAL FOR * WHEN tool IS irreversible
FLAG * WHEN time OUTSIDE 09:00-17:00
```

No Cedar. No Rego. No policy server. Your product manager can read these rules. Your compliance team can write them.

**Syntax:** `ACTION tool WHEN condition [AND condition] [UNLESS condition]`

| Action | Effect |
|--------|--------|
| `BLOCK` | Prevent execution |
| `ALLOW` | Explicitly permit (logged) |
| `FLAG` | Allow but mark for review |
| `REQUIRE APPROVAL FOR` | Call approval callback first |

| Condition | Operators | Example |
|-----------|-----------|---------|
| `phase` | IS, IS NOT | `phase IS NOT commit` |
| `tool` | IS, IS NOT | `tool IS irreversible` |
| `budget` | ABOVE, BELOW | `budget ABOVE 80%` |
| `time` | OUTSIDE | `time OUTSIDE 06:00-22:00` |

### Proof Traces — know *why* every action was allowed

Every tool call produces a structured decision record:

```python
{
    "tool": "send_email",
    "decision": "ALLOWED",
    "phase": "commit",
    "budget_spent": 0.11,
    "budget_limit": 5.00,
    "rules_evaluated": [
        {"check": "phase",  "passed": True,  "detail": "Phase commit allows irreversible"},
        {"check": "budget", "passed": True,  "detail": "2.2% spent"},
        {"check": "rule",   "passed": True,  "detail": "Approval granted"},
    ],
    "tx_id": "T1",
    "duration_s": 0.003
}
```

Not "what happened" — **why it was permitted**. Every decision. Every rule evaluated. Every trace queryable.

## Integration

Shape wraps callables. If your framework calls functions, Shape governs them.

```python
# Strands Agents SDK
from shape import Agent, ToolEffect, wrap_tool

agent = Agent("my-agent", budget=5.00)
governed_fn = wrap_tool(agent, "my_tool", original_fn, ToolEffect.REVERSIBLE)

# LangGraph, CrewAI, raw Python — same pattern
agent.tool("any_tool", effect=ToolEffect.READ, fn=any_callable)
```

## API Reference

| Method | Description |
|--------|-------------|
| `Agent(name, budget=0.0)` | Create a governed agent |
| `agent.tool(name, effect, fn, compensation)` | Register a tool |
| `agent.rules(text)` | Add governance rules |
| `agent.on_approval(callback)` | Set approval handler |
| `agent.explore()` | Enter EXPLORE phase (read-only) |
| `agent.decide()` | Enter DECIDE phase (read-only, proposals) |
| `agent.commit()` | Enter COMMIT phase (transactional) |
| `agent.traces` | All proof traces |
| `wrap_tool(agent, name, fn, effect)` | Register + return governed callable |

## Testing

```bash
python -m pytest test_shape.py -v
# 54 tests, 0.04s
```

## Why This Exists

Between December 2025 and March 2026, at least four independent groups arrived at the same insight: AI agents need lifecycle governance. Galileo built observability. AWS built Cedar policies. Atomix formalized transactions. Forrester named the category "Agent Control Plane."

Nobody combined phases + transactions + budget gates + proof traces in one place.

Shape does. In 466 lines.

## License

MIT
