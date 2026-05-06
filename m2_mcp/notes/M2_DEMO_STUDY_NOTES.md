# Module 2 — Demo Walkthrough & Concept Notes

Personal study notes captured while running each demo hands-on.

---

## Demo 01 — MCP Initialize Handshake (`demos/01_initialize_handshake.py`)

### What it teaches
The raw JSON-RPC frames that make up the MCP handshake. No SDK, no abstraction — you see exactly what the protocol sends and receives.

### How to run
```bash
python m2_mcp/demos/01_initialize_handshake.py   # no API key needed
```

### Actual output (5 frames)

**Frame 1 — client → server: `initialize`**
```json
{
  "jsonrpc": "2.0", "id": 1, "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "demo-client", "version": "0.1"}
  }
}
```
Client announces itself. `protocolVersion` is the MCP spec version. `capabilities` is empty — this raw client doesn't support any advanced features.

**Frame 2 — server → client: `initialize` result**
```json
{
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {"listChanged": false},
      "prompts": {"listChanged": false},
      "resources": {"subscribe": false, "listChanged": false}
    },
    "serverInfo": {"name": "real-estate-pricing", "version": "1.27.0"}
  }
}
```
Server confirms same protocol version. Reports what it supports: tools ✓, prompts ✓, resources ✓. `listChanged: false` means the server won't notify if tools change at runtime.

**Frame 3 — client → server: `notifications/initialized`**
```json
{"jsonrpc": "2.0", "method": "notifications/initialized"}
```
Client confirms it's ready. This is a notification (no `id` field) — the server doesn't respond.

**Frame 4 — client → server: `tools/list`**
```json
{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
```

**Frame 5 — server → client: `tools/list` result (2 tools)**
Returns full JSON Schema for each tool:
- `get_market_price` — required: `address` (string), optional: `property_type` (string, default "single_family")
- `calculate_discount` — required: `base_price` (number), optional: `market_condition` (enum: hot/balanced/cold), `days_on_market` (int), `property_condition` (enum: excellent/good/fair/poor)

### Key observations

1. **JSON-RPC is the wire format.** Every frame has `jsonrpc: "2.0"`, an `id` (for requests), and `method`. This is the same JSON-RPC used by A2A in M3.

2. **5 frames total.** The minimal handshake is: initialize → result → initialized → tools/list → result. After this, the client can call any tool.

3. **JSON Schema from type hints.** The `inputSchema` for `calculate_discount` has `enum: ["hot", "balanced", "cold"]` — generated automatically from Python's `Literal["hot", "balanced", "cold"]` type hint. No manual schema writing.

4. **Capabilities are negotiated.** The server says what it supports (tools, prompts, resources). A server with only tools would return `{"tools": {}}` and omit prompts/resources.

### Key teaching points for class

1. **"This is the raw wire."** Students see the exact JSON-RPC frames before any SDK wraps them. Knowing the protocol makes debugging easier.
2. **"5 frames — that's the whole handshake."** initialize → result → initialized → tools/list → result. Everything after this is just `tools/call`.
3. **"Type hints become JSON Schema."** `Literal["hot", "balanced", "cold"]` in Python → `enum` in the schema. Docstrings → `description`. No manual schema authoring.
4. **"Compare to A2A in M3."** The same JSON-RPC `2.0` wire format is used by A2A's `message/send`. Students who understand MCP frames will recognize A2A frames instantly.

---

## Demo 02 — Tool Loop Trace (`demos/02_tool_loop_trace.py`)

### What it teaches
The full model ↔ host ↔ server tool-calling loop with timestamps. Shows the three actors (Model, Host, Server) and their roles.

### How to run
```bash
python m2_mcp/demos/02_tool_loop_trace.py   # requires OPENAI_API_KEY
```

### Actual output

```
[t= 0.00s] HOST    connecting to MCP server (stdio subprocess)
[t= 3.18s] HOST    tools/list
[t= 3.19s] SERVER  returned 2 tools
[t= 3.67s] MODEL   receiving prompt + tool catalog
[t= 6.77s] MODEL   emitted tool_use(get_market_price)
[t= 6.77s] HOST    translating tool_use -> tools/call
[t= 6.77s] SERVER  returned CallToolResult
[t= 6.77s] HOST    injecting tool_result back into model context
[t=10.42s] MODEL   emitted final assistant text
```

