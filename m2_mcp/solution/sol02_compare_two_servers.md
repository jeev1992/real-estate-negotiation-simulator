# Solution 2: Wire an MCP Tool into the Buyer Agent

## Code changes

### 1. No planner prompt changes needed

The buyer agent discovers tools **dynamically** via `list_tools()` at startup. Since you added `get_property_tax_estimate` to the pricing server (Exercise 1), the agent will automatically see it — the planner prompt is built from the server's live tool schemas.

You can verify by watching the startup log:
```
[Buyer] Discovering MCP tools (first call)...
[Buyer] Discovered 3 tools: ['get_market_price', 'calculate_discount', 'get_property_tax_estimate']
```

### 2. No execution handling changes needed

`_gather_mcp_context()` dispatches tool calls dynamically using the `_tool_server_map` built during discovery. Since `get_property_tax_estimate` is on the pricing server (already mapped), it is automatically routed — no `elif` branch needed.

The flow is:
1. `_ensure_tools_discovered()` calls `list_tools()` on the pricing server
2. It finds `get_property_tax_estimate` and maps it: `_tool_server_map["get_property_tax_estimate"] = PRICING_SERVER_PATH`
3. When the planner selects it, `_gather_mcp_context()` looks up the server path and calls it via `call_mcp_server_batch()`

### 3. Update `BUYER_SYSTEM_PROMPT` strategy section

Add this line to the strategy bullet list:

```
- Reference property tax estimates to strengthen your negotiation position
```

### No other changes needed

The `call_mcp_server_batch()` function is **generic** — it opens one MCP session per server and executes all planned calls through it. Since `get_property_tax_estimate` is registered on the pricing server (already in `_tool_server_map`), it works automatically with zero code changes.

This is the power of MCP's dynamic discovery combined with dynamic dispatch: adding a new `@mcp.tool()` on the server side is automatically picked up by the agent's `list_tools()` call at startup, mapped to the right server, and routed during execution. No prompt editing, no dispatch code — fully automatic.

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
