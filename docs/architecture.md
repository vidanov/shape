# Architecture

Shape can integrate with AI agents in two ways.

## Architecture A: Shape as hook

```
┌─────────────────────────────────┐
│  Agent (Kiro / Claude / Codex)  │
│                                 │
│  tool call ──→ SHAPE gate ──→ execute
│                  │
│              block / allow / flag
└─────────────────────────────────┘
```

Shape runs as a pre-tool-use hook. The agent's own runtime calls Shape before each tool execution. Shape evaluates phase, budget, and rules, then allows or blocks.

**Pros:**
- Easy to add to existing agents
- No changes to agent code
- Works with any hook-compatible CLI

**Cons:**
- No transactional atomicity (each tool call is independent)
- No compensation/rollback
- Budget is estimated
- Phase transitions are manual

**Implementations:** [`kiro/`](../kiro/README.md), [`claude/`](../claude/README.md), [`codex/`](../codex/README.md)

## Architecture B: Shape as orchestrator

```
┌──────────────────────────────────────┐
│  SHAPE orchestrator                  │
│                                      │
│  phase management                    │
│  budget tracking                     │
│  transaction coordination            │
│                                      │
│  ┌────────────────────────────────┐  │
│  │  Agent (via API / subprocess)  │  │
│  │  tool calls go through Shape   │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

Shape wraps the agent entirely. All tool calls are mediated by Shape's transaction engine. This gives full governance including atomic transactions and compensation.

**Pros:**
- Full transactional atomicity
- Automatic compensation on failure
- Accurate budget tracking (including LLM inference via `cost_fn`)
- Programmatic phase transitions

**Cons:**
- Requires wrapping the agent
- More integration effort
- Agent must use Shape's API for tool calls

**Implementation:** Use `shape.py` directly in your Python code (see main README examples).

## Choosing an architecture

| Need | Architecture |
|------|-------------|
| Quick governance on existing CLI agent | A (hooks) |
| Full transactional safety | B (orchestrator) |
| Compliance audit trail | Either (both produce traces) |
| Budget hard-stops | Either |
| Automatic rollback | B only |
