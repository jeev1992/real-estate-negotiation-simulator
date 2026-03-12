# Solution 2: Wire an MCP Tool into the Buyer Agent

## Code changes

### 1. Update `BUYER_MCP_PLANNER_PROMPT` in `m3_langgraph_multiagents/buyer_simple.py`

Add the new tool to the available tools list in the planner prompt:

```python
BUYER_MCP_PLANNER_PROMPT = """You are selecting MCP tools for a buyer negotiation agent.

Return strict JSON in this format:
{
    "tool_calls": [
        {"tool": "<tool_name>", "arguments": { ... }}
    ]
}

Available tools and required arguments:
- get_market_price: {"address": "string", "property_type": "single_family|condo|townhouse"}
- calculate_discount: {
        "base_price": number,
        "market_condition": "hot|balanced|cold",
        "days_on_market": number,
        "property_condition": "excellent|good|fair|poor"
    }
- get_property_tax_estimate: {"price": number, "tax_rate": number}

Rules:
- Call 1-3 tools only.
- Prefer get_market_price first when market context is stale or unknown.
- Call calculate_discount when offer-range guidance is needed.
- Call get_property_tax_estimate to factor in annual holding costs.
- Never invent tools outside the list.
- Output JSON only.
"""
```

### 2. Update `BUYER_SYSTEM_PROMPT` strategy section

Add this line to the strategy bullet list:

```
- Reference property tax estimates to strengthen your negotiation position
```

### No other changes needed

The `call_pricing_mcp()` function is **generic** — it takes any `tool_name` and `arguments` dict and calls them on the pricing server. Since `get_property_tax_estimate` is registered on the same server, it works automatically through the existing MCP client code.

This is the power of the MCP protocol: adding a new tool on the server side requires zero changes to the client transport layer. Only the LLM's prompt needs updating so it knows the tool exists.

## Reflection answer

Letting the LLM decide whether to call the tax tool is better because:
- **Cost**: Calling all tools every round wastes tokens and API budget on data the agent may not need.
- **Relevance**: In early rounds, market price matters most; tax estimates become relevant when fine-tuning a near-final offer.
- **Scalability**: As the tool list grows (5, 10, 20 tools), hardcoding all calls becomes unmanageable. ReAct planning scales naturally.

## Verify
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 2
```