**Final answer:**
> The estimated market value is $462,000. Listed at $485,000 (4.7% above comps). Fair offer range: $449,473–$477,276. 4BR/3BA, 2400 sqft, 18 DOM. Recent upgrades: kitchen ($45K), roof ($18K), HVAC ($12K).

### Three actors, clear roles

| Actor | What it does | Time spent |
|-------|-------------|------------|
| **HOST** (your Python code) | Connects to server, translates between OpenAI ↔ MCP formats | ~3.7s (startup + handshake) |
| **MODEL** (GPT-4o) | Reads query + tool schemas, decides to call `get_market_price`, produces final answer | ~6.7s (two LLM calls) |
| **SERVER** (pricing_server.py) | Executes `get_market_price`, returns structured data | <0.01s (instant — simulated data) |

### Key observations

1. **3.18s for server startup.** The stdio subprocess takes ~3s to initialize (Python import time). In production with remote servers, this is a one-time connection cost.

2. **The model made TWO calls.** First call (t=3.67→6.77): model decided to call `get_market_price`. Second call (t=6.77→10.42): model reasoned about the result and produced the final answer.

3. **The host is the bridge.** It converts OpenAI's `tool_calls` format to MCP's `tools/call` format and back. In M3, ADK's `MCPToolset` does this automatically.

4. **This is the exact loop ADK replaces.** `github_agent_client.py` and `sse_agent_client.py` both have ~60 lines implementing this loop. M3's `tools=[MCPToolset(...)]` replaces all of it.

### Key teaching points for class

1. **"Three actors, three roles."** Model (decides which tools to call), Host (translates between OpenAI and MCP formats), Server (executes tools). This trio is the universal pattern.
2. **"The model made TWO LLM calls."** One to decide which tool to call, one to reason about the result. Students should see the timestamps to understand the cost.
3. **"The host is what ADK replaces."** In M3, `MCPToolset` IS the host — it does the OpenAI ↔ MCP translation automatically. Understanding this loop means understanding what ADK does under the hood.
4. **"Server startup is the bottleneck."** ~3s for the Python subprocess. In production with remote servers, this is a one-time connection cost paid at startup, not per-request.

### Questions to try

| # | Query | Expected behavior | What it teaches |
|---|-------|-------------------|----------------|
| 1 | "What is 742 Evergreen Terrace worth?" | `get_market_price` → rich data with comps, estimated value, market conditions | Full tool loop with timestamps |
| 2 | "What's the weather?" | No tool call — LLM answers from knowledge | The model decides WHEN to call tools |

---

## Demo 03 — List All Primitives (`demos/03_list_all_primitives.py`)

### What it teaches
MCP servers can expose more than just tools — they also have Resources and Prompts.

### How to run
```bash
python m2_mcp/demos/03_list_all_primitives.py   # no API key needed
```

### Actual output

```
=== PRICING SERVER (pricing_server.py) ===
server caps: tools=True resources=True prompts=True

[tools] 2
  - get_market_price
  - calculate_discount

[resources] 0

[prompts] 1
  - negotiation-tactics: Tactical guidance string for a buyer or seller in a given market.

=== INVENTORY SERVER (inventory_server.py) ===
server caps: tools=True resources=True prompts=True

[tools] 2
  - get_inventory_level
  - get_minimum_acceptable_price

[resources] 1
  - inventory://floor-prices :: floor_prices_resource

[prompts] 0
```

### The four MCP primitives

| Primitive | Direction | Pricing server | Inventory server |
|-----------|-----------|---------------|-----------------|
| **Tools** | Client → Server (invoke) | 2 tools | 2 tools |
| **Resources** | Client → Server (read) | 0 | 1 (`floor_prices`) |
| **Prompts** | Client → Server (expand) | 1 (`negotiation-tactics`) | 0 |
| **Sampling** | Server → Client (LLM call) | Not used | Not used |

### Key observations

1. **Pricing server has tools + prompts, no resources.** The `negotiation-tactics` prompt is a reusable template the host can render into the conversation.
2. **Inventory server has tools + resources, no prompts.** The `inventory://floor-prices` resource is readable data (like a file), not a callable function.
3. **Both report all three capability flags as True.** Even if a server has 0 resources, it still advertises `resources=True` capability — meaning it supports the primitive, not that it has items.
4. **Capabilities ≠ count.** A capability being `True` means the server supports `list_resources()` calls. Having 0 resources is valid.

