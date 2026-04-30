"""Shape Bedrock integration — real cost tracking from Converse API responses."""

# Pricing per 1M tokens (April 2026, Anthropic direct / Bedrock on-demand)
PRICING = {
    # Anthropic Claude (Bedrock matches direct API pricing)
    "anthropic.claude-opus-4-20250514-v1:0":     {"in": 5.00, "out": 25.00},
    "anthropic.claude-sonnet-4-20250514-v1:0":   {"in": 3.00, "out": 15.00},
    "anthropic.claude-haiku-4-20250514-v1:0":    {"in": 1.00, "out": 5.00},
    # Amazon Nova
    "amazon.nova-pro-v1:0":                      {"in": 0.80, "out": 3.20},
    "amazon.nova-lite-v1:0":                     {"in": 0.06, "out": 0.24},
    "amazon.nova-micro-v1:0":                    {"in": 0.035, "out": 0.14},
    # Mistral
    "mistral.mistral-large-3-v1:0":              {"in": 0.50, "out": 1.50},
    # DeepSeek
    "deepseek.deepseek-v3-2-v1:0":              {"in": 0.62, "out": 1.85},
}


def bedrock_cost(result):
    """cost_fn for Shape. Expects result with 'usage' and '_model_id'."""
    usage = result.get("usage", {})
    model_id = result.get("_model_id", "")
    p = PRICING.get(model_id, {"in": 3.00, "out": 15.00})
    tokens_in = usage.get("inputTokens", 0)
    tokens_out = usage.get("outputTokens", 0)
    cost = (tokens_in * p["in"] + tokens_out * p["out"]) / 1_000_000
    return {"cost": cost, "tokens_in": tokens_in, "tokens_out": tokens_out}


def converse(client, model_id, messages, system=None, max_tokens=1000, **kwargs):
    """Thin wrapper around Bedrock Converse that stashes model_id in response."""
    params = {"modelId": model_id, "messages": messages,
              "inferenceConfig": {"maxTokens": max_tokens}}
    if system:
        params["system"] = [{"text": system}]
    params.update(kwargs)
    response = client.converse(**params)
    response["_model_id"] = model_id
    return response
