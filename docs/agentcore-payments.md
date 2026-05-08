# Shape + Amazon Bedrock AgentCore Payments

## Context

Amazon Bedrock AgentCore [shipped payment capabilities in preview](https://aws.amazon.com/blogs/machine-learning/agents-that-transact-introducing-amazon-bedrock-agentcore-payments-built-with-coinbase-and-stripe/) on 2026-05-07.

Agents can hold wallets (Coinbase CDP or Stripe Privy), make micropayments via the x402 protocol, and buy access to APIs, MCP servers, and content autonomously.

Available in: us-east-1, us-west-2, eu-central-1, ap-southeast-2.

## What AgentCore payments provides

- Wallet management (Coinbase CDP wallets, Stripe Privy wallets)
- x402 protocol: HTTP 402 → auto-pay → content delivered back to agent
- Per-session spending limits
- User authorization before agent can access wallet
- Observability (logs, metrics, traces in AgentCore console)
- Coinbase x402 Bazaar MCP server for agent discovery of paid endpoints

## What AgentCore payments does NOT provide

- **No lifecycle phases**: agent can pay during exploration before forming a plan
- **No multi-step atomicity**: if step 2 fails after step 1 paid, no compensation
- **No graduated budget behavior**: spending limit is binary (under/over), not behavioral
- **No proof traces**: observability shows what happened, not why it was *permitted*
- **No per-call approval thresholds**: can't distinguish "50 calls at $0.01" from "1 call at $2.40"

## How Shape fills the gaps

| Gap | Shape feature |
|-----|--------------|
| Premature payments | Phases: payment tools blocked until COMMIT |
| Partial failure | Transactions with compensation |
| Flat spending limits | Budget gates (50% degrade, 75% block, 90% stop) |
| No decision audit | Proof traces for every tool call |
| No approval rules | Rule DSL: `REQUIRE APPROVAL FOR * WHEN cost ABOVE 0.50` |

## Integration pattern

```python
from shape import Agent, ToolEffect

# Your AgentCore payment function (wraps the AgentCore SDK call)
def agentcore_pay(endpoint: str = "", **kw):
    # Calls AgentCore payment API
    # Returns content from paid endpoint
    ...

agent = Agent("research-agent", budget=5.00)

# Register payment as irreversible tool
agent.tool("pay_for_data", effect=ToolEffect.IRREVERSIBLE, fn=agentcore_pay)
agent.tool("analyze", effect=ToolEffect.READ, fn=analyze_fn)
agent.tool("send_report", effect=ToolEffect.IRREVERSIBLE, fn=send_fn)

agent.rules("""
BLOCK pay_for_data WHEN phase IS NOT commit
BLOCK * WHEN budget ABOVE 90%
REQUIRE APPROVAL FOR * WHEN cost ABOVE 0.50
FLAG * WHEN time OUTSIDE 09:00-17:00
""")

# EXPLORE: gather info, no payments possible
with agent.explore() as ctx:
    sources = ctx.call("list_available_feeds")

# DECIDE: propose what to buy
with agent.decide() as ctx:
    plan = ctx.propose(action="buy_market_data", source="premium-feed", cost=0.05)

# COMMIT: pay and act, transactionally
with agent.commit() as tx:
    data = tx.call("pay_for_data", cost=0.05, endpoint="premium-feed")
    result = tx.call("analyze", cost=0.01, data=data)
    tx.call("send_report", cost=0.10, to="user@company.com", body=result)
    # if analyze fails → compensation fires for pay_for_data
```

## Positioning

Shape is not competing with AgentCore. They operate at different layers:

- **AgentCore payments** = payment execution infrastructure (wallets, protocols, rails)
- **Shape** = governance over when/whether the agent is allowed to use those rails

Shape wraps the agent. AgentCore provides the tools the agent calls. Shape decides if the call is permitted.

## Links

- [AWS announcement](https://aws.amazon.com/blogs/machine-learning/agents-that-transact-introducing-amazon-bedrock-agentcore-payments-built-with-coinbase-and-stripe/)
- [AgentCore payments docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments.html)
- [x402 protocol](https://www.x402.org/)
- [Coinbase CDP](https://docs.cdp.coinbase.com/)
- [Stripe Privy](https://privy.io/)
