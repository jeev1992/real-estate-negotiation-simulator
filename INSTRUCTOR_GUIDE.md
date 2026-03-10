# Instructor Guide — Real Estate Negotiation Simulator Workshop
## 4-Hour Workshop Flow Script

---

## BEFORE THE SESSION (30 min prep)

### Environment Setup
```bash
cd negotiation_workshop
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env
# Edit .env — add your OPENAI_API_KEY
```

### Verify everything works before participants arrive
```bash
python m1_baseline/state_machine.py        # Should print FSM demo, no API key
python m1_baseline/naive_negotiation.py    # Should fail loudly (that's the point)
pytest tests/ -v                           # All tests should pass, no API keys needed
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 2           # Quick smoke test with OpenAI
python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102
python m4_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 1
```

### What to have on screen when participants arrive
- Terminal open in `negotiation_workshop/`
- This guide visible in a second window
- README.md open showing architecture diagram

### Opening repo structure callout (first 2–3 min)

At the start of the workshop, explicitly orient learners to the repo layout:

- Each module folder (`m1_baseline/`, `m2_mcp/`, `m3_langgraph_multiagents/`, `m4_adk_multiagents/`) has its own `README.md`.
- That module `README.md` explains what the module demonstrates and how to run it.
- Each module also has a `notes/` folder for deeper conceptual material.
- Encourage participants to treat module `README.md` as the runbook and `notes/` as the reference.

---

## WORKSHOP SCHEDULE OVERVIEW

| Time        | Module | Topic                                        | Key Command / File                              |
|-------------|--------|----------------------------------------------|-------------------------------------------------|
| 0:00–0:15   | Intro  | What we're building + architecture overview  | Show README diagram                             |
| 0:15–0:30   | M1     | Why naive AI agents break (demo)             | `python m1_baseline/naive_negotiation.py`       |
| 0:30–0:45   | M1     | FSM: the termination fix                     | `python m1_baseline/state_machine.py`           |
| 0:45–1:30   | M2     | MCP deep dive: protocol + GitHub live demo   | `python m2_mcp/github_demo_client.py`           |
| 1:30–1:45   | Break  | —                                            | —                                               |
| 1:45–2:05   | M2     | Custom MCP servers + information asymmetry   | Walk `m2_mcp/pricing_server.py`                 |
| 2:05–2:50   | M3     | LangGraph deep dive + full run               | `m3_langgraph_multiagents/langgraph_flow.py`, `m3_langgraph_multiagents/main_langgraph_multiagent.py` |
| 2:50–3:50   | M4     | A2A protocol: networked agents               | `m4_adk_multiagents/a2a_protocol_seller_server.py`, `m4_adk_multiagents/a2a_protocol_buyer_client_demo.py` |
| 3:50–4:00   | Wrap   | Exercises + Q&A                              | `exercises/code_solutions/README.md`            |

### Note Mapping

Notes live inside each module's `notes/` subfolder.

| Module | Notes location |
|---|---|
| M1 | `m1_baseline/notes/agents_fundamentals.md` |
| M2 | `m2_mcp/notes/mcp_deep_dive.md` |
| M3 | `m3_langgraph_multiagents/notes/langgraph_explained.md` |
| M4 | `m4_adk_multiagents/notes/a2a_protocols.md` |
| M4 | `m4_adk_multiagents/notes/google_adk_overview.md` |
| M4 (cross-module) | `m4_adk_multiagents/notes/langgraph_adk_a2a_comparison.md` |

---

## MODULE-BY-MODULE SCRIPT

---

### INTRO (0:00–0:15) — "What We're Building"

**SAY:**
> "Today we're building a real multi-agent system. Two AI agents — a buyer and a seller —
> will negotiate the purchase of a house at 742 Evergreen Terrace, Austin TX, listed at $485,000.
>
> The buyer has a max budget of $460K. The seller won't go below $445K.
> There's a $15K zone of agreement — the question is whether the agents find it,
> and how cleanly the system terminates either way.
>
> We're building this three different ways so you can see the same problem solved
> with increasing sophistication: a broken naive version, then OpenAI + LangGraph,
> then OpenAI + Google ADK. Same negotiation, same MCP servers, different frameworks."

**SHOW:** README.md — architecture diagram.

**KEY TALKING POINTS:**
- Every layer of the architecture solves a specific failure mode from the naive version
- MCP = agent ↔ external data. A2A = agent ↔ agent. LangGraph = workflow orchestration.
- Why real estate: concrete domain, clear adversarial agents, obvious information asymmetry

---

### MODULE 1 — Part 1 (0:15–0:30): "Why Naive AI Agents Break"

```bash
python m1_baseline/naive_negotiation.py
```

**SAY before running:**
> "This is what most people build first. It works in the demo.
> Watch what happens when we stress-test it."

**WATCH FOR:**
- Demo 1: Works by luck — string parsing happens to work
- Demo 2: RUNS 100 TURNS on an impossible agreement — no real termination
- Demo 3: The 10 failure modes printed explicitly

**SAY after Demo 2:**
> "100 turns. That's the emergency exit. In production: infinite loop, burning tokens.
> And the 'DEAL' detection is string matching — fragile."

**WALK THROUGH the code:**
```python
while True:                              # no guarantee
    if "DEAL" in seller_response:        # string matching — can be spoofed
    if turn_count > 100: break           # emergency exit, not a proof
```

