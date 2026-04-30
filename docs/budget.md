# Budget Gates

Budget isn't just tracked — it *changes agent behavior* at thresholds.

## Thresholds

| Spent | What happens |
|-------|-------------|
| < 50% | Normal operation |
| ≥ 50% | **DEGRADE** — signal to reduce scope |
| ≥ 75% | **FORCE_DECIDE** — blocks COMMIT, forces re-evaluation |
| ≥ 100% | **STOP** — all tool calls blocked |

Your agent doesn't just run out of money. At 75%, it's *forced to stop and think*.

## Usage

```python
agent = Agent("my-agent", budget=5.00)

# Each tool call declares its cost
with agent.commit() as tx:
    tx.call("charge_card", cost=0.50, amount=99.00)
    tx.call("send_email",  cost=0.10, to=email)
    # budget_spent is now 0.60 / 5.00 = 12%
```

## Governing LLM inference cost

The LLM itself burns tokens outside Shape's control — unless you wrap it:

```python
agent.tool("call_llm",
           effect=ToolEffect.READ,
           fn=lambda prompt, **kw: claude.messages.create(
               model="sonnet", messages=[{"role": "user", "content": prompt}]
           ),
           cost_fn=lambda r: r.usage.input_tokens  * 0.000003
                           + r.usage.output_tokens * 0.000015)
```

`cost_fn` takes the tool's return value and returns a dollar amount. The cost is recorded *after* execution — same as a credit card: the purchase that maxes you out goes through, the next one declines.

## Budget in rules

```
BLOCK * WHEN budget ABOVE 90%
FLAG * WHEN budget ABOVE 50%
```

## Real-world pattern

```python
agent = Agent("my-agent", budget=5.00)

# Wrap LLM — inference cost tracked
agent.tool("call_llm", effect=ToolEffect.READ, fn=call_claude,
           cost_fn=lambda r: r.usage.total_tokens * 0.00003)

# Wrap tools — explicit cost per call
agent.tool("send_email", effect=ToolEffect.IRREVERSIBLE, fn=send_email_fn)

# One budget pool. LLM inference + tool costs. One gate for everything.
with agent.explore() as ctx:
    response = ctx.call("call_llm", prompt="analyze this")  # cost tracked via cost_fn

with agent.commit() as tx:
    tx.call("send_email", cost=0.10, to=email)              # cost tracked explicitly
```
