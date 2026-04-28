# Exercise 2: Wire an MCP Tool into the Buyer Agent `[Core]`

## Goal
After adding `get_property_tax_estimate` in Exercise 1, connect it to the buyer agent so it can factor property tax data into its negotiation strategy. This teaches you how agents **consume** MCP tools — the other side of the protocol.

> **Note — cross-module exercise:** This exercise bridges M2 (MCP servers) and M3 (ADK buyer agent). You'll edit files in both `m2_mcp/` and `m3_adk_multiagents/`. The MCP tool lives in M2; the agent that consumes it lives in M3.

## What to look for
In `m3_adk_multiagents/negotiation_agents/buyer_agent/agent.py`, the buyer is a declarative `LlmAgent` that connects to the pricing MCP server through ADK's `MCPToolset`:

```python
root_agent = LlmAgent(
    name="buyer_agent",
    model="openai/gpt-4o",
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                )
            )
        )
    ],
)
```

`MCPToolset` performs `tools/list` against the pricing server at startup and exposes every discovered tool to the `LlmAgent` as a function-calling tool. The model decides when to call which tool; ADK runs the MCP `tools/call` and feeds the result back into the conversation — fully automatic.

Adding a new `@mcp.tool()` to the pricing server is therefore enough — ADK will pick it up on the next start and surface it to the model.

## Steps

### Step 1 — Confirm your new tool works
Make sure Exercise 1 is complete and the pricing server starts with your new tool:
```bash
python m2_mcp/pricing_server.py
```

### Step 2 — Verify the tool is auto-discovered
No wiring code needs to change. `MCPToolset` calls `tools/list` against the pricing server when the buyer agent starts, so `get_property_tax_estimate` is automatically discovered and available.

### Step 3 — Nudge the model to use it
In `m3_adk_multiagents/negotiation_agents/buyer_agent/agent.py`, add this to the `instruction` string in the STRATEGY section:

```
- Reference property tax estimates to strengthen your negotiation position
```

This nudges GPT-4o (via ADK) to call `get_property_tax_estimate` when reasoning about its next offer.

### Step 4 — Test the full system
Run the buyer agent via `adk web`:
```bash
adk web m3_adk_multiagents/negotiation_agents/
```

Pick `buyer_agent` from the dropdown. Ask it about 742 Evergreen Terrace. Watch whether it calls `get_property_tax_estimate` — the tool should appear in the tool call traces in the web UI.

## Verify
- The pricing server starts without errors after Exercise 1
- The buyer agent boots without errors and lists `get_property_tax_estimate` among its tools
- If the agent calls `get_property_tax_estimate`, the MCP `tools/call` succeeds and returns tax data

## Reflection question
> The buyer's tool catalog is built dynamically from `tools/list`. What are the advantages and risks of auto-discovering tools vs. a hardcoded allowlist? Think about: security (what if a server exposes a dangerous tool), prompt size (20+ tools), and deployment (adding tools without redeploying agents).
