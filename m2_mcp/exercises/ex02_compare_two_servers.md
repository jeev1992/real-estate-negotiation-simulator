# Exercise 2: Wire an MCP Tool into the Buyer Agent `[Core]`

## Goal
After adding `get_property_tax_estimate` in Exercise 1, connect it to the buyer agent so it can factor property tax data into its negotiation strategy. This teaches you how agents **consume** MCP tools — the other side of the protocol.

## What to look for
In `m3_langgraph_multiagents/buyer_simple.py`, the buyer agent uses a two-phase pattern:
1. **Planning phase** (`BUYER_MCP_PLANNER_PROMPT`): GPT-4o decides which MCP tools to call
2. **Execution phase** (`call_pricing_mcp()`): The agent executes those tool calls

You need to update both phases so the LLM knows the new tool exists and can choose to call it.

## Steps

### Step 1 — Confirm your new tool works
Make sure Exercise 1 is complete and the pricing server starts with your new tool:
```bash
python m2_mcp/pricing_server.py
```

### Step 2 — Update the planner prompt
In `m3_langgraph_multiagents/buyer_simple.py`, find `BUYER_MCP_PLANNER_PROMPT` and add the new tool to the available tools list:

```python
- get_property_tax_estimate: {"price": number, "tax_rate": number (optional, default 0.02)}
```

Add it after the existing `calculate_discount` entry.

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
- The buyer agent runs without errors with the updated planner prompt
- If the agent calls `get_property_tax_estimate`, the MCP call succeeds and returns tax data

## Reflection question
> Why is it better to let the LLM decide whether to call the tax tool (ReAct-style planning) rather than hardcoding it to always call all three tools? Think about: token cost, relevance, and what happens as the tool list grows.
