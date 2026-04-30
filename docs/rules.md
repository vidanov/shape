# Rule DSL

Human-readable governance rules. No Cedar. No Rego. No policy server.

## Syntax

```
ACTION tool_pattern WHEN condition [AND condition] [UNLESS condition]
```

## Actions

| Action | Effect |
|--------|--------|
| `BLOCK` | Prevent execution |
| `ALLOW` | Explicitly permit (logged) |
| `FLAG` | Allow but mark for review |
| `REQUIRE APPROVAL FOR` | Call approval callback first |

## Conditions

| Condition | Operators | Example |
|-----------|-----------|---------|
| `phase` | IS, IS NOT | `phase IS NOT commit` |
| `tool` | IS, IS NOT | `tool IS irreversible` |
| `budget` | ABOVE, BELOW | `budget ABOVE 80%` |
| `time` | OUTSIDE | `time OUTSIDE 06:00-22:00` |

## Examples

```
# Only allow writes in commit phase
BLOCK send_email WHEN phase IS NOT commit

# Hard stop at 90% budget
BLOCK * WHEN budget ABOVE 90%

# Require human approval for irreversible actions
REQUIRE APPROVAL FOR * WHEN tool IS irreversible

# Flag after-hours activity
FLAG * WHEN time OUTSIDE 09:00-17:00

# Allow reads always
ALLOW read_db WHEN phase IS explore
```

## Usage in code

```python
agent = Agent("my-agent", budget=5.00)

agent.rules("""
    BLOCK send_email WHEN phase IS NOT commit
    BLOCK * WHEN budget ABOVE 90%
    REQUIRE APPROVAL FOR * WHEN tool IS irreversible
""")

# Or load from file
with open("rules.shape") as f:
    agent.rules(f.read())
```

## Approval handler

```python
def my_approval(tool_name, args, context):
    """Called when REQUIRE APPROVAL matches. Return True to allow."""
    return input(f"Allow {tool_name}? [y/n] ") == "y"

agent.on_approval(my_approval)
```

## Design philosophy

- Your product manager can read these rules
- Your compliance team can write them
- No separate policy language to learn
- Rules are evaluated in order; first match wins