### Key teaching points for class

1. **"Tools are 90% of MCP usage."** Most integrations only use tools. Resources and prompts are bonus capabilities, not requirements.
2. **"Resources are like files, prompts are like templates."** Resources: read-only data the agent can pull. Prompts: parameterized text the host can expand.
3. **"Sampling is the fourth primitive."** It lets the server ask the LLM to generate text. We don't demo it because our hosts aren't sampling-capable, but students should know it exists.
4. **"Both servers in one script."** Show how the `inspect()` function connects to each server independently — the client doesn't care how many servers exist.

### Questions to try

| # | What to observe | Expected | What it teaches |
|---|----------------|----------|----------------|
| 1 | Count tools per server | Pricing: 2, Inventory: 2 | Tool distribution across servers |
| 2 | Which server has the resource? | Inventory: `inventory://floor-prices` | Resources are data, not functions |
| 3 | Which server has the prompt? | Pricing: `negotiation-tactics` | Prompts are templates, not tools |

---

## Demo 04 — Content Types (`demos/04_content_types.py`)

### What it teaches
Tool results can return different content block types — not just text.

### How to run
```bash
python m2_mcp/demos/04_content_types.py   # no API key needed
```

### Actual output

```
=== get_text ===
  type=text
  text='hello as plain text'

=== get_image ===
  type=image
  mimeType=image/png  data_len=92 (base64)

=== get_resource ===
  type=resource
  uri=demo://greeting.txt  mimeType=text/plain  text='hello from an embedded resource'
```

### Three content block types

| Type | JSON shape | When to use |
|------|-----------|-------------|
| **TextContent** | `{"type": "text", "text": "..."}` | Most common — tool results |
| **ImageContent** | `{"type": "image", "data": "base64...", "mimeType": "..."}` | Charts, screenshots |
| **EmbeddedResource** | `{"type": "resource", "resource": {"uri": "...", "text": "..."}}` | References to stored data |

### Key observations

1. **Self-contained demo server.** The script writes a temporary inline MCP server to disk, spawns it, then cleans up. No external dependencies.
2. **ImageContent carries base64.** The 1×1 transparent PNG is 92 bytes of base64. In production, a charting tool might return a full histogram.
3. **EmbeddedResource has a URI.** `demo://greeting.txt` — the resource is identified by URI, meaning the client could fetch it independently later. Unlike TextContent (ephemeral), resources have identity.
4. **Most tools return TextContent.** This demo exists to show the OTHER types. In our workshop, `get_market_price` returns TextContent wrapping a JSON string.

### Key teaching points for class

1. **"Three content types, one result."** A single `CallToolResult` can carry multiple content blocks of different types — text, image, and resource in the same response.
2. **"TextContent is the default."** When `@mcp.tool()` returns a string or dict, FastMCP wraps it in TextContent automatically. You only use ImageContent/EmbeddedResource when you need them.
3. **"This maps to A2A Parts in M3."** MCP has TextContent/ImageContent/EmbeddedResource. A2A has TextPart/DataPart/FilePart. Different names, same idea — typed content blocks.

### Questions to try

| # | What to observe | Expected | What it teaches |
|---|----------------|----------|----------------|
| 1 | Run the script | 3 tool calls, 3 different content types | Content type variety |
| 2 | Check `data_len` for image | 92 bytes (tiny 1×1 PNG) | Images are base64-encoded |
| 3 | Check `uri` for resource | `demo://greeting.txt` | Resources have identity |

---

## github_agent_client.py — The Agentic MCP Client

### What it teaches
A full LLM-powered agent that connects to GitHub's MCP server and lets GPT-4o decide which tools to call. This is the same ReAct-style tool loop used by the buyer/seller agents in M3.

### How to run
```bash
python m2_mcp/github_agent_client.py "Find popular MCP server implementations"
# requires OPENAI_API_KEY + GITHUB_TOKEN + Node.js
```

### The agentic loop pattern

```python
# 1. Connect + discover
tools = await session.list_tools()
openai_tools = mcp_tools_to_openai_functions(tools)

# 2. Agent loop — LLM decides what to call
for iteration in range(max_iterations):
    response = await openai.create(messages=messages, tools=openai_tools)
    if response.tool_calls:
        for call in response.tool_calls:
            result = await session.call_tool(call.name, call.args)
            messages.append({"role": "tool", "content": result})
    else:
        return response.content  # done
```

