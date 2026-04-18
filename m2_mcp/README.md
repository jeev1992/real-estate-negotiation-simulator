# Module 2 — MCP Servers (`m2_mcp`)

**Requires:** `GITHUB_TOKEN` for the GitHub demo. No API key needed for the pricing/inventory servers standalone.

This module introduces **MCP (Model Context Protocol)** — the standard that lets AI agents call external tools without knowing where the data comes from.

---

## What this module teaches

In Module 1, the negotiation used hardcoded prices (failure mode #8). The agents had no real market data — they just made up numbers.

MCP fixes that. It is a protocol that:
1. Lets a server **expose tools** (functions with typed inputs/outputs)
2. Lets a client **discover** those tools automatically (`list_tools`)
3. Lets a client **call** those tools over a standard interface (`call_tool`)

The agent doesn't need to know if the data comes from a database, an API, or a spreadsheet. It just calls the tool by name.

---

## File breakdown

### `github_agent_client.py` — An LLM agent that uses GitHub via MCP

This file connects to **GitHub's official MCP server** and lets GPT-4o decide which tools to call based on your natural language query.

Why GitHub? Because you already know what GitHub does. Seeing an LLM agent use MCP with a familiar tool makes the protocol click before you write your own servers.

**What it demonstrates:**
- Connecting to an MCP server over `stdio` transport
- Auto-discovering tools via `list_tools` and converting schemas to OpenAI function-calling format
- The LLM **choosing** which tools to call (agentic, not scripted)
- The ReAct-style tool loop: LLM calls tools, gets results, calls more tools or answers
- This is the **same pattern** used by our ADK buyer/seller agents in Module 3 (via `MCPToolset`)

**Prerequisites:**
- Node.js 18+ installed (`node --version`)
- A GitHub Personal Access Token (`repo` or `public_repo` scope)
- An OpenAI API key

```bash
export GITHUB_TOKEN=ghp_your_token_here
export OPENAI_API_KEY=sk-your_key_here
python m2_mcp/github_agent_client.py

# Or with a custom query:
python m2_mcp/github_agent_client.py "Find popular MCP server implementations"
```

---

### `sse_agent_client.py` — SSE agent client (connects over HTTP)

An LLM-powered agent that connects to the pricing and/or inventory servers running in **SSE mode** (HTTP) and lets GPT-4o decide which tools to call — the same agentic pattern as `github_agent_client.py`, just a different transport.

**What it demonstrates:**
- Connecting to MCP servers via SSE (Server-Sent Events) transport
- The LLM **choosing** which tools to call (agentic, not scripted)
- Connecting to multiple MCP servers from a single agent
- Proving the transport is irrelevant — same protocol, same agent loop

**Prerequisites:**
- Start the servers in SSE mode first (in separate terminals)
- An OpenAI API key

```bash
# Terminal 1:
python m2_mcp/pricing_server.py --sse --port 8001

# Terminal 2:
python m2_mcp/inventory_server.py --sse --port 8002

# Terminal 3 — run the agent:
python m2_mcp/sse_agent_client.py                                          # all sample queries
python m2_mcp/sse_agent_client.py "Is this property overpriced?"            # custom query
python m2_mcp/sse_agent_client.py --both "Use inventory and pricing data"   # both servers
```

---

### `pricing_server.py` — Custom MCP server for market pricing

This is the first custom MCP server. It wraps simulated real estate pricing data and exposes it as MCP tools.

**Tools it exposes:**

| Tool | What it does | Who uses it |
|---|---|---|
| `get_market_price(address, property_type)` | Returns comparable sales, estimated value, and market analysis | Both buyer and seller |
| `calculate_discount(base_price, market_condition, days_on_market, property_condition)` | Returns suggested offer ranges and negotiation tips | Both buyer and seller |

**Two transport modes (same server, different usage):**

```bash
# stdio — default, client spawns this as a subprocess (used by Modules 3 + 4)
python m2_mcp/pricing_server.py

# SSE — HTTP server, multiple clients can connect at once
python m2_mcp/pricing_server.py --sse --port 8001
```

In Modules 3 and 4, the agents start this server automatically as a subprocess. You don't need to run it manually — but you *can* to inspect it.

---

### `inventory_server.py` — Custom MCP server for inventory + seller constraints

This server simulates an MLS (Multiple Listing Service) system. It has one public tool and one **seller-only** tool.

**Tools it exposes:**

| Tool | What it does | Who uses it |
|---|---|---|
| `get_inventory_level(zip_code)` | Returns active listings, days on market, market condition | Both buyer and seller |
| `get_minimum_acceptable_price(property_id)` | Returns the seller's absolute floor price | **Seller only** |

**The information asymmetry lesson:**

The buyer agent never connects to `get_minimum_acceptable_price`. This is intentional — in real estate, only the seller's agent knows the seller's walk-away price. The seller uses this tool to set a hard floor; the buyer has to negotiate without knowing it.

This is the same pattern used in real production systems: MCP access control means different agents get different tools.

```bash
# stdio — default
python m2_mcp/inventory_server.py

# SSE
python m2_mcp/inventory_server.py --sse --port 8002
```

---

## MCP in one diagram

```
AGENT                       MCP Protocol              SERVER
─────────────────           ────────────────          ──────────────────
"What tools exist?"
await session.list_tools() ─────────────────────────> Returns tool schemas
                                                       [{name, description,
                                                         inputSchema}]

"Call this tool"
await session.call_tool(    ─────────────────────────> Executes Python fn
  "get_market_price",
  {"address": "742..."}
)
                           <───────────────────────── Returns result dict
"Comps avg $462K,
listing is 4.9% above
market. I'll offer $425K."
```

The agent never imports your Python functions directly. It talks to the server over the protocol — the same way whether the server is local or remote.

---

## How to run

```bash
# GitHub MCP agent (needs GITHUB_TOKEN + OPENAI_API_KEY + Node.js)
export GITHUB_TOKEN=ghp_your_token_here
export OPENAI_API_KEY=sk-your_key_here
python m2_mcp/github_agent_client.py

# Inspect pricing server tools (no API key needed)
python m2_mcp/pricing_server.py
# Then Ctrl+C to stop (it's a server, it waits for connections)

# Inspect inventory server tools (no API key needed)
python m2_mcp/inventory_server.py

# SSE mode — run in one terminal, connect from another
python m2_mcp/pricing_server.py --sse --port 8001
python m2_mcp/inventory_server.py --sse --port 8002

# Then connect with the SSE agent client (in another terminal)
python m2_mcp/sse_agent_client.py                    # all sample queries (pricing only)
python m2_mcp/sse_agent_client.py --both              # includes inventory queries too
```

**What to expect from the GitHub agent:**
- It connects to GitHub's server via `npx`
- Lists all available tools (there are ~20+)
- GPT-4o decides which tools to call based on your query
- Executes the tool calls via MCP and feeds results back
- Produces a natural language summary

**What to expect from the pricing/inventory servers:**
- They start and wait for a client to connect
- On their own they don't print much — they're servers
- In Modules 3 and 4, the agents connect to them automatically

---

## Deep-dive demos (`m2_mcp/demos/`)

Standalone, runnable scripts that crack open the MCP protocol so you can see what's happening on the wire. Each one is self-contained and prints what it sends/receives. Read them in order; companion notes live in [m2_mcp/notes/mcp_deep_dive.md](m2_mcp/notes/mcp_deep_dive.md).

| Demo | What it shows | Run |
|---|---|---|
| [`01_initialize_handshake.py`](m2_mcp/demos/01_initialize_handshake.py) | Raw JSON-RPC frames of the MCP `initialize` handshake (no SDK) — capability negotiation, `notifications/initialized`, then `tools/list` | `python m2_mcp/demos/01_initialize_handshake.py` |
| [`02_tool_loop_trace.py`](m2_mcp/demos/02_tool_loop_trace.py) | The full **model ↔ host ↔ server** tool-calling loop, narrated step by step with timestamps (uses the `mcp` SDK + OpenAI function calling) | `python m2_mcp/demos/02_tool_loop_trace.py` |
| [`03_list_all_primitives.py`](m2_mcp/demos/03_list_all_primitives.py) | Lists **Tools, Resources, and Prompts** from both workshop servers — proves MCP carries more than just tools | `python m2_mcp/demos/03_list_all_primitives.py` |
| [`04_content_types.py`](m2_mcp/demos/04_content_types.py) | A tiny inline server that returns each `Content` block kind (text / image / embedded resource) so you can see the JSON shape of each | `python m2_mcp/demos/04_content_types.py` |
| [`05_streamable_http_transport.py`](m2_mcp/demos/05_streamable_http_transport.py) | Same MCP protocol, **Streamable HTTP** transport (the spec's recommended replacement for raw SSE) | Server: `python m2_mcp/demos/05_streamable_http_transport.py --serve --port 8765`<br>Client: `python m2_mcp/demos/05_streamable_http_transport.py --client --port 8765` |

> Demos 01–04 spawn their own server subprocess — no manual setup. Only demo 05 needs two terminals.

---

## Exercises

| Exercise | Difficulty | Task |
|---|---|---|
| `ex01_add_mcp_tool.md` | `[Starter]` | Add a `get_property_tax_estimate` tool to the pricing server using `@mcp.tool()` |
| `ex02_wire_tool_to_buyer.md` | `[Core]` | Wire the new tool into the buyer agent and verify it's auto-discovered via `list_tools()` |

Solutions are in `m2_mcp/solution/`. Each exercise includes a reflection question.

---

## Quick mental model
- If you want to see *how to build* an MCP server, read `pricing_server.py` (simpler, 2 tools) then `inventory_server.py` (adds the seller-only tool).
- The `@mcp.tool()` decorator is all you need to expose a Python function as an MCP tool.
- In Modules 3 and 4, both agents use these servers — you don't need to start them manually.
