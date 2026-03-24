# Exercise 2: Wire an MCP Tool into the Buyer Agent `[Core]`

## Goal
After adding `get_property_tax_estimate` in Exercise 1, connect it to the buyer agent so it can factor property tax data into its negotiation strategy. This teaches you how agents **consume** MCP tools — the other side of the protocol.

> **Note — cross-module exercise:** This exercise bridges M2 (MCP servers) and M3 (LangGraph agents). You'll edit files in both `m2_mcp/` and `m3_langgraph_multiagents/`. The MCP tool lives in M2; the agent that consumes it lives in M3.

## What to look for
In `m3_langgraph_multiagents/buyer_simple.py`, the buyer agent uses a two-phase pattern:
1. **Planning phase** (`_plan_mcp_tool_calls`): GPT-4o decides which MCP tools to call
2. **Execution phase** (`call_mcp_server_batch()`): The agent executes those tool calls in a single MCP session

The planner prompt is built **dynamically** — the agent calls `list_tools()` on the MCP server at startup and injects the discovered tool schemas into the prompt. A `_tool_server_map` built during discovery maps each tool name to its originating server, so execution is fully dynamic. Adding a tool to the pricing server is enough — the agent discovers it, the planner can select it, and the dispatch routes it automatically.

## Steps

### Step 1 — Confirm your new tool works
Make sure Exercise 1 is complete and the pricing server starts with your new tool:
```bash
python m2_mcp/pricing_server.py
```

### Step 2 — Verify the tool is auto-discovered
The buyer agent discovers tools dynamically via `list_tools()` at startup. Since you added `get_property_tax_estimate` to the pricing server, the agent will automatically see it in its planner prompt — **no manual prompt editing needed**.

Run the agent and watch for the discovery log:
```
[Buyer] Discovering MCP tools (first call)...
[Buyer] Discovered 3 tools: ['get_market_price', 'calculate_discount', 'get_property_tax_estimate']
```

Since `_gather_mcp_context()` dispatches tool calls dynamically via the `_tool_server_map` (built during discovery), **no code changes are needed** for execution — the new tool is automatically routed to the pricing server.

### Step 3 — Update the system prompt
In `BUYER_SYSTEM_PROMPT`, add a note encouraging the buyer to consider annual tax costs when justifying offers. For example, add to the strategy section:

```
- Reference property tax estimates to strengthen your negotiation position
```

### Step 4 — Test the full system
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 2
```

Watch the buyer agent output. It may or may not call `get_property_tax_estimate` (that's the LLM's choice based on context). The key is that the tool is **available** for the agent to use.

## Verify
- The pricing server starts without errors after Exercise 1
- The buyer agent discovers 3 tools (including `get_property_tax_estimate`) on startup
- If the agent calls `get_property_tax_estimate`, the MCP call succeeds and returns tax data

## Reflection question
> The planner prompt is now built dynamically from `list_tools()`. What are the advantages and risks of auto-discovering tools vs. a hardcoded allowlist? Think about: security (what if a server exposes a dangerous tool), prompt size (20+ tools), and deployment (adding tools without redeploying agents).
