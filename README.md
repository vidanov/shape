# Shape

**Governance for AI agents. One file. Zero dependencies.**

```
Your agent just mass-emailed 10,000 customers with a hallucinated discount.
It had the tool. It had the permission. Nobody told it to stop.
```

Shape prevents this.

🌐 [Visual explainer](https://vidanov.github.io/shape/) · 🎮 [Interactive demo](https://vidanov.github.io/shape/demo.html) · 📄 [Full article](https://vidanov.github.io/shape/article.html)

---

## What it does

```python
from shape import Agent, ToolEffect

agent = Agent("customer-service", budget=5.00)

agent.tool("lookup_customer", effect=ToolEffect.READ,         fn=lookup_fn)
agent.tool("update_record",   effect=ToolEffect.REVERSIBLE,   fn=update_fn)
agent.tool("send_email",      effect=ToolEffect.IRREVERSIBLE, fn=email_fn)

agent.rules("""
    BLOCK send_email WHEN phase IS NOT commit
    BLOCK * WHEN budget ABOVE 90%
""")

# EXPLORE → read only, safe
with agent.explore() as ctx:
    customer = ctx.call("lookup_customer", id="C-1234")

# COMMIT → transactional, all-or-nothing
with agent.commit() as tx:
    tx.call("update_record", cost=0.01, id="C-1234", status="welcomed")
    tx.call("send_email",    cost=0.10, to=customer["email"], template="welcome")
    # if send_email fails → update_record is compensated automatically
```

**Three phases. One transaction. Full audit trail.**

---

## Why Shape exists

AI agents get tool access — databases, APIs, payments, infrastructure. The frameworks (LangGraph, CrewAI, Strands) optimize for *capability*. None optimize for *permission*.

| Gap | What goes wrong |
|-----|----------------|
| No lifecycle phases | Agent writes before it finishes reading |
| No transactions | 3-step action fails halfway — step 1 sticks |
| No budget control | Cost is a metric you check *after* the damage |
| No audit trail | You know *what* happened, not *why it was allowed* |

Shape fills all four. In ~400 lines of Python.

---

## Install

```bash
cp shape.py /your/project/
```

No pip. No dependencies. No config server.

---

## Core concepts

| Concept | One-liner | Docs |
|---------|-----------|------|
| **Phases** | EXPLORE → DECIDE → COMMIT. Controls *when* agents can act | [→ phases](docs/phases.md) |
| **Effect classification** | READ / REVERSIBLE / IRREVERSIBLE per tool | [→ effects](docs/effects.md) |
| **Transactions** | All-or-nothing with automatic compensation | [→ transactions](docs/transactions.md) |
| **Budget gates** | Cost as a control signal, not a log line | [→ budget](docs/budget.md) |
| **Rule DSL** | Human-readable governance rules | [→ rules](docs/rules.md) |
| **Proof traces** | Structured record of *why* each call was allowed | [→ traces](docs/traces.md) |

---

## Integration with coding agents

Shape governs any tool-calling agent via hooks (Architecture A):

| Agent | Directory | Setup |
|-------|-----------|-------|
| [Kiro CLI](https://kiro.dev) | [`kiro/`](kiro/README.md) | PreToolUse/PostToolUse hooks |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | [`claude/`](claude/README.md) | `.claude/settings.json` hooks |
| [OpenAI Codex CLI](https://github.com/openai/codex) | [`codex/`](codex/README.md) | Config-based hooks |

**Limitations (Architecture A):** No transactional atomicity, no compensation, estimated budget, manual phase transitions. See each directory's README for details.

For full governance including transactions → use Architecture B (Shape as orchestrator). See [→ architecture](docs/architecture.md).

---

## Integration with agent frameworks

```python
from shape import Agent, ToolEffect, wrap_tool

agent = Agent("my-agent", budget=5.00)
governed_fn = wrap_tool(agent, "my_tool", original_fn, ToolEffect.REVERSIBLE)
```

Works with Strands, LangGraph, CrewAI, or raw Python. If your framework calls functions, Shape governs them. See [→ framework integration](docs/framework-integration.md).

---

## How Shape compares

| Capability | Galileo | AWS AgentCore | Atomix | **Shape** |
|-----------|---------|---------------|--------|-----------|
| Phase enforcement | ✗ | ✗ | ✗ | ✓ |
| Transactional tool calls | ✗ | ✗ | ✓ (paper) | ✓ |
| Compensation / rollback | ✗ | ✗ | partial | ✓ |
| Cost as control signal | ✗ | ✗ | ✗ | ✓ |
| Proof traces | ✗ | ✗ | ✗ | ✓ |
| Readable rule DSL | ✗ | Cedar | ✗ | ✓ |
| Dependencies | many | AWS SDK | N/A | **zero** |

---

## Testing

```bash
python -m pytest test_shape.py -v   # 58 tests
```

---

## License

MIT
