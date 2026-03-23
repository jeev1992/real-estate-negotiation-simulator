# Solution 2: Wire an MCP Tool into the Buyer Agent

## Code changes

### 1. No planner prompt changes needed

The buyer agent discovers tools **dynamically** via `list_tools()` at startup. Since you added `get_property_tax_estimate` to the pricing server (Exercise 1), the agent will automatically see it — the planner prompt is built from the server's live tool schemas.

You can verify by watching the startup log:
```
[Buyer] Discovering MCP tools (first call)...
[Buyer] Discovered 3 tools: ['get_market_price', 'calculate_discount', 'get_property_tax_estimate']
```

### 2. Add execution handling in `_gather_mcp_context()`

In `buyer_simple.py`, add a new `elif` branch to handle the tool call:

```python
elif tool == "get_property_tax_estimate":
    args = {
        "price": float(arguments.get("price", LISTING_PRICE)),
        "tax_rate": float(arguments.get("tax_rate", 0.02)),
    }
    print("   [Buyer] Calling MCP: get_property_tax_estimate...")
    tax_data = await call_pricing_mcp("get_property_tax_estimate", args)
```

### 3. Update `BUYER_SYSTEM_PROMPT` strategy section

Add this line to the strategy bullet list:

```
- Reference property tax estimates to strengthen your negotiation position
```

### No other changes needed

The `call_pricing_mcp()` function is **generic** — it takes any `tool_name` and `arguments` dict and calls them on the pricing server. Since `get_property_tax_estimate` is registered on the same server, it works automatically through the existing MCP client code.

This is the power of MCP's dynamic discovery: adding a new `@mcp.tool()` on the server side is automatically picked up by the agent's `list_tools()` call at startup. No prompt editing needed — the planner prompt is built from live schemas.

## Reflection answer

Dynamic discovery via `list_tools()` has clear advantages:
- **Deployment**: Add a tool to the server, restart it, agents pick it up — no agent code changes.
- **Consistency**: The prompt always matches what the server actually offers — no stale hardcoded lists.
- **Scalability**: Works the same whether the server has 2 tools or 20.

The risks to consider:
- **Security**: If a server exposes a dangerous tool, the agent might call it. The allowlist in `_plan_mcp_tool_calls` (built from `list_tools()` results) mitigates this — but only if you trust the servers you connect to.
- **Prompt size**: 20+ tool schemas could consume significant context. In production, you might filter or summarize.
- **Determinism**: Adding a tool changes agent behavior without touching agent code — good for agility, risky for auditability.

## Verify
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 2
```
