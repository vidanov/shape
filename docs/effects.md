# Effect Classification

Every tool registered with Shape declares its effect — what it does to the world.

## The three effects

| Effect | Meaning | Example |
|--------|---------|---------|
| `READ` | No side effects | Query DB, read file, call GET endpoint |
| `REVERSIBLE` | Can be undone | Update record (has undo), create draft |
| `IRREVERSIBLE` | Cannot be undone | Send email, charge card, deploy to prod |

## Usage

```python
from shape import Agent, ToolEffect

agent = Agent("my-agent", budget=5.00)

agent.tool("query_db",     effect=ToolEffect.READ,         fn=query_fn)
agent.tool("update_record", effect=ToolEffect.REVERSIBLE,   fn=update_fn, compensation=undo_fn)
agent.tool("send_email",   effect=ToolEffect.IRREVERSIBLE, fn=email_fn)
```

## How effects interact with phases

| Phase | READ | REVERSIBLE | IRREVERSIBLE |
|-------|------|-----------|-------------|
| EXPLORE | ✓ | ✗ | ✗ |
| DECIDE | ✓ | ✗ | ✗ |
| COMMIT | ✓ | ✓ | ✓ |

## How effects interact with rules

The rule DSL can reference effects:

```
REQUIRE APPROVAL FOR * WHEN tool IS irreversible
FLAG * WHEN tool IS reversible
```

## Compensation

REVERSIBLE tools should provide a compensation function — what to call if the transaction needs to roll back:

```python
agent.tool("charge_card",
           effect=ToolEffect.REVERSIBLE,
           fn=charge_fn,
           compensation=lambda: refund())
```

If a later step in a transaction fails, Shape calls compensation functions for all completed steps in reverse order.
