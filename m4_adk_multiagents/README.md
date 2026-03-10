# Module 4 — True A2A Protocol (`m4_adk_multiagents`)

**Requires:** `OPENAI_API_KEY`

This module shows what production multi-agent systems look like: two agents running as **independent HTTP services**, communicating over the A2A protocol standard.

---

## What this module teaches

In Module 3, the buyer and seller were both Python objects in the same process. The buyer called the seller like a function.

Module 4 changes that fundamental assumption:

| | Module 3 | Module 4 |
|---|---|---|
| Where agents run | Same Python process | Separate HTTP servers |
| How they communicate | Shared LangGraph state dict | A2A JSON-RPC over HTTP |
| Agent discovery | Hardcoded imports | Agent Card at `/.well-known/agent-card.json` |
| LLM | GPT-4o (OpenAI) | GPT-4o (OpenAI via ADK) |
| Tool framework | Manual MCP calls | ADK `MCPToolset` (auto tool-use) |

This is what you'd build if the buyer and seller were owned by **different teams** — or even different companies.

---

## File breakdown

### `a2a_protocol_seller_server.py` — The A2A seller server *(start here)*

This file turns the seller agent into a real HTTP server. Any A2A-compatible client can connect to it — it doesn't need to be Python or even know that ADK is running underneath.

**What it does:**
- Exposes an Agent Card at `GET /.well-known/agent-card.json`
  - The card describes what the agent does, what inputs it accepts, what it returns
  - Any client fetches this first to discover the agent's capabilities
- Accepts A2A JSON-RPC `message/send` requests at `POST /`
- Runs the ADK seller agent (`seller_adk.py`) to generate a response
- Returns the counter-offer as an A2A task result

**The task lifecycle:**

```
client sends message
    -> task status: "submitted"
    -> SellerADKA2AExecutor.execute() runs
    -> task status: "working"
    -> SellerAgentADK responds (OpenAI + MCP)
    -> task status: "completed"
    -> client receives counter-offer
```

### `a2a_protocol_buyer_client_demo.py` — Single-turn A2A buyer demo *(pair with seller server)*

This file is the buyer's side for a **single request/response**: it makes one offer and sends it to the seller server over the A2A protocol.

**Three-step flow:**

```python
# Step 1: Buyer ADK agent makes an offer (OpenAI + MCP, same as always)
async with BuyerAgentADK(...) as buyer:
    offer = await buyer.make_initial_offer()

# Step 2: Discover the seller — no hardcoded knowledge
resolver = A2ACardResolver(base_url=seller_url)
card = await resolver.get_agent_card()   # GET /.well-known/agent-card.json
client = A2AClient(agent_card=card)

# Step 3: Send the offer as an A2A message
response = await client.send_message(request)   # POST / (message/send)
```

The buyer doesn't import the seller's code. It doesn't know how the seller is built. It only knows the seller's URL and what the Agent Card says.

### `a2a_protocol_http_orchestrator.py` — Multi-round HTTP orchestrator *(recommended path)*

This is the full A2A loop over HTTP (buyer turn -> seller turn -> repeat until terminal state).

**What makes it ADK-native:**
- Round/status tracking is stored in ADK `InMemorySessionService` state
- Buyer/seller exchange strict JSON envelopes over A2A (no `ADKNegotiationMessage` conversion in HTTP path)
- Boundary parsing uses strict `json.loads` fail-fast behavior (no manual JSON scraping)

---

### `buyer_adk.py` — Buyer agent (Google ADK + OpenAI)

The buyer agent, rebuilt with Google ADK instead of OpenAI.

**The key difference from Module 3:**
- In Module 3, the buyer manually called MCP tools then passed results to GPT-4o
- Here, `MCPToolset` gives the model direct access to MCP tools — it decides when to call them autonomously

```python
pricing_toolset = MCPToolset(connection_params=StdioConnectionParams(...))
tools = await pricing_toolset.get_tools()

self._agent = LlmAgent(
  model="openai/gpt-4o",
    tools=tools,    # model calls these when it decides it needs market data
)
```

For ADK provider-style models, use the provider prefix (for example `openai/gpt-4o`).

  ### `seller_adk.py` — Seller agent (Google ADK + OpenAI)

Same pattern as the buyer, but connects to **two** MCP toolsets: pricing + inventory.

```python
all_tools = list(pricing_tools) + list(inventory_tools)
```

The seller has access to `get_minimum_acceptable_price` — the buyer does not. Same information asymmetry as Module 2, now running in a real networked setup.

---

## How to run

**You need two terminals.**

```bash
# Terminal 1 — start the seller A2A server
python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102
# You should see: "A2A seller server listening at http://127.0.0.1:9102"

# Optional but recommended: open the Agent Card in a browser first
# http://127.0.0.1:9102/.well-known/agent-card.json

# Terminal 2 — run the full multi-round orchestrator (after the server is up)
python m4_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 5

# Optional: run the single-turn buyer demo
python m4_adk_multiagents/a2a_protocol_buyer_client_demo.py --seller-url http://127.0.0.1:9102
```

**What to expect:**
- Terminal 1: Server starts, waits. When the buyer connects, you'll see the OpenAI + MCP activity
- Terminal 2 (orchestrator): Runs a real round loop over HTTP until agreement/withdrawal/deadlock
- Final output includes ADK session state (round, status, prices)

---

## Quick mental model

- If you want to understand A2A (core teaching), start with `a2a_protocol_seller_server.py` and `a2a_protocol_http_orchestrator.py`.
- If you want to understand how ADK agents work internally, read `buyer_adk.py` and `seller_adk.py`.

---

## A2A in one diagram

```
Terminal 2 (buyer)                          Terminal 1 (seller)
──────────────────                          ──────────────────────────
BuyerAgentADK                               a2a_protocol_seller_server.py
  OpenAI + MCP                                FastAPI app
  make_initial_offer()                          GET /.well-known/agent-card.json
                                               POST / (message/send)
                                                  |
A2ACardResolver                                   v
  GET /.well-known/ ──────────────────────> returns Agent Card
  agent-card.json

A2AClient                                   SellerADKA2AExecutor
  send_message() ─────────────────────────> execute()
  (HTTP POST /)                               SellerAgentADK
                                               OpenAI + MCP (pricing + inventory)
                                               responds with counter-offer

  receives response <───────────────────── updater.complete(counter_offer)
```
