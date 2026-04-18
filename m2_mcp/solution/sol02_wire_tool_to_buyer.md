# Solution 2: Wire an MCP Tool into the Buyer Agent

## Code changes

### 1. Uncomment the tool (Exercise 1)

In `m2_mcp/pricing_server.py`, search for `Exercise 1` and uncomment the `get_property_tax_estimate` function.

### 2. No discovery code changes needed

The M3 buyer (`m3_adk_multiagents/buyer_adk.py`) connects to the pricing server through ADK's `MCPToolset`, which performs `tools/list` against the server at startup. Once you uncomment `get_property_tax_estimate`, ADK will automatically:

1. Discover the new tool via `tools/list`
2. Add it to the agent's tool catalog
3. Render it into the `{tools_section}` of `BUYER_INSTRUCTION_TEMPLATE`
4. Allow the underlying `LlmAgent` to call it via the standard tool-calling loop

No wiring code in `buyer_adk.py` needs to change.

### 3. No execution handling changes needed

When the model decides to call `get_property_tax_estimate`, ADK runs the MCP `tools/call` against the pricing server (already mapped through the `MCPToolset` connection) and feeds the result back into the conversation — fully automatic.

### 4. Update `BUYER_INSTRUCTION_TEMPLATE` strategy section

In `m3_adk_multiagents/buyer_adk.py`, in `BUYER_INSTRUCTION_TEMPLATE`, add this line to the `YOUR STRATEGY` section (e.g., after `- Use market data to justify EVERY offer`):

```
- Reference property tax estimates to strengthen your negotiation position
```

This nudges GPT-4o to call `get_property_tax_estimate` when reasoning about its next offer.

### No other changes needed

This is the power of MCP combined with ADK's `MCPToolset`: adding a new `@mcp.tool()` on the server side is automatically picked up via `tools/list` at agent startup, surfaced to the model, and routed during execution. No prompt-template plumbing, no dispatch code — fully automatic.

## Reflection answer

Dynamic discovery via `tools/list` has clear advantages:
- **Deployment**: Add a tool to the server, restart it, agents pick it up — no agent code changes.
- **Consistency**: The tool catalog always matches what the server actually offers — no stale hardcoded lists.
- **Scalability**: Works the same whether the server has 2 tools or 20.

The risks to consider:
- **Security**: If a server exposes a dangerous tool, the agent might call it. Trust the servers you connect to, and consider per-tool allowlists / human-in-the-loop callbacks for sensitive operations.
- **Prompt size**: 20+ tool schemas could consume significant context. In production, you might filter or summarize.
- **Determinism**: Adding a tool changes agent behavior without touching agent code — good for agility, risky for auditability.

## Verify
```bash
python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102
python m3_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 2
```
