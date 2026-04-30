# Transactions

Shape provides all-or-nothing execution for multi-step agent actions.

## The problem

```python
# Without transactions:
charge_card(amount=99.00)    # ✓ succeeds
create_order(items=cart)     # ✗ fails
send_receipt(to=email)       # never runs
# Customer is charged but has no order. Manual cleanup needed.
```

## The solution

```python
with agent.commit() as tx:
    tx.call("charge_card",   cost=0.50, amount=99.00)   # step 1
    tx.call("create_order",  cost=0.01, items=cart)      # step 2 — fails
    tx.call("send_receipt",  cost=0.10, to=email)        # step 3 — never runs
    # Step 1 is automatically compensated (refund issued)
```

If any step fails, all previously completed steps are compensated in reverse order.

## Registering compensation

```python
agent.tool("charge_card",
           effect=ToolEffect.REVERSIBLE,
           fn=charge_fn,
           compensation=lambda: refund())

agent.tool("create_order",
           effect=ToolEffect.REVERSIBLE,
           fn=create_order_fn,
           compensation=lambda: cancel_order())
```

## How it works

1. Each `tx.call()` executes the tool and records it in the transaction log
2. If a call raises an exception, the transaction enters rollback mode
3. Compensation functions are called in reverse order for all completed steps
4. The transaction trace records the full sequence including rollback

## Limitations

- Compensation is best-effort — if a compensation function itself fails, it's logged but execution continues
- IRREVERSIBLE tools cannot be compensated (by definition) — use `REQUIRE APPROVAL` rules for these
- Transactions are per-commit-block, not distributed across multiple agents
