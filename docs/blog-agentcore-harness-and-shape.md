---
title: "Your Agent Has Infrastructure. It Still Has No Guardrails."
published: false
description: "AWS AgentCore Harness manages compute, memory, and tools for AI agents. Shape adds the missing governance layer: phases, transactions, budget gates, and proof traces."
tags: ["ai", "aws", "python", "agents"]
---

# Your agent has infrastructure. It still has no guardrails.

AWS just shipped a new managed service called AgentCore Harness (public preview). It handles the infrastructure problem that every team building AI agents has been solving from scratch: compute, memory, tool connectivity, observability. You declare a config, you get a running agent.

Here's what it is, what it gives you, and where it stops.

## What is AgentCore Harness?

Every AI agent needs an orchestration loop: call the model, pick a tool, pass results back, manage context, handle failures. Running that loop requires infrastructure underneath. Compute to host the agent. A sandbox to execute code safely. Secure connections to tools. Persistent storage. Identity. Observability.

That infrastructure is the "harness." Until now, every team built it from scratch. AgentCore Harness replaces that build with a configuration.

You declare what your agent does (which model, which tools, which instructions) and AWS handles the rest.

**Available regions**: US West (Oregon), US East (N. Virginia), Asia Pacific (Sydney), Europe (Frankfurt).

**Pricing**: No separate harness charge. You pay for the underlying AgentCore capabilities you use.

**Powered by**: [Strands Agents](https://strandsagents.com), the open-source agent framework from AWS.

## What the harness provides

**Isolated compute**: Every session runs in its own microVM. The agent gets its own filesystem and shell. You can run shell commands directly on the session without model reasoning (no token cost) for setup, scripts, or debugging.

**Stateful by default**: Persistent short-term and long-term memory across sessions. Persistent filesystem. Your agent picks up where it left off.

**Multi-model, mid-session**: Use any model from Amazon Bedrock, OpenAI, or Google Gemini. Switch providers mid-session without losing context.

**Tool connectivity**: Connect tools through [AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html), [MCP servers](https://modelcontextprotocol.io), or the built-in [browser](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html) and [code interpreter](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html).

**Custom environments**: Bring your own source code, dependencies, and tools.

**Automatic observability**: Every action traced through [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html).

**Security**: VPC networking, identity management, access controls per session.

From a team's perspective, this cuts days of infrastructure plumbing down to a config file. Trying a different model or adding a new tool is a config change, not a code rewrite.

Full docs: [AgentCore Harness documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html)

## Where the harness stops

Your agent now has a secure environment, persistent memory, and access to a dozen tools. The infrastructure problem is solved. But a different set of questions remains:

- Can the agent call `send_email` before it's finished reading customer data?
- If a 3-step workflow fails at step 2, does step 1 get rolled back?
- When the agent burns 90% of its budget, does its behavior actually change?
- Can you prove *why* a specific tool call was permitted, not just that it happened?

AgentCore Harness traces *what* happened. It doesn't control *what's allowed to happen*. It provides observability, not governance.

This isn't a criticism. It's a layer boundary. Infrastructure and governance are separate concerns.

## Shape: runtime governance for the tools your agent calls

[Shape](https://github.com/vidanov/shape) is a single-file Python library (~400 lines, zero dependencies) that adds the governance layer:

```python
from shape import Agent, ToolEffect

agent = Agent("customer-service", budget=5.00)

agent.tool("lookup_customer", effect=ToolEffect.READ, fn=lookup_fn)
agent.tool("update_record",   effect=ToolEffect.REVERSIBLE, fn=update_fn)
agent.tool("send_email",      effect=ToolEffect.IRREVERSIBLE, fn=email_fn)

agent.rules("""
    BLOCK send_email WHEN phase IS NOT commit
    BLOCK * WHEN budget ABOVE 90%
""")

# EXPLORE: read-only, safe
with agent.explore() as ctx:
    customer = ctx.call("lookup_customer", id="C-1234")

# COMMIT: transactional, all-or-nothing
with agent.commit() as tx:
    tx.call("update_record", cost=0.01, id="C-1234", status="welcomed")
    tx.call("send_email",    cost=0.10, to=customer["email"], template="welcome")
    # if send_email fails → update_record is compensated automatically
```

### What Shape enforces

**Phase lifecycle**: Explore → Decide → Commit. In Explore, only read tools work. Call a write tool in Explore and you get an exception, not a warning. The agent reads before it writes, structurally.

**Transactional tool calls**: Either all steps in a commit succeed, or none stick. Automatic compensation (rollback) on failure. Databases solved this in 1978. AI agents still haven't, until now.

**Budget as a control signal**: Not a metric you check after the bill arrives. At configurable thresholds, the agent's behavior changes in real time: reduce scope, block commits, force re-evaluation, full stop.

**Proof traces**: A structured record of *why* each tool call was permitted. Phase check passed. Budget check passed. Rule check passed. Not a log line. A decision chain.

**Human-readable rule DSL**: Governance rules that non-engineers can read and audit.

## How they fit together

```
┌─────────────────────────────────────┐
│  Agent logic (LLM + prompts)        │
├─────────────────────────────────────┤
│  Shape (governance)                 │  ← permission, phases, transactions
├─────────────────────────────────────┤
│  AgentCore Harness (infrastructure) │  ← compute, memory, networking
└─────────────────────────────────────┘
```

Deploy Shape inside an AgentCore Harness custom environment. The harness provides the runtime. Shape controls what the agent is allowed to do inside that runtime.

| Capability | AgentCore Harness | Shape |
|-----------|------------------|-------|
| Managed compute and isolation | ✓ | not its job |
| Persistent memory/filesystem | ✓ | not its job |
| Multi-model switching | ✓ | not its job |
| Observability (what happened) | ✓ | not its job |
| Phase enforcement (read before write) | ✗ | ✓ |
| Transactional tool calls with rollback | ✗ | ✓ |
| Budget as a behavioral gate | ✗ | ✓ |
| Proof traces (why it was permitted) | ✗ | ✓ |
| Human-readable rule DSL | Cedar (via Gateway) | built-in |
| Vendor lock-in | AWS | none |
| Dependencies | AWS SDK | zero |

## The pattern across frameworks

This gap isn't specific to AgentCore. LangGraph, CrewAI, Strands: they optimize for capability. None enforce permission at runtime.

From real projects, the failure modes repeat:

- Agent writes to a database before finishing its read phase. Partial data corrupts downstream services.
- A 3-step workflow fails at step 2. Step 1 already committed. Manual cleanup follows.
- Cost spikes because nothing gates behavior at budget thresholds. You find out from the invoice.
- An incident happens. You can trace what the agent did, but not why the system allowed it.

Infrastructure answers "can my agent run?" Governance answers "should my agent act right now, with this tool, at this cost?"

## Links

- [AgentCore Harness docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html)
- [AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [Strands Agents (open-source framework powering the harness)](https://strandsagents.com)
- [Shape on GitHub](https://github.com/vidanov/shape)
- [Shape visual explainer](https://vidanov.github.io/shape/)
- [Shape interactive demo](https://vidanov.github.io/shape/demo.html)
