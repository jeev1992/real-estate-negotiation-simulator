# Module 3 — True A2A Protocol (`m3_adk_multiagents`)

**Requires:** `OPENAI_API_KEY`

This module shows what production multi-agent systems look like: two agents running as **independent HTTP services**, communicating over the A2A protocol standard.

---

## What this module teaches

Up through Module 2, both agents would have lived as Python objects in the same process — the buyer would call the seller like a function.

Module 3 changes that fundamental assumption:

| | In-process baseline | Module 3 (this module) |
|---|---|---|
| Where agents run | Same Python process | Separate HTTP services |
| How they communicate | Direct method calls / shared memory | A2A JSON-RPC over HTTP |
| Agent discovery | Hardcoded imports | Agent Card at `/.well-known/agent-card.json` |
| LLM | GPT-4o (OpenAI) | GPT-4o (OpenAI via Google ADK) |
| Tool framework | Manual MCP calls | ADK `MCPToolset` (auto tool-use) |
| Orchestration | `while` loop in caller | ADK workflow agents (`SequentialAgent`, `LoopAgent`) + A2A task lifecycle |

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
- Buyer/seller exchange strict JSON envelopes over A2A
- Boundary parsing uses strict `json.loads` fail-fast behavior (no manual JSON scraping)

---

### `buyer_adk.py` — Buyer agent (Google ADK + OpenAI)

The buyer agent, rebuilt with Google ADK instead of OpenAI.

**The key idea:**
- A naive buyer would manually call MCP tools and then pass the results to GPT-4o as text.
- Here, ADK's `MCPToolset` gives the model direct access to MCP tools — it decides when to call them autonomously and ADK handles the request/response loop.

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
python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102
# You should see: "A2A seller server listening at http://127.0.0.1:9102"

# Optional but recommended: open the Agent Card in a browser first
# http://127.0.0.1:9102/.well-known/agent-card.json

# Terminal 2 — run the full multi-round orchestrator (after the server is up)
python m3_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 5

# Optional: run the single-turn buyer demo
python m3_adk_multiagents/a2a_protocol_buyer_client_demo.py --seller-url http://127.0.0.1:9102
```

### Visual Dashboard (Streamlit)

For a visual negotiation experience, use the Streamlit dashboard:

```bash
# Terminal 1 — start the seller A2A server (same as above)
python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102

# Terminal 2 — launch the dashboard
streamlit run m3_adk_multiagents/streamlit_dashboard.py
```

The dashboard shows:
- **Price convergence chart** — buyer offers vs seller counters per round
- **Live status banner** — negotiating, agreed, deadlocked, or walked away
- **Round-by-round history** — expandable details with messages, conditions, prices
- **Zone of agreement reference** — buyer ceiling ($460K) and seller floor ($445K)

**What to expect:**
- Terminal 1: Server starts, waits. When the buyer connects, you'll see the OpenAI + MCP activity
- Terminal 2 (orchestrator): Runs a real round loop over HTTP until agreement/withdrawal/deadlock
- Final output includes ADK session state (round, status, prices)

---

## Deep-dive demos (`m3_adk_multiagents/demos/`)

Two flights of standalone, runnable scripts. The first set (01–05) cracks open the **A2A protocol** on the wire against the seller server; the second set (06–11) drills into **Google ADK** primitives without needing the seller server. Companion notes: [a2a_protocols.md](m3_adk_multiagents/notes/a2a_protocols.md), [google_adk_overview.md](m3_adk_multiagents/notes/google_adk_overview.md), [adk_quick_reference.md](m3_adk_multiagents/notes/adk_quick_reference.md).

### A2A protocol demos (need the seller server running)

Start the seller first: `python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102`, then in another terminal:

| Demo | What it shows | Run |
|---|---|---|
| [`01_handcraft_message_send.py`](m3_adk_multiagents/demos/01_handcraft_message_send.py) | Hand-built JSON-RPC `message/send` body POSTed with `httpx` — no A2A SDK, no ADK. The exact wire shape | `python m3_adk_multiagents/demos/01_handcraft_message_send.py --seller-url http://127.0.0.1:9102` |
| [`02_task_lifecycle.py`](m3_adk_multiagents/demos/02_task_lifecycle.py) | Task state transitions: `submitted → working → completed` (valid envelope) and the `failed` path (broken envelope) | `python m3_adk_multiagents/demos/02_task_lifecycle.py --seller-url http://127.0.0.1:9102` |
| [`03_parts_and_artifacts.py`](m3_adk_multiagents/demos/03_parts_and_artifacts.py) | Multi-part `Message` (text + structured data) and the `negotiation-summary` `Artifact` the seller attaches on completion | `python m3_adk_multiagents/demos/03_parts_and_artifacts.py --seller-url http://127.0.0.1:9102` |
| [`04_streaming_negotiation.py`](m3_adk_multiagents/demos/04_streaming_negotiation.py) | `message/stream` JSON-RPC method — receive incremental `TaskStatusUpdate` / `TaskArtifactUpdate` events as they arrive | `python m3_adk_multiagents/demos/04_streaming_negotiation.py --seller-url http://127.0.0.1:9102` |
| [`05_context_threading.py`](m3_adk_multiagents/demos/05_context_threading.py) | Reusing `contextId` + `taskId` across rounds so the seller recognizes follow-ups as the same negotiation | `python m3_adk_multiagents/demos/05_context_threading.py --seller-url http://127.0.0.1:9102` |

