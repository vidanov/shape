# Phases

Shape enforces a strict lifecycle on agent behavior.

```
EXPLORE ──→ DECIDE ──→ COMMIT
   ↑                      │
   └──────────────────────┘
```

## The three phases

| Phase | What's allowed | Purpose |
|-------|---------------|---------|
| **EXPLORE** | Read only | Gather information safely |
| **DECIDE** | Read only | Evaluate options, propose actions |
| **COMMIT** | Read + Write | Execute with transactional protection |

An agent in EXPLORE *cannot* call a write tool. Not "shouldn't" — *cannot*. It raises an exception.

## Usage

```python
from shape import Agent, ToolEffect

agent = Agent("my-agent", budget=5.00)
agent.tool("read_db",    effect=ToolEffect.READ,         fn=read_fn)
agent.tool("send_email", effect=ToolEffect.IRREVERSIBLE, fn=email_fn)

# EXPLORE — only READ tools work
with agent.explore() as ctx:
    data = ctx.call("read_db", query="SELECT *")
    # ctx.call("send_email", ...) → raises PhaseError

# DECIDE — same as explore, but semantically for evaluation
with agent.decide() as ctx:
    plan = ctx.propose(action="send_email", to="user@example.com")

# COMMIT — all tools available, transactional
with agent.commit() as tx:
    tx.call("send_email", cost=0.10, to="user@example.com")
```

## Why phases matter

Without phases, an agent with access to `send_email` can call it at any time — during information gathering, during planning, whenever. Phases create a mandatory workflow:

1. **Read first** — understand the situation
2. **Plan second** — propose what to do
3. **Act last** — execute with protection

This mirrors how humans work in high-stakes environments (surgery, aviation, finance): observe, orient, act.

## Phase transitions

Phases must be entered explicitly via context managers. There's no way to "skip ahead" — the code structure enforces the order.

In CLI agent integrations (Kiro, Claude Code, Codex), phase transitions are manual:

```bash
shape-transition explore   # safe mode
shape-transition decide    # planning mode
shape-transition commit    # execution mode
```
