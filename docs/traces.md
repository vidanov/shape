# Proof Traces

Every tool call produces a structured decision record — not just *what* happened, but *why it was permitted*.

## Trace structure

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

## Accessing traces

```python
agent = Agent("my-agent", budget=5.00)

# ... tool calls ...

# All traces
for trace in agent.traces:
    print(trace["tool"], trace["decision"])

# Filter blocked calls
blocked = [t for t in agent.traces if t["decision"] == "BLOCKED"]
```

## What traces answer

| Question | Field |
|----------|-------|
| What tool was called? | `tool` |
| Was it allowed? | `decision` |
| What phase was the agent in? | `phase` |
| How much budget was used? | `budget_spent` / `budget_limit` |
| Which rules were evaluated? | `rules_evaluated` |
| Was it part of a transaction? | `tx_id` |
| How long did it take? | `duration_s` |

## Why this matters

Traditional logging tells you *what* happened. Proof traces tell you *why the system allowed it*. This is the difference between:

- "Email was sent at 14:32" (audit log)
- "Email was allowed because: agent was in commit phase, budget was at 2.2%, rule 'BLOCK send_email WHEN phase IS NOT commit' evaluated to false, approval callback returned true" (proof trace)

The second one is what compliance teams, incident responders, and debugging engineers actually need.