### ADK primitives demos (no server needed)

These show ADK building blocks in isolation — useful before reading `buyer_adk.py` / `seller_adk.py`. They call the OpenAI API directly via ADK.

| Demo | What it shows | Run |
|---|---|---|
| [`06_sequential_agent.py`](m3_adk_multiagents/demos/06_sequential_agent.py) | `SequentialAgent` chains `market_brief → offer_drafter → message_polisher`, passing data via session state | `python m3_adk_multiagents/demos/06_sequential_agent.py` |
| [`07_parallel_agent.py`](m3_adk_multiagents/demos/07_parallel_agent.py) | `ParallelAgent` fan-out — three sub-agents run concurrently writing to different state keys | `python m3_adk_multiagents/demos/07_parallel_agent.py` |
| [`08_loop_agent.py`](m3_adk_multiagents/demos/08_loop_agent.py) | `LoopAgent` with a haggler + judge — the judge `escalate`s to break the loop when the price is in range | `python m3_adk_multiagents/demos/08_loop_agent.py` |
| [`09_agent_as_tool.py`](m3_adk_multiagents/demos/09_agent_as_tool.py) | `AgentTool` — wrap an agent so another agent can call it like a function (foundation for expert hierarchies) | `python m3_adk_multiagents/demos/09_agent_as_tool.py` |
| [`10_tool_context.py`](m3_adk_multiagents/demos/10_tool_context.py) | `ToolContext` — a function tool that reads/writes session state with scope prefixes (`app:`, `user:`, `temp:`) across turns | `python m3_adk_multiagents/demos/10_tool_context.py` |
| [`11_callbacks.py`](m3_adk_multiagents/demos/11_callbacks.py) | `before_model` / `before_tool` / `after_tool` callbacks — PII redaction, tool allowlist, and result logging | `python m3_adk_multiagents/demos/11_callbacks.py` |

---

## Exercises

| Exercise | Difficulty | Task |
|---|---|---|
| `ex01_fetch_agent_card.md` | `[Core]` | Write a script to fetch and inspect the seller's A2A Agent Card — learn agent discovery |
| `ex02_history_endpoint.md` | `[Core]` | Add a `/history` REST endpoint to the seller server for negotiation observability |

Solutions are in `m3_adk_multiagents/solution/`. Each exercise includes a reflection question.

---

## Quick mental model
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