**SAY:**
> "Ten problems. We'll fix all of them. The summary table at the bottom maps each
> problem to which workshop component resolves it."

---

### MODULE 1 — Part 2 (0:30–0:45): "The FSM Fix"

```bash
python m1_baseline/state_machine.py
```

**SAY:**
> "A Finite State Machine gives a mathematical guarantee: the negotiation MUST terminate.
> Not 'should'. MUST. Here's why."

**WALK THROUGH the TRANSITIONS dict:**
```python
TRANSITIONS = {
    NegotiationState.IDLE:        {NEGOTIATING, FAILED},
    NegotiationState.NEGOTIATING: {NEGOTIATING, AGREED, FAILED},
    NegotiationState.AGREED:      set(),    # EMPTY = no way out
    NegotiationState.FAILED:      set(),    # EMPTY = no way out
}
```

> "Terminal states have empty sets. You cannot leave them. That's the proof."

Point to the informal proof in the class docstring:
> "M = (is_terminal, turn_count). Every call either sets is_terminal=True (done)
> or increments turn_count. Since turn_count is bounded by max_turns,
> the FSM reaches a terminal state in finite steps. QED."

**ASK:**
> "LangGraph has a node called END with no outgoing edges.
> Does that structure look familiar?"
> (Answer: it's the same guarantee, at workflow level. Preview for Module 3.)

**Run the tests:**
```bash
pytest tests/test_fsm.py -v
```
> "TestTerminationGuarantee tests the mathematical property — not just 'does it run'."

---

### MODULE 2 — Part 1 (0:45–1:30): "MCP Deep Dive + GitHub Live Demo"

This is the longest single block. Spend real time here — MCP is foundational.

#### 1. Conceptual framing (5 min)

**DRAW on whiteboard or show:**
```
WITHOUT MCP:
  LLM prompt: "The house at 742 Evergreen is worth about $450K"
  (hardcoded, stale, can't verify, agent can't query anything)

WITH MCP:
  LLM prompt: "You have access to get_market_price(). Call it first."
  LLM calls:  get_market_price("742 Evergreen Terrace...")
  Server:     returns live comps, estimated value, market condition
  LLM reasons: on real data
```

**SAY:**
> "MCP is the standard protocol for giving agents access to external data and tools.
> Think of it like a USB standard — any MCP client can connect to any MCP server.
> GitHub publishes one. Anthropic publishes one for filesystem. We built two custom ones.
> The pattern is always the same."

**The three things MCP defines:**
1. **Discovery** — "What tools do you have?" (list_tools)
2. **Schema** — "What arguments does each tool take?" (JSON Schema)
3. **Invocation** — "Call this tool with these args" (call_tool)

> "That's it. Three operations. The LLM sees function signatures, not HTTP endpoints.
> The MCP server handles the actual implementation."

#### 2. Transport layer (3 min)

**SHOW:**
```
stdio transport:
  Client spawns server as subprocess
  Communicates via stdin/stdout pipes
  Simple, local, no network needed
  -> Used in our workshop

SSE transport (Server-Sent Events):
  Server runs as HTTP endpoint
  Client connects via HTTP
  Can be remote, multiple clients
  -> Used in production
```

**SAY:**
> "Both transports use the same JSON-RPC wire protocol.
> Switch `--sse` on our server and the tools are identical.
> Production teams start with stdio for local dev, then move to SSE/HTTP."

#### 3. Wire protocol (5 min)

**SHOW the JSON-RPC messages — write these on a whiteboard:**

```json
// Client → Server: initialize
{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}

// Server → Client: capabilities
{"jsonrpc": "2.0", "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}}

// Client → Server: list tools
{"jsonrpc": "2.0", "method": "tools/list", "params": {}}

// Server → Client: tool schemas
{"jsonrpc": "2.0", "result": {"tools": [
  {"name": "get_market_price", "description": "...", "inputSchema": {"type": "object", "properties": {...}}}
]}}

// Client → Server: call tool
{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "get_market_price", "arguments": {"address": "742..."}}}

// Server → Client: result
{"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": "{\"estimated_value\": 462000, ...}"}]}}
```

**SAY:**
> "That's the entire protocol. Six message types. JSON-RPC 2.0 over stdio or HTTP.
> The Python `mcp` library handles this for you — you just call `session.call_tool()`
> and it constructs the JSON-RPC messages."

#### 4. GitHub live demo (20 min)

**Prerequisites check:**
```bash
node --version      # Need 18+
echo $GITHUB_TOKEN  # Should start with ghp_
```

**Run:**
```bash
python m2_mcp/github_demo_client.py
```

**WALK THROUGH the output section by section — pause after each:**

**Section 1 — Connection:**
> "Watch the handshake. Our Python client spawns the GitHub npm package as a subprocess,
> connects via stdio, and negotiates the protocol version.
> This is the `initialize` JSON-RPC call we just saw on the whiteboard."

**Section 2 — Tool Discovery:**
> "The client sends `tools/list`. The server responds with ALL available tools —
> GitHub's MCP server has 50+ tools. We're printing the first few.
> Notice the JSON schema for each tool — that's what the LLM receives.
> The LLM doesn't know what GitHub is. It just sees function signatures."

**SHOW what the LLM actually sees (explain the schema):**
```json
{
  "name": "search_repositories",
  "description": "Search for GitHub repositories",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "Search query"},
      "page": {"type": "integer", "default": 1}
    },
    "required": ["query"]
  }
}
```
> "The LLM's function-calling mechanism reads this schema and knows:
> 'I can call search_repositories(query=...). It needs at least a query string.'
> No HTTP knowledge. No REST concepts. Just function signatures."

**Section 3 — Tool Calling:**
> "Now we call `get_me()` — same as running `gh api /user`.
> Under the hood: `tools/call` JSON-RPC request. Server executes GitHub API call. Returns text."
>
> "Notice we didn't write any GitHub API code. We wrote MCP client code.
> The server handles the GitHub integration. This is the power of the protocol separation."

**Section 4 — Side by Side:**
> "Direct REST call vs MCP call — same data, different path.
> The MCP path adds: tool discovery, schema validation, LLM compatibility.
> The direct path is faster but the LLM can't call it autonomously."

**Section 5 — Bridge to our servers:**
> "Now look at the comparison table in the output.
> `search_repositories()` maps to our `get_market_price()`.
> `get_file_contents()` maps to our `calculate_discount()`.
> `GITHUB_TOKEN` env var maps to our pricing server having no auth (it's local).
> The pattern is identical. Only the domain changes."

**KEY INSIGHT — draw this:**
```
MCP = Agent ↔ External Tool
A2A = Agent ↔ Agent

Buyer agent flow:
  1. [LLM planner] decide which MCP tool(s) to call this turn
  2. [MCP] execute selected tool call(s) → pricing_server.py
  3. Reason about the data with GPT-4o
  4. [A2A] send OFFER message            → seller agent
```

**ASK the group:**
> "Why not just hardcode the market data in the prompt?
> What breaks if you do that?"
>
> Answers: data goes stale, can't adapt to different properties, agent can't query follow-up,
> no audit trail of what data was used, can't swap data sources.

**ASK:**
> "Why does MCP use JSON-RPC instead of REST?"
>
> Answer: bidirectional, streaming-friendly, language-agnostic, the server can push
> notifications back. REST is request-response only. MCP needs the server to
> potentially push tool-call results async.

**Run the FSM tests to reinforce termination concepts:**
```bash
pytest tests/test_fsm.py -v
```

> "These tests validate the FSM termination guarantee from Module 1 — same guarantee
> that LangGraph's END node provides at workflow level."

---

### BREAK (1:50–2:05)

Leave `m2_mcp/pricing_server.py` open. Terminal ready.

---

### MODULE 2 — Part 2 (1:45–2:05): "Custom MCP Servers"

**SAY:**
> "The GitHub demo showed us what a published MCP server looks like.
> Now we look at our own — and how a simple design choice creates information asymmetry."

#### Walk through `m2_mcp/pricing_server.py` — highlight the @mcp.tool() decorator

```python
@mcp.tool()
def get_market_price(address: str, property_type: str = "single_family") -> dict:
    """Get comprehensive market pricing data for a property."""
    ...
```

> "The `@mcp.tool()` decorator registers this function with the MCP server.
> The function signature becomes the JSON Schema. The docstring becomes the description.
> When the LLM calls this tool, the server runs this exact Python function."

**Show the return structure:**
> "Returns JSON with: estimated_value, comparable_sales, market_condition, days_on_market.
> The buyer uses this to justify every offer. No hallucination — it's grounded in data."

**Show SSE mode:**
```bash
python m2_mcp/pricing_server.py --sse --port 8001   # start in terminal 1
# same tools, now accessible via HTTP
```

#### Walk through `m2_mcp/inventory_server.py` — the information asymmetry

```python
@mcp.tool()
async def get_minimum_acceptable_price(property_id: str) -> str:
    """Get the seller's minimum acceptable price (seller-confidential)."""
    ...
```

> "This tool only exists on the SELLER's server. The buyer's server doesn't have it.
> The buyer is trying to INFER the floor price from market data.
> The seller KNOWS it exactly because the inventory server tells it.
>
> We model information asymmetry by controlling which MCP server each agent connects to.
> In production, you'd add MCP auth (OAuth tokens) to enforce this at the protocol level.
> Our comments point to where you'd add that."

**ASK:**
> "Can you think of other real-world domains where information asymmetry matters?
> Insurance? Job offers? Healthcare billing?"

---

### MODULE 3 (2:05–2:50): "LangGraph Deep Dive + Full Simple Version"

This is the most complex module. Take it in three parts.

#### Part A: Why orchestration? (2:05–2:15) — 10 min

**SAY:**
> "Before LangGraph, multi-agent coordination looked like this:"

```python
# Raw Python approach
buyer_response = buyer_agent(initial_prompt)
seller_response = seller_agent(buyer_response)
buyer_response = buyer_agent(seller_response)
# ... repeat manually
```

> "Problems:
> - No shared state. Each call is stateless.
> - You manage the loop. You manage termination. You manage errors.
> - You can't add a third agent without rewriting the loop.
>
> LangGraph solves all three: shared state, declarative routing, built-in termination."

**DRAW the mental model:**
```
                    LANGGRAPH MENTAL MODEL
                    ======================

Raw Python:             LangGraph:
  while True:             START
    buyer(...)               |
    seller(...)           buyer_node
    if done: break           |
                          seller_node
                             |
                         [conditional router]
                          /           \
                      buyer_node      END
                      (loop)
```

> "LangGraph turns your orchestration logic into a graph.
> The graph is the control flow. Nodes are the work. Edges are the routing.
> And END is a terminal node — same as the FSM's AGREED/FAILED states."

#### Part B: LangGraph code walkthrough (2:15–2:35) — 20 min

Open `m3_langgraph_multiagents/langgraph_flow.py`.

**1. The State — 5 min**

```python
class NegotiationState(TypedDict):
    # Immutable context: session_id, property_address, listing_price
    # Agent constraints: buyer_budget, seller_minimum, max_rounds
    # Current positions: buyer_current_offer, seller_current_counter
    # Round tracking: round_number
    # Outcome: status, agreed_price
    # Last messages (node-to-node handoff): last_buyer_message, last_seller_message
    # Append-only audit trail: history
    # Agent references (set once in init node): _buyer_agent_ref, _seller_agent_ref
```

> "This TypedDict is the SINGLE source of truth for the entire negotiation.
> Every node reads from it. Every node writes to it.
> No global variables. No passing objects between functions.
> The state flows through the graph."

**Point to the Annotated reducer pattern:**
```python
# From langgraph_flow.py — the actual field definition:
history: Annotated[list[dict], operator.add]
```

> "This is LangGraph's Annotated reducer. Instead of overwriting the list,
> each node APPENDS to it. So after 5 rounds you have all 10 messages in order.
> Without this: each node would overwrite the previous history.
> With it: history accumulates automatically."

**ASK:**
> "Why not just use a global variable for the message history?"
> (Answer: graph nodes run async, possibly in parallel in other workflows.
> State is thread-safe. Globals are not.)

**2. The Nodes — 5 min**

```python
async def buyer_node(state: dict) -> dict:
    buyer_agent: BuyerAgent = state["_buyer_agent_ref"]
    last_seller_msg = state.get("last_seller_message")

    if last_seller_msg is None:
        buyer_message = await buyer_agent.make_initial_offer()   # Round 1
    else:
        buyer_message = await buyer_agent.respond_to_counter(last_seller_msg)  # Round 2+

    # Determine status from message type
    new_status = state["status"]
    if buyer_message["message_type"] == "WITHDRAW":
        new_status = "buyer_walked"
    elif buyer_message["message_type"] == "ACCEPT":
        new_status = "agreed"

    return {
        "buyer_current_offer": buyer_message.get("price") or state["buyer_current_offer"],
        "round_number": buyer_message["round"],
        "status": new_status,
        "last_buyer_message": buyer_message,
        "history": [{"round": buyer_message["round"], "agent": "buyer", ...}],  # reducer appends
    }
```

> "Notice: the node takes state, does work, returns a PARTIAL state update.
> LangGraph merges the returned dict into the existing state.
> The node doesn't know about other nodes. It communicates through state:
> buyer_node writes last_buyer_message → seller_node reads last_buyer_message.
>
> Node types in LangGraph:
> - LLM step: calls a language model (buyer_node, seller_node)
> - Data step: reads/transforms data
> - Action step: calls an API, tool, or side effect
> - User input step: waits for human input (interrupts)
>
> Our buyer_node is all three: it reads state (data), calls MCP (action), calls GPT-4o (LLM)."

**3. The Router — 5 min**

```python
def route_after_seller(state: dict) -> Literal["continue", "end"]:
    status = state.get("status", "negotiating")
    if status != "negotiating":
        return "end"
    if state.get("round_number", 0) >= state.get("max_rounds", 5):
        return "end"
    return "continue"
```

> "This is the FSM translated into LangGraph. Every non-negotiating status routes to 'end'.
> 'end' maps to the END constant — a special node with no outgoing edges.
> The graph CANNOT leave END. Termination guaranteed at the workflow level."

**Show how the graph is assembled:**
```python
workflow = StateGraph(NegotiationState)
workflow.add_node("init", initialize_agents_node)
workflow.add_node("buyer", buyer_node)
workflow.add_node("seller", seller_node)
workflow.set_entry_point("init")
workflow.add_edge("init", "buyer")
workflow.add_conditional_edges("buyer", route_after_buyer, {"to_seller": "seller", "end": END})
workflow.add_conditional_edges("seller", route_after_seller, {"continue": "buyer", "end": END})
graph = workflow.compile()
```

> "add_node: register the function.
> add_edge: unconditional transition.
> add_conditional_edges: the router function returns a string key, mapped to the next node.
> compile(): validates the graph, checks for unreachable nodes, builds the execution plan."

**4. The cycle — 2 min**

> "The buyer → seller → buyer loop is a CYCLE in the graph.
> LangGraph allows cycles. The termination guarantee comes from two sources:
> 1. The router returns 'end' for terminal states
> 2. max_rounds enforces a hard ceiling on iterations
> Both are explicit in the code — not hidden in a while loop."

**COMPARISON — put these side by side:**
```python
# Naive (naive_negotiation.py)          # LangGraph (langgraph_flow.py)
while True:                              # while not fsm.is_terminal():
    buyer_msg = buyer.respond(...)       #   buyer_node(state) -> returns update
    if "DEAL" in buyer_msg: break        #   route_after_buyer -> "to_seller" or "end"
    seller_msg = seller.respond(...)     #   seller_node(state) -> returns update
    if turn > 100: break                 #   route_after_seller -> "continue" or "end"
```

> "LangGraph forces you to be explicit about routing. You can't accidentally forget
> to check a terminal condition. The graph structure IS the termination logic."

#### Part C: Run and observe (2:35–2:50) — 15 min

```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py
```

**SAY:**
> "Watch the output with this mental model:
> - '[Buyer] Calling MCP' = MCP protocol in action (Module 2)
> - '[LangGraph] routing' = conditional edge firing
> - 'A2A messages' = structured agent-to-agent communication
> Each line you see corresponds to a specific layer of the architecture."

**AFTER IT RUNS — debrief (5 min):**
- What round did they agree? (Usually 2–4)
- Was the price in the $445K–$460K zone?
- Which agent conceded more? Why? (Seller starts higher, must come down more)

**TRY a deadlock scenario:**
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --seller-minimum 470000 --buyer-budget 460000
```
> "No overlap zone. Watch LangGraph terminate cleanly at round 5.
> Count the lines — exactly 5 rounds, then END. No emergency exit needed."

---

### MODULE 4 (2:50–3:50): "True A2A Protocol — Networked Agents"

This module shows what production multi-agent systems look like: two agents running
as independent HTTP services, communicating over the A2A protocol standard.

**THE BIG PICTURE:**
> "In Modules 2 and 3, both agents lived in the same Python process.
> The buyer called the seller like a function.
> In the real world, agents run on different machines, owned by different teams,
> possibly written in different languages.
> The A2A protocol is the standard that makes that possible.
> This module shows the exact same negotiation — but now the seller is an HTTP server
> and the buyer calls it over the network."

**DRAW the architecture shift:**
```
MODULE 3 (same process):
  main_langgraph_multiagent.py
    buyer_node() ----calls----> seller_node()
    (Python function call — same memory, same machine)

MODULE 4 (networked A2A):
  Terminal 1: a2a_protocol_seller_server.py   <-- HTTP server, port 9102
  Terminal 2: a2a_protocol_buyer_client_demo.py

  buyer_adk.py                   a2a_protocol_seller_server.py
  [OpenAI + MCP]                 [A2A endpoint]
       |                               |
       | 1. make offer via ADK         | 3. receive A2A message
       | 2. send via A2AClient ------> | 4. run SellerAgentADK
       |    HTTP POST /               | 5. return counter-offer
       | 6. parse response <--------- |
```

---

#### Part A: The A2A Protocol (2:50–3:05) — 15 min

**SAY:**
> "A2A (Agent-to-Agent) is an open protocol for agents to discover and call each other.
> It defines three things — the same three things MCP defines, but for agents instead of tools."

**DRAW the parallel:**
```
MCP (agent <-> tool):           A2A (agent <-> agent):
  1. list_tools()                 1. GET /.well-known/agent-card.json
     "What can you do?"              "Who are you and what can you do?"
  2. Tool JSON Schema             2. Agent Card (skills, input/output modes)
     "How do I call you?"            "Here's my full capability description"
  3. tools/call                   3. POST / (message/send JSON-RPC)
     "Do this thing"                 "Handle this task"
```

> "The Agent Card is the A2A equivalent of MCP's tool schema.
> It's a JSON document at a well-known URL that describes what the agent does,
> what inputs it accepts, and what it returns.
> Any client can discover any A2A agent just by fetching that URL."

**Show the Agent Card from `a2a_protocol_seller_server.py`:**
```python
AgentCard(
    name="adk_seller_a2a_server",
    description="Google ADK-backed seller agent exposed via A2A protocol",
    url=base_url,
    skills=[
        AgentSkill(
            id="real_estate_seller_negotiation",
            name="Real Estate Seller Negotiation",
            description="Responds to buyer offers with ADK-generated counter-offers or acceptance",
            tags=["real_estate", "negotiation", "seller", "adk", "a2a"],
            examples=["Buyer offers $438,000 with 45-day close"],
        )
    ],
)
```

> "This Agent Card is served at `GET /agent-card.json`.
> The buyer client fetches it first, before sending a single message.
> From the card, the client knows: what this agent does, what format it accepts,
> and what URL to POST tasks to.
> No documentation needed. Self-describing, like MCP tools."

**The task lifecycle — 2 min:**
> "A2A introduces the concept of a Task — a unit of work with a lifecycle:
> submitted -> working -> completed (or failed).
> The `TaskUpdater` in our server code drives this:
> `await updater.start_work()` ... `await updater.complete(message)`
> Long-running agents can stream partial results back through the task lifecycle."

---

#### Part B: ADK as the Agent Backing Layer (3:05–3:15) — 10 min

Open `m4_adk_multiagents/buyer_adk.py` and `m4_adk_multiagents/seller_adk.py`.

**SAY:**
> "The ADK agents are the LLM + MCP layer — the intelligence behind the A2A endpoints.
> Understanding three things is enough:"

**1. LlmAgent + MCPToolset — the agent definition**

```python
pricing_toolset = MCPToolset(connection_params=StdioConnectionParams(...))
tools = await pricing_toolset.get_tools()   # discovers get_market_price, calculate_discount

self._agent = LlmAgent(
    name="buyer_agent",
  model="openai/gpt-4o",
    instruction=BUYER_INSTRUCTION,
    tools=tools,   # model can now call MCP tools autonomously
)
```

> "MCPToolset replaces all the manual `stdio_client` / `call_tool` code from Module 3.
> The model decides when to call which tools — the tool-use loop is inside the ADK runner.
> The seller uses TWO toolsets merged together: pricing + inventory."

**2. Runner executes turns, SessionService holds memory**

> "Runner.run_async() returns an event stream — tool calls, tool results, final response.
> SessionService gives the agent memory across rounds. That's the full ADK picture."

**3. Context manager = clean MCP subprocess management**

> "Both agents are async context managers. `__aenter__` connects to MCP servers.
> `__aexit__` closes them. No leaked subprocesses even if the negotiation crashes."

---

#### Part C: The A2A Seller Server (3:15–3:30) — 15 min

Open `m4_adk_multiagents/a2a_protocol_seller_server.py`.

**Walk through the executor — the heart of the server:**

```python
class SellerADKA2AExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, task_id=context.task_id, ...)
        await updater.start_work()                       # task is now "working"

        incoming_text = context.get_user_input().strip() # the buyer's message
        buyer_price = _extract_price(incoming_text)      # parse the offer

        buyer_message = create_offer(...)                # wrap as ADK A2A type

        async with SellerAgentADK(...) as seller:
            seller_reply = await seller.respond_to_offer(buyer_message)  # run ADK agent

        response_payload = {                             # serialize response
            "message_type": seller_reply.message_type,
            "price": seller_reply.payload.price,
            "message": seller_reply.payload.message,
        }

        agent_message = updater.new_agent_message(parts=[TextPart(text=json.dumps(response_payload))])
        await updater.complete(agent_message)            # task is now "completed"
```

> "The executor is the adapter between the A2A protocol and the ADK agent.
> It receives an A2A task, runs the seller ADK agent, and returns the result.
> The ADK agent does all the OpenAI + MCP reasoning — the executor just wires it up."

**Show how the server is assembled:**

```python
handler = DefaultRequestHandler(
    agent_executor=SellerADKA2AExecutor(),
    task_store=InMemoryTaskStore(),
    queue_manager=InMemoryQueueManager(),
)
app_builder = A2ARESTFastAPIApplication(agent_card=card, http_handler=handler)
app = app_builder.build(agent_card_url="/.well-known/agent-card.json", rpc_url="/")
uvicorn.run(app, host=args.host, port=args.port)
```

> "A2ARESTFastAPIApplication wires the handler into a FastAPI app with two routes:
> GET `/.well-known/agent-card.json` — returns the Agent Card
> POST `/` — handles `message/send` JSON-RPC calls
> That's the entire A2A server. Any A2A-compatible client can now talk to it."

---

#### Part D: The A2A Buyer Client (3:30–3:40) — 10 min

Open `m4_adk_multiagents/a2a_protocol_buyer_client_demo.py`.

**Walk through the three-step client flow:**

```python
# Step 1: Buyer ADK agent makes an offer (OpenAI + MCP — same as before)
async with BuyerAgentADK(session_id=...) as buyer:
    offer = await buyer.make_initial_offer()

offer_text = f"Buyer offer: ${offer.payload.price:,.0f}. Message={offer.payload.message}"

async with httpx.AsyncClient() as http_client:
    # Step 2: Discover the seller — fetch Agent Card from well-known URL
    resolver = A2ACardResolver(httpx_client=http_client, base_url=args.seller_url)
    card = await resolver.get_agent_card()     # GET /.well-known/agent-card.json
    client = A2AClient(httpx_client=http_client, agent_card=card)

    # Step 3: Send the offer over A2A JSON-RPC
    request = SendMessageRequest(
        params=MessageSendParams(
            message=Message(parts=[TextPart(text=offer_text)])
        )
    )
    response = await client.send_message(request)   # POST / (message/send)
```

> "Three lines of actual business logic — the rest is standard protocol plumbing.
> Step 1: buyer ADK makes the offer exactly as before.
> Step 2: discover the seller's capabilities from its well-known URL — no hardcoding.
> Step 3: send the offer as an A2A message. The seller could be on any machine."

**ASK:**
> "In Module 3, the buyer and seller shared a LangGraph state dict.
> In Module 4, what does the buyer know about the seller's internal state?"
>
> Answer: Nothing. The buyer only knows what's in the Agent Card and the response message.
> The seller's floor price, MCP calls, model reasoning — all hidden behind the A2A interface.
> This is true information encapsulation. Even stronger than the MCP access control from Module 2.

---

#### Part E: Run the Full A2A Demo (3:40–3:50) — 10 min

**Prerequisites:**
```bash
pip install a2a-sdk uvicorn httpx litellm   # if not already in requirements.txt
export OPENAI_API_KEY=sk-...
```

**Terminal 1 — start the seller A2A server:**
```bash
python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102
# Output: A2A seller server listening at http://127.0.0.1:9102
#         Agent card: http://127.0.0.1:9102/.well-known/agent-card.json
```

**Instructor live demo (do this before Terminal 2): open Agent Card in browser**

After starting the server, open:

`http://127.0.0.1:9102/.well-known/agent-card.json`

Explain that this is the seller agent's self-description (A2A discovery document) that any A2A client can fetch before sending a message.

Expected response shape:

```json
{
  "capabilities": {
    "pushNotifications": false,
    "streaming": false
  },
  "defaultInputModes": [
    "text/plain"
  ],
  "defaultOutputModes": [
    "text/plain"
  ],
  "description": "ADK-backed seller agent exposed via A2A protocol",
  "name": "adk_seller_a2a_server",
  "preferredTransport": "JSONRPC",
  "protocolVersion": "0.3.0",
  "provider": {
    "organization": "Negotiation Workshop",
    "url": "https://example.local/negotiation-workshop"
  },
  "skills": [
    {
      "description": "Responds to buyer offers with ADK-generated counter-offers or acceptance",
      "examples": [
        "Buyer offers $438,000 with 45-day close"
      ],
      "id": "real_estate_seller_negotiation",
      "inputModes": [
        "text/plain"
      ],
      "name": "Real Estate Seller Negotiation",
      "outputModes": [
        "text/plain"
      ],
      "tags": [
        "real_estate",
        "negotiation",
        "seller",
        "adk",
        "a2a"
      ]
    }
  ],
  "url": "http://127.0.0.1:9102",
  "version": "1.0.0"
}
```

**Terminal 2 — run the HTTP orchestrator loop:**
```bash
python m4_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 5
```

**Optional single-turn demo:**
```bash
python m4_adk_multiagents/a2a_protocol_buyer_client_demo.py --seller-url http://127.0.0.1:9102
```

**Watch specifically for:**
- Buyer runs multi-round offers via ADK (you see OpenAI + MCP tool calls in terminal 2)
- Client fetches the Agent Card from the seller server (in terminal 1 logs)
- `message/send` JSON-RPC request fires each round — visible in both terminals
- Seller runs its ADK agent (OpenAI + 3 MCP tool calls visible in terminal 1)
- Orchestrator stops on terminal state or max rounds and prints ADK session state

**AFTER IT RUNS — the key insight:**
> "The buyer had no import of seller_adk.py. No shared state object. No shared process.
> It sent an HTTP request to a URL. The seller could be deployed on AWS, written in Java,
> maintained by a completely different team — as long as it speaks A2A, the buyer works.
> That's the point of a protocol standard."

---

### WRAP-UP (3:50–4:00): Exercises + Q&A

```bash
start exercises/code_solutions/README.md    # Windows
open exercises/code_solutions/README.md     # Mac
```

**RECOMMENDED EXERCISES by difficulty:**

**Easy (15 min) — no API keys:**
- Exercise 1: Define MCP, A2A, FSM in your own words. How does each solve a specific failure from naive_negotiation.py?
- Run `pytest tests/ -v` and explain what each test class is verifying.

**Medium (30 min) — requires API keys:**
- Exercise 5: Add `get_school_district_rating(zip_code)` to the pricing server and wire it into the buyer's prompt
- Exercise 6: Add retry logic with exponential backoff to `call_pricing_mcp()` in buyer_simple.py

**Hard (45+ min):**
- Exercise 7: Implement the SSE client — connect buyer_simple.py to pricing_server running with `--sse --port 8001`
- Exercise 8: Add a mediator agent to LangGraph — triggers when gap > $20K and offers a split-the-difference counter
- Exercise 9: Replace InMemorySessionService with a file-based session to make the ADK negotiation resumable

**Part D (45+ min):**
- Exercise 11: Run and extend `exercises/code_solutions/ex11_support_triage_langgraph_runner.py`
- Exercise 12: Run and extend `exercises/code_solutions/ex12_support_triage_adk_runner.py`

**Exercise 7 prerequisite (SSE):**
```bash
# Terminal 1
python m2_mcp/pricing_server.py --sse --port 8001

# Terminal 2
python exercises/code_solutions/ex07_sse_client_demo.py
```

**Q&A prompts if the group is quiet:**
- "If you had to add a third agent — a real estate attorney who reviews the final deal — where would it go in the LangGraph graph?"
- "The seller's floor price is enforced in parse_seller_response(). Is that the right place? What are the alternatives?"
- "How would you test whether the buyer agent behaves correctly? What would you mock?"
- "Our ADK version doesn't use LangGraph at all. Could you add LangGraph to orchestrate ADK agents? Why might you want to?"

---

## COMMON ISSUES AND FIXES

### "ModuleNotFoundError: No module named 'm3_langgraph_multiagents'"
```bash
# Must run from negotiation_workshop/ directory
cd path/to/negotiation_workshop
python m3_langgraph_multiagents/main_langgraph_multiagent.py
```

### "OPENAI_API_KEY not set"
```bash
source .env              # bash/zsh
set -a; source .env; set +a    # if .env doesn't export automatically
```

### Model returns malformed JSON (ADK version)
`_extract_json()` tries 4 strategies. If all fail, you see:
```
[ADK Messaging] Warning: Could not parse seller JSON response
```
This is intentional — fallback counter at $475K is returned and negotiation continues.
Shows why production systems need defensive parsing. Good teaching moment.

### "GitHub MCP server not found" (npx error)
```bash
node --version      # must be 18+
npx --version       # must work
# If npx cache is stale:
npx clear-npx-cache
```

### Exercise 12 fails with provider quota / rate-limit errors
This usually means provider quota is exhausted for the active project.

```bash
# Retry later, or use a key/project with available quota.
# The script now exits with a clear quota message.
python exercises/code_solutions/ex12_support_triage_adk_runner.py
```

### Windows Unicode errors in baseline
```bash
set PYTHONIOENCODING=utf-8
python m1_baseline/naive_negotiation.py
```

### Tests fail with ImportError
```bash
cd negotiation_workshop   # must be in workshop root
pytest tests/ -v
```

---

## KEY CONCEPTS CHEAT SHEET

| Concept | One-line Definition | Where in Code |
|---------|-------------------|---------------|
| MCP | Standard protocol for agent ↔ external tool (3 operations: list, schema, call) | `m2_mcp/` |
| A2A (workshop) | Structured JSON envelopes exchanged over HTTP JSON-RPC between buyer and seller agents | `m4_adk_multiagents/a2a_protocol_http_orchestrator.py`, `m4_adk_multiagents/a2a_protocol_seller_server.py` |
| A2A (bonus demo) | True networked A2A protocol server (Agent Card + JSON-RPC via a2a-sdk) | `m4_adk_multiagents/a2a_protocol_seller_server.py` + `a2a_protocol_buyer_client_demo.py` |
| FSM | Termination guaranteed by empty transition sets on terminal states | `m1_baseline/state_machine.py` |
| LangGraph StateGraph | Declarative workflow graph with shared state and conditional routing | `m3_langgraph_multiagents/langgraph_flow.py` |
| Annotated reducer | Append-not-overwrite pattern for lists in LangGraph state | `langgraph_flow.py` line ~110 |
| LlmAgent | ADK's agent object: model + instruction + tools (not a running process) | `m4_adk_multiagents/buyer_adk.py` |
| MCPToolset | Connects to MCP server, discovers tools, converts to model function schemas | `m4_adk_multiagents/buyer_adk.py` |
| Runner | Executes ADK agent turns, returns async event stream | `m4_adk_multiagents/buyer_adk.py` |
| InMemorySessionService | ADK's per-agent conversation memory | `m4_adk_multiagents/buyer_adk.py` |
| Information Asymmetry | Seller knows its floor via inventory server; buyer infers from market data | `m2_mcp/inventory_server.py` |
| Context manager | Ensures MCP subprocess cleanup even on error | `m4_adk_multiagents/buyer_adk.py` `__aenter__`/`__aexit__` |

---

## ARCHITECTURE DIAGRAM (for whiteboard)

```
                    WORKSHOP ARCHITECTURE
                    =====================

MODULE 2: MCP          MODULE 3: AGENTS     MODULE 3: ORCHESTRATION
─────────────────      ───────────────      ──────────────────────

External Data           Buyer Agent          LangGraph StateGraph
┌─────────────┐         ┌──────────┐         ┌────────────────────┐
│  pricing    │ tools   │ GPT-4o / │  A2A    │ START              │
│  server     │◄────────│ OpenAI   │─────────► buyer_node         │
└─────────────┘         │          │         │   |                │
                        │  OFFER   │         │   v                │
External Data           └──────────┘         │ seller_node        │
┌─────────────┐                              │   |        |       │
│  pricing +  │ tools   ┌──────────┐         │ loop      END      │
│  inventory  │◄────────│ GPT-4o / │◄────────└────────────────────┘
│  server     │         │ OpenAI   │  A2A
└─────────────┘         │          │
                        │  COUNTER │
                        └──────────┘
                         Seller Agent

MODULE 4: TRUE A2A PROTOCOL — NETWORKED AGENTS
──────────────────────────────────────────────
Terminal 1: a2a_protocol_seller_server.py   (HTTP server, port 9102)
  [Agent Card at /.well-known/agent-card.json]
  [SellerAgentADK: OpenAI + MCPToolset (pricing + inventory)]

Terminal 2: a2a_protocol_buyer_client_demo.py
  [BuyerAgentADK: OpenAI + MCPToolset (pricing only)]
       |
      | 1. make offer via ADK (OpenAI + MCP)
       | 2. A2ACardResolver.get_agent_card()  -> GET /.well-known/agent-card.json
       | 3. A2AClient.send_message()          -> POST / (message/send JSON-RPC)
       | 4. receive counter-offer in response <-

BONUS (in-process, no network):
  bonus/main_adk_multiagent.py — same ADK agents, manual loop, no A2A protocol

MODULE 1: BASELINE (shows what breaks WITHOUT modules 2-4)
```

---

## TIMING NOTES FOR REPEAT SESSIONS

- **If running long on M2 (GitHub demo):** Skip the wire protocol section (Section 3 above). Jump straight from conceptual framing to the live demo.
- **If running long on M3 (LangGraph):** Skip Part A (philosophy). Go straight to code walkthrough. The code speaks for itself.
- **If running long on M4 (A2A):** Skip Part B (ADK backing layer detail) entirely — just say "ADK agents = OpenAI + MCPToolset" and move straight to the server and client walkthroughs. The A2A protocol itself is the key insight, not ADK internals.
- **2-hour condensed version:** M1 Part 1 (15 min) + M2 GitHub demo (25 min) + M3 run only (30 min) + M4 compare (25 min) + Q&A (25 min). Skip M1 Part 2, M2 custom servers, and all deep dives.
- Negotiation outcomes are non-deterministic — run twice if the first run is uninteresting.
- Costs vary by provider and plan. For workshops, keep prompts short and rounds low to control spend.