### Key insight
This is the **manual version** of what ADK's `MCPToolset` automates. Understanding this loop means understanding what ADK does under the hood.

---

## MCP Servers — pricing_server.py & inventory_server.py

### Tool design principle

> **"Group tools around intent, not endpoints."** Fewer, well-described tools consistently outperform exhaustive API mirrors. A single `create_issue_from_thread` tool beats `get_thread` + `parse_messages` + `create_issue` + `link_attachment`.
> — [Building agents that reach production systems with MCP](https://claude.com/blog/building-agents-that-reach-production-systems-with-mcp)

Our servers follow this principle:
- `get_market_price` returns comps + estimated value + market conditions + negotiation context in ONE call
- NOT: separate tools for `get_comps`, `get_sqft_price`, `get_dom`, `get_appreciation_rate`

### Information asymmetry — the floor price moved

| Module | Where the floor price lives | Who can see it |
|--------|---------------------------|----------------|
| M1 | `SELLER_MIN_PRICE = 445_000` (Python constant) | Everyone reading source |
| M2 | `get_minimum_acceptable_price()` (MCP server) | Anyone who calls the tool |
| M3 | Same MCP tool + `before_tool_callback` allowlist | **Seller only** |

---

## Production patterns from the Anthropic article

Key insights from [Building agents that reach production systems with MCP](https://claude.com/blog/building-agents-that-reach-production-systems-with-mcp):

1. **Three paths: API → CLI → MCP.** Direct APIs work for one agent × one service. CLIs work locally. MCP provides the portable, standardized layer for cloud-hosted agents. Production teams converge on MCP.

2. **Build remote servers for maximum reach.** A remote server (HTTP) runs across web, mobile, and cloud-hosted agents. stdio is great for development; remote is what ships.

3. **Group tools around intent, not endpoints.** Our `get_market_price` is a good example — one call returns everything the agent needs. Avoid mirroring REST endpoints 1:1 into MCP tools.

4. **Skills + MCP are complementary.** MCP gives agents access to tools and data. Skills teach the agent *how* to use those tools. In M3, the agent's `instruction` is the skill — it tells the LLM when and how to call MCP tools.

5. **MCP compounds.** As more clients adopt the spec, the same server gets more capable without shipping anything new. 300M+ SDK downloads/month proves the ecosystem is real.

---

## Connection to the rest of the workshop

### M1 → M2: Hardcoded → Server-side

| M1 Problem | M2 Solution |
|------------|-------------|
| `SELLER_MIN_PRICE = 445_000` | `get_minimum_acceptable_price()` from MCP server |
| No market data | `get_market_price()` + `calculate_discount()` |
| Prices visible in source | Server returns data at runtime |

### M2 → M3: Manual loop → ADK declaration

| M2 (manual) | M3 (ADK) |
|-------------|----------|
| 60-line tool loop in `github_agent_client.py` | `tools=[MCPToolset(...)]` |
| `mcp_tools_to_openai_functions()` conversion | ADK does it automatically |
| `session.call_tool()` + message append | ADK handles the tool loop |
| `max_iterations` in Python loop | `max_iterations` in LoopAgent |

---

## Key teaching points for class

1. **"Run Demo 01 to see the wire."** The handshake is 5 JSON-RPC frames. Students should see raw frames before using the SDK.

2. **"Demo 02 shows the three actors."** Model (decides), Host (bridges), Server (executes). The host is what MCPToolset replaces.

3. **"Group tools around intent."** Show the Anthropic article quote. Our `get_market_price` returns everything in one call.

4. **"The floor price moved."** M1: Python constant. M2: MCP tool. M3: allowlist-protected MCP tool. Same data, increasingly better architecture.

5. **"M2 is the manual version of M3."** Understanding this loop means understanding what ADK does under the hood.

6. **"Build remote servers for maximum reach."** stdio for dev, HTTP for production. The protocol is the same.

---

## Demo 05 — Streamable HTTP Transport (`demos/05_streamable_http_transport.py`)

**File:** `m2_mcp/demos/05_streamable_http_transport.py` (~70 lines)

### What it teaches
MCP works over HTTP too — not just stdio pipes. This demo runs the same protocol over "Streamable HTTP," the spec's recommended replacement for raw SSE. Same `list_tools` + `call_tool`, different transport.

### How to run
```bash
# Terminal 1: start the server
python m2_mcp/demos/05_streamable_http_transport.py --serve --port 8765

# Terminal 2: run the client
python m2_mcp/demos/05_streamable_http_transport.py --client --port 8765
```

### Expected output

**Server terminal:**
```
Serving MCP on http://127.0.0.1:8765/mcp
```

**Client terminal:**
```
Connecting client to http://127.0.0.1:8765/mcp
discovered tools: ['echo']
response: echo: hello over HTTP
```

### Key code elements

**Server (5 lines of tool code):**
```python
mcp = FastMCP("http-transport-demo")

@mcp.tool()
def echo(text: str) -> str:
    """Echo back the supplied text."""
    return f"echo: {text}"

mcp.run(transport="streamable-http")
```

**Client (uses `streamablehttp_client` instead of `stdio_client`):**
```python
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(url) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("echo", {"text": "hello over HTTP"})
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **Streamable HTTP** | The MCP spec's recommended HTTP transport. Uses `POST /mcp` with JSON-RPC, supports streaming responses. Successor to raw SSE |
| **`mcp.run(transport="streamable-http")`** | One-line transport switch. Same server code, different wire format |
| **`streamablehttp_client`** | The client-side counterpart. Same `ClientSession` API as stdio — `list_tools()`, `call_tool()` work identically |
| **Separate processes** | Unlike stdio (where client spawns server), here they're independent processes. Server lives beyond client disconnection |

### Key observations

1. **Same API, different wire.** `session.list_tools()` and `session.call_tool()` are identical to Demo 01's stdio calls. Only the connection setup changed.

2. **The server is an HTTP endpoint.** It runs at `http://127.0.0.1:8765/mcp`. Any MCP client — not just Python — can connect. A TypeScript agent, a Go agent, or curl could all call this endpoint.

3. **The echo tool is trivial on purpose.** The point isn't the tool logic — it's proving the transport works. The tool could be `get_market_price` (just change the import) and it would work identically.

4. **Independent lifecycle.** The server keeps running after the client disconnects. In stdio mode, the server dies when the client exits. This is the production advantage of HTTP-based transports.

### d01 vs d05 — the transport comparison

| | Demo 01 (stdio) | Demo 05 (Streamable HTTP) |
|---|---|---|
| **Connection** | `stdio_client(params)` | `streamablehttp_client(url)` |
| **Server lifecycle** | Subprocess — dies when client exits | Independent process — lives forever |
| **Client count** | 1:1 (one client per server) | Many:1 (multiple clients, one server) |
| **Protocol calls** | `session.list_tools()`, `session.call_tool()` | Identical |
| **Use case** | Local development, ADK `MCPToolset` | Production, remote agents |

### Key teaching points for class

1. **"Same protocol, different transport."** The JSON-RPC messages are identical. Only the delivery mechanism changes (pipe vs HTTP).
2. **"This is the production path."** stdio is for development (one client, local). Streamable HTTP is for production (many clients, remote). Anthropic's guidance: "Build remote servers for maximum reach."
3. **"Compare to Demo 01."** The `list_tools()` call returns the same structure. The `call_tool()` call returns the same structure. The student should see that transport is pluggable.
4. **"SSE is the legacy HTTP transport."** Streamable HTTP is the spec's recommended successor. Our `sse_agent_client.py` uses SSE (still widely supported). Demo 05 uses the newer Streamable HTTP.

### Questions to try

| # | Action | Expected | What it teaches |
|---|--------|----------|----------------|
| 1 | Run server, then client | `discovered tools: ['echo']`, `response: echo: hello over HTTP` | Streamable HTTP transport works |
| 2 | Run client without server | Connection refused error | Client and server are independent processes |
| 3 | Run client twice (server still running) | Same output both times | Server survives client disconnection |

---

## sse_agent_client.py — SSE Transport + Agentic Loop

**File:** `m2_mcp/sse_agent_client.py` (~350 lines)

### What it teaches
The same agentic tool loop as `github_agent_client.py`, but connecting to our real estate MCP servers over SSE (HTTP) instead of stdio. Proves the agent code is transport-agnostic — only the connection setup changes.

### How to run
```bash
# Terminal 1: start pricing server in SSE mode
python m2_mcp/pricing_server.py --sse --port 8001

# Terminal 2 (optional): start inventory server in SSE mode
python m2_mcp/inventory_server.py --sse --port 8002

# Terminal 3: run the agent
python m2_mcp/sse_agent_client.py "What is 742 Evergreen Terrace worth?"

# With both servers (pricing + inventory):
python m2_mcp/sse_agent_client.py --both "What's the seller's minimum price?"
```

### Expected output (single server)

```
=================================================================
SSE MCP AGENT
An LLM that decides which real estate tools to call over HTTP
=================================================================

[Agent] Query: What is 742 Evergreen Terrace worth?

[Agent] Connected to Pricing Server (http://localhost:8001/sse)
[Agent] Discovered 2 tools:
         - get_market_price
         - calculate_discount

[Agent] Iteration 1: calling GPT-4o...
[Agent]   -> Calling: get_market_price({"address": "742 Evergreen Terrace, Austin, TX 78701"})

[Agent] Iteration 2: calling GPT-4o...

=================================================================
AGENT ANSWER
=================================================================

The estimated market value for 742 Evergreen Terrace is $462,000.
The property is listed at $485,000 (4.7% above comps).
Fair offer range: $449,473–$477,276.
```

### Expected output (both servers, `--both`)

```
[Agent] Connected to Pricing Server (http://localhost:8001/sse)
[Agent] Discovered 2 tools:
         - get_market_price
         - calculate_discount

[Agent] Connected to Inventory Server (http://localhost:8002/sse)
[Agent] Discovered 2 tools:
         - get_inventory_level
         - get_minimum_acceptable_price

[Agent] Iteration 1: calling GPT-4o...
[Agent]   -> Calling: get_market_price({"address": "742 Evergreen Terrace..."})
[Agent]   -> Calling: get_minimum_acceptable_price({"property_id": "742-evergreen-austin-78701"})
[Agent]   -> Calling: get_inventory_level({"zip_code": "78701"})

[Agent] Iteration 2: calling GPT-4o...

=================================================================
AGENT ANSWER
=================================================================

Based on all available data:
- Market value: $462,000 (listed at $485,000)
- Seller's minimum: $445,000
- Market condition: balanced (3.1 months inventory)
- Recommendation: Offer $445,000–$462,000. The seller needs at least $445K.
```

### The agentic loop (same pattern as github_agent_client.py)

```python
# 1. Connect to SSE servers + discover tools
async with sse_client(pricing_url) as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        tools = await session.list_tools()

# 2. Agent loop — LLM decides what to call
for iteration in range(1, max_iterations + 1):
    response = await openai.create(messages=messages, tools=openai_tools)
    if choice.finish_reason == "tool_calls":
        for tool_call in choice.message.tool_calls:
            # Reconnect to the right server and call the tool
            async with sse_client(url) as (rs, ws):
                async with ClientSession(rs, ws) as sess:
                    await sess.initialize()
                    result = await sess.call_tool(fn_name, fn_args)
    else:
        return choice.message.content  # done
```

### github_agent_client.py vs sse_agent_client.py

| | github_agent_client.py | sse_agent_client.py |
|---|---|---|
| **Transport** | stdio (subprocess) | SSE (HTTP endpoint) |
| **Server** | GitHub's MCP server (`npx @modelcontextprotocol/server-github`) | Our `pricing_server.py` + `inventory_server.py` |
| **Connection** | `stdio_client(params)` | `sse_client(url)` |
| **Multi-server** | No (single GitHub server) | Yes (`--both` connects to pricing + inventory) |
| **Tool loop** | Identical | Identical |
| **LLM calls** | GPT-4o | GPT-4o |

### Key observations

1. **The agent loop is identical.** Both clients use the same `for iteration in range(max_iterations)` → call LLM → check for tool_calls → execute via MCP → feed back. Only the connection setup differs.

2. **Multi-server support.** With `--both`, the agent discovers tools from TWO servers and merges them into one unified tool list for the LLM. The LLM doesn't know (or care) which server hosts which tool.

3. **SSE reconnects per tool call.** Unlike stdio (persistent pipe), SSE clients reconnect for each `call_tool`. This is because SSE connections are stateless at the transport level — the session is the MCP-level concept, not the HTTP connection.

4. **Same tool results as Demo 02.** The agent gets the same market price data ($462K), same comps, same negotiation tips. The transport changed; the data didn't.

5. **`--both` reveals the information asymmetry.** When connected to both servers, the agent can see `get_minimum_acceptable_price` ($445K floor). In M3, the buyer's allowlist blocks this tool — but here, no restrictions. This is the setup step for M3's allowlist callbacks.

### Key teaching points for class

1. **"The loop is the same."** Side-by-side the `github_agent_client.py` and `sse_agent_client.py` tool loops. The only difference is `stdio_client` vs `sse_client`.
2. **"`--both` connects to two servers."** The LLM sees 4 tools from 2 servers as one unified set. This is how the seller agent works in M3 — two MCPToolsets merged.
3. **"SSE is the HTTP transport."** In M3, ADK's `MCPToolset` with `SseConnectionParams` does the same thing. Understanding this script means understanding what ADK does with remote servers.
4. **"No access control here."** Both servers are fully accessible. The restriction (buyer can't call `get_minimum_acceptable_price`) is added in M3 via `before_tool_callback`.

### Questions to try

| # | Command | Expected | What it teaches |
|---|---------|----------|----------------|
| 1 | `python m2_mcp/sse_agent_client.py "What is 742 Evergreen Terrace worth?"` | Calls `get_market_price` → $462K | Basic SSE tool loop |
| 2 | `python m2_mcp/sse_agent_client.py "Calculate a discount for a $485K property"` | Calls `calculate_discount` → offer ranges | LLM picks the right tool |
| 3 | `python m2_mcp/sse_agent_client.py --both "What's the seller's minimum?"` | Calls `get_minimum_acceptable_price` → $445K | Multi-server discovery |
| 4 | `python m2_mcp/sse_agent_client.py --both "Should I offer below asking?"` | Calls multiple tools, synthesizes answer | Multi-tool reasoning |

---

## Questions students might ask

**"Why three transports? Why not just one?"**
Each serves a different deployment pattern. stdio is simplest — the client spawns the server as a subprocess, no networking. SSE is for existing HTTP infrastructure. Streamable HTTP is the spec's recommended production transport — it's cleaner than SSE and supports bidirectional streaming. Use stdio for development, HTTP for production.

**"Can I use a TypeScript MCP server with a Python client?"**
Yes — that's the whole point of a protocol. The GitHub MCP server (`github_agent_client.py`) is TypeScript (`npx @modelcontextprotocol/server-github`). Our Python client connects to it over stdio. The transport and the language are independent.

**"Why does sse_agent_client reconnect for each tool call?"**
SSE connections are inherently unidirectional (server → client). The MCP SDK's `sse_client` establishes a new HTTP session for each interaction. This is a transport detail — stdio maintains a persistent pipe, SSE reconnects. Streamable HTTP (Demo 05) is cleaner because it uses standard POST requests.

**"Why not use function calling / structured outputs from the start?"**
Function calling is how the LLM decides WHICH tool to call — but MCP is how the tool EXECUTES. They're complementary, not alternatives. OpenAI function calling says "call get_market_price(address='742...')". MCP delivers that call to the server and returns the result. In M3, ADK combines both — `MCPToolset` discovers tools via MCP protocol AND exposes them as OpenAI function-calling schemas.

**"How does the LLM know which tools exist?"**
During the MCP handshake, `list_tools()` returns JSON schemas for every tool. The client (our Python code) converts these to OpenAI's function-calling format via `mcp_tools_to_openai_functions()`. The LLM sees tool names, descriptions, and parameter schemas — the same as if you'd hand-written them.

**"What happens if the server crashes mid-tool-call?"**
In stdio mode: the pipe breaks, the client gets an `EOFError`. In SSE/HTTP mode: the client gets a connection error. Either way, the error propagates to the LLM as a tool result (e.g., `{"error": "connection failed"}`). The LLM can decide to retry or give up. In M3, ADK handles this via its error handling pipeline.

**"Is MCP just for AI agents?"**
Primarily yes — it was designed for agents and LLM clients. But the pattern (discover + invoke) works for any tool integration. Claude Desktop, ChatGPT, Cursor, VS Code Copilot, and ADK all support MCP. The 300M+ SDK downloads/month show it's becoming the standard for agent-tool integration.
