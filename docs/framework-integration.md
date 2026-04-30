# Framework Integration

Shape wraps callables. If your framework calls functions, Shape governs them.

## Generic pattern

```python
from shape import Agent, ToolEffect, wrap_tool

agent = Agent("my-agent", budget=5.00)
governed_fn = wrap_tool(agent, "my_tool", original_fn, ToolEffect.REVERSIBLE)
```

`wrap_tool` returns a callable that passes through Shape's gate before executing.

## Strands Agents SDK

```python
from shape import Agent, ToolEffect, wrap_tool

agent = Agent("strands-agent", budget=5.00)

# Wrap each tool the Strands agent uses
governed_search = wrap_tool(agent, "search", search_fn, ToolEffect.READ)
governed_email  = wrap_tool(agent, "send_email", email_fn, ToolEffect.IRREVERSIBLE)
```

## LangGraph

```python
from shape import Agent, ToolEffect, wrap_tool

agent = Agent("langgraph-agent", budget=5.00)

# Wrap tools before passing to the graph
tools = [
    wrap_tool(agent, "query", query_fn, ToolEffect.READ),
    wrap_tool(agent, "update", update_fn, ToolEffect.REVERSIBLE),
]
```

## CrewAI

```python
from shape import Agent as ShapeAgent, ToolEffect, wrap_tool

shape = ShapeAgent("crew-agent", budget=5.00)

# Wrap CrewAI tool functions
governed_fn = wrap_tool(shape, "research", research_fn, ToolEffect.READ)
```

## Real agent loop (raw Python)

```python
agent = Agent("my-agent", budget=5.00)

agent.tool("call_llm", effect=ToolEffect.READ, fn=call_claude,
           cost_fn=lambda r: r.usage.total_tokens * 0.00003)
agent.tool("read_db",    effect=ToolEffect.READ,         fn=read_db_fn)
agent.tool("send_email", effect=ToolEffect.IRREVERSIBLE, fn=send_email_fn)

# EXPLORE — gather context
with agent.explore() as ctx:
    while True:
        response = ctx.call("call_llm", prompt=history)
        if response.stop_reason == "tool_use":
            result = ctx.call(response.tool_name, **response.tool_args)
            history.append(result)
        else:
            break

# COMMIT — execute with transaction protection
with agent.commit() as tx:
    while True:
        response = tx.call("call_llm", prompt=history)
        if response.stop_reason == "tool_use":
            tx.call(response.tool_name, cost=0.10, **response.tool_args)
        else:
            break
```

## API Reference

| Method | Description |
|--------|-------------|
| `Agent(name, budget=0.0)` | Create a governed agent |
| `agent.tool(name, effect, fn, compensation, cost_fn)` | Register a tool |
| `agent.rules(text)` | Add governance rules |
| `agent.on_approval(callback)` | Set approval handler |
| `agent.explore()` | Enter EXPLORE phase (read-only) |
| `agent.decide()` | Enter DECIDE phase (read-only, proposals) |
| `agent.commit()` | Enter COMMIT phase (transactional) |
| `agent.traces` | All proof traces |
| `wrap_tool(agent, name, fn, effect, cost_fn)` | Register + return governed callable |
