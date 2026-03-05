# Instructor Guide — Real Estate Negotiation Simulator Workshop
## 4-Hour Workshop Flow Script

---

## BEFORE THE SESSION (30 min prep)

### Environment Setup
```bash
cd negotiation_workshop
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — add your OPENAI_API_KEY and GOOGLE_API_KEY
```

### Verify everything works before participants arrive
```bash
python m1_baseline/state_machine.py        # Should print FSM demo, no API key
python m1_baseline/naive_negotiation.py    # Should fail loudly (that's the point)
pytest tests/ -v                           # All tests should pass, no API keys needed
python main_simple.py --rounds 2           # Quick smoke test with OpenAI
python main_adk.py --rounds 1             # Quick smoke test with Gemini
```

### What to have on screen when participants arrive
- Terminal open in `negotiation_workshop/`
- This guide visible in a second window
- README.md open showing architecture diagram

---

## WORKSHOP SCHEDULE OVERVIEW

| Time        | Module | Topic                                        | Key Command / File                              |
|-------------|--------|----------------------------------------------|-------------------------------------------------|
| 0:00–0:15   | Intro  | What we're building + architecture overview  | Show README diagram                             |
| 0:15–0:40   | M1     | Why naive AI agents break (demo)             | `python m1_baseline/naive_negotiation.py`       |
| 0:40–1:05   | M1     | FSM: the termination fix                     | `python m1_baseline/state_machine.py`           |
| 1:05–1:50   | M2     | MCP deep dive: protocol + GitHub live demo   | `python m2_mcp/github_demo_client.py`           |
| 1:50–2:05   | Break  | —                                            | —                                               |
| 2:05–2:25   | M2     | Custom MCP servers + information asymmetry   | Walk `m2_mcp/pricing_server.py`                 |
| 2:25–3:10   | M3     | LangGraph deep dive + full run               | `m3_agents/langgraph_flow.py`, `main_simple.py` |
| 3:10–3:50   | M4     | Google ADK deep dive + full run              | `m4_adk/buyer_adk.py`, `main_adk.py`           |
| 3:50–4:00   | Wrap   | Exercises + Q&A                              | `exercises/exercises.md`                        |

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
> then Gemini + Google ADK. Same negotiation, same MCP servers, different frameworks."

**SHOW:** README.md — architecture diagram.

**KEY TALKING POINTS:**
- Every layer of the architecture solves a specific failure mode from the naive version
- MCP = agent ↔ external data. A2A = agent ↔ agent. LangGraph = workflow orchestration.
- Why real estate: concrete domain, clear adversarial agents, obvious information asymmetry

---

### MODULE 1 — Part 1 (0:15–0:40): "Why Naive AI Agents Break"

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

### MODULE 1 — Part 2 (0:40–1:05): "The FSM Fix"

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

### MODULE 2 — Part 1 (1:05–1:50): "MCP Deep Dive + GitHub Live Demo"

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
  1. [MCP]  call get_market_price()      → pricing_server.py
  2. [MCP]  call calculate_discount()    → pricing_server.py
  3. Reason about the data with GPT-4o/Gemini
  4. [A2A]  send OFFER message           → seller agent
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

**Run the A2A tests to show validation:**
```bash
pytest tests/test_a2a.py -v
```

> "The A2A bus is a state machine over message types — same FSM concept from Module 1.
> You can't respond to an ACCEPT because VALID_RESPONSES['ACCEPT'] is an empty list."

---

### BREAK (1:50–2:05)

Leave `m2_mcp/pricing_server.py` open. Terminal ready.

---

### MODULE 2 — Part 2 (2:05–2:25): "Custom MCP Servers"

**SAY:**
> "The GitHub demo showed us what a published MCP server looks like.
> Now we look at our own — and how a simple design choice creates information asymmetry."

#### Walk through `m2_mcp/pricing_server.py` — highlight the @mcp.tool() decorator

```python
@mcp.tool()
async def get_market_price(address: str, property_type: str) -> str:
    """Get current market price and comparable sales for a property."""
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

### MODULE 3 (2:25–3:10): "LangGraph Deep Dive + Full Simple Version"

This is the most complex module. Take it in three parts.

#### Part A: Why orchestration? (2:25–2:35) — 10 min

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

#### Part B: LangGraph code walkthrough (2:35–2:55) — 20 min

Open `m3_agents/langgraph_flow.py`.

**1. The State — 5 min**

```python
class NegotiationState(dict):
    # buyer, seller, bus, round, status, agreed_price, message_history
```

> "This dict is the SINGLE source of truth for the entire negotiation.
> Every node reads from it. Every node writes to it.
> No global variables. No passing objects between functions.
> The state flows through the graph."

**Point to the Annotated reducer pattern:**
```python
# Conceptually what's happening with message history:
message_history: Annotated[list[A2AMessage], operator.add]
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
async def buyer_node(state: NegotiationState) -> dict:
    buyer = state["buyer"]
    bus = state["bus"]
    ...
    message = await buyer.make_offer(...)
    bus.send(message)
    return {"round": state["round"] + 1, "status": bus.get_outcome()}
```

> "Notice: the node takes state, does work, returns a partial state update.
> LangGraph merges the returned dict into the existing state.
> The node doesn't know about other nodes. It just reads state and returns updates.
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
def route_after_seller(state: NegotiationState) -> Literal["buyer", "end"]:
    status = state.get("status", "negotiating")
    if status in ("agreed", "buyer_walked", "seller_rejected", "deadlocked", "error"):
        return "end"
    if state.get("round", 0) >= state.get("max_rounds", 5):
        return "end"
    return "buyer"
```

> "This is the FSM translated into LangGraph. Every terminal status routes to 'end'.
> 'end' maps to the END constant — a special node with no outgoing edges.
> The graph CANNOT leave END. Termination guaranteed at the workflow level."

**Show how the graph is assembled:**
```python
graph = StateGraph(NegotiationState)
graph.add_node("buyer", buyer_node)
graph.add_node("seller", seller_node)
graph.add_edge(START, "buyer")
graph.add_conditional_edges("buyer", route_after_buyer, {"seller": "seller", "end": END})
graph.add_conditional_edges("seller", route_after_seller, {"buyer": "buyer", "end": END})
compiled = graph.compile()
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
    if "DEAL" in buyer_msg: break        #   route_after_buyer -> "seller" or "end"
    seller_msg = seller.respond(...)     #   seller_node(state) -> returns update
    if turn > 100: break                 #   route_after_seller -> "buyer" or "end"
```

> "LangGraph forces you to be explicit about routing. You can't accidentally forget
> to check a terminal condition. The graph structure IS the termination logic."

#### Part C: Run and observe (2:55–3:10) — 15 min

```bash
python main_simple.py
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
python main_simple.py --seller-minimum 470000 --buyer-budget 460000
```
> "No overlap zone. Watch LangGraph terminate cleanly at round 5.
> Count the lines — exactly 5 rounds, then END. No emergency exit needed."

---

### MODULE 4 (3:10–3:50): "Google ADK Deep Dive + Full Run"

This module shows how ADK changes the agent model: from explicit tool calls to autonomous tool use.

#### Part A: ADK philosophy (3:10–3:20) — 10 min

**SAY:**
> "In Module 3, WE decided when to call MCP tools:
> 'Before the LLM runs, call get_market_price, then call calculate_discount,
> then give the results to GPT-4o.'
>
> In ADK, we don't make that decision. The LLM does.
> We say: 'Here are the tools. Figure out when to use them.'
> This is a fundamentally different agent model."

**DRAW the difference:**
```
SIMPLE VERSION (explicit tool orchestration):
  Orchestrator:  "Round 1, buyer's turn"
  buyer_node:    1. call MCP get_market_price()  <- WE decide
                 2. call MCP calculate_discount() <- WE decide
                 3. call GPT-4o with results
                 4. return A2AMessage

ADK VERSION (autonomous tool use):
  Orchestrator:  "Round 1, buyer's turn"
  ADK Runner:    1. send prompt to Gemini
                 Gemini: "I need market data. I'll call get_market_price()"
                 ADK:    executes the tool call
                 Gemini: "Now I'll call calculate_discount()"
                 ADK:    executes the tool call
                 Gemini: "Based on this data, my offer is $427,000"
                 2. return response text
  buyer_agent:   3. parse text -> A2AMessage
```

> "Same outcome. Very different control flow.
> With explicit: you control the tool sequence. Predictable but rigid.
> With ADK: Gemini decides. Flexible but less predictable.
>
> Production rule of thumb: use explicit when you need reliability guarantees.
> Use ADK when the task is complex enough that the LLM should decide the tool sequence."

#### Part B: ADK components (3:20–3:35) — 15 min

Open `m4_adk/buyer_adk.py`.

**1. LlmAgent — the core agent object (3 min)**

```python
self._agent = LlmAgent(
    name="buyer_agent",
    model=GEMINI_MODEL,           # "gemini-2.0-flash"
    description="Real estate buyer agent for 742 Evergreen Terrace",
    instruction=BUYER_INSTRUCTION, # the system prompt
    tools=tools,                   # discovered from MCP server
)
```

> "LlmAgent is NOT a running process — it's a configuration object.
> Four things define an agent:
> - model: which LLM
> - instruction: system prompt / persona
> - tools: what the agent can call
> - description: how OTHER agents understand this agent (important for multi-agent)
>
> The instruction replaces our explicit BUYER_SYSTEM_PROMPT from Module 3.
> The tools replace our manual call_pricing_mcp() calls."

**2. MCPToolset — automatic tool discovery (4 min)**

```python
pricing_toolset = MCPToolset(
    connection_params=StdioServerParameters(
        command=sys.executable,
        args=[_PRICING_SERVER],     # absolute path to pricing_server.py
    )
)
tools, exit_stack = await pricing_toolset.async_init_tools()
```

> "MCPToolset does what our buyer_simple.py does manually — but automatically.
> It spawns the MCP server, runs the handshake, calls list_tools(),
> converts the tool schemas into Gemini function-calling format,
> and returns them as a list Gemini can use.
>
> The agent then gives Gemini these tools. When Gemini decides to call one,
> ADK executes the call_tool() request and feeds the result back to Gemini.
> You never write a single line of MCP client code in the agent itself."

**Show the tool names discovered:**
```python
tool_names = [t.name for t in tools if hasattr(t, 'name')]
print(f"   [Buyer ADK] Discovered MCP tools: {tool_names}")
# Output: ['get_market_price', 'calculate_discount']
```

> "These are the same tools our simple buyer calls explicitly.
> Now Gemini decides when to call them."

**3. Runner + SessionService (4 min)**

```python
self._session_service = InMemorySessionService()
self._runner = Runner(
    agent=self._agent,
    app_name=APP_NAME,
    session_service=self._session_service,
)
await self._session_service.create_session(...)
```

> "SessionService is ADK's memory. It stores the conversation history for this agent.
> Between rounds, the buyer remembers what it offered last time and what the seller countered.
> Without it: every round would be stateless — the buyer could offer less than before.
>
> InMemorySessionService = in-process memory. In production you'd use:
> DatabaseSessionService (persists to Postgres/etc.) for resumable agents."

> "Runner executes the agent. It takes the agent config + session service + app name
> and creates an execution engine. runner.run_async() returns an async generator of events:
> tool calls, tool results, partial responses, final response."

**SHOW the event loop:**
```python
async for event in self._runner.run_async(
    user_id=self.user_id,
    session_id=self.session_id,
    new_message=content,
):
    if hasattr(event, 'tool_calls') and event.tool_calls:
        # Gemini decided to call a tool — ADK is executing it
        for tc in event.tool_calls:
            print(f"   [Buyer ADK] Calling tool: {tc.function.name}(...)")

    if event.is_final_response() and event.content:
        # Gemini is done — this is the final answer
        final_response += part.text
```

> "Events arrive as Gemini reasons. You might see:
> tool_call event: get_market_price()  <- Gemini decided to call this
> tool_result event: {estimated_value: 462000, ...}
> tool_call event: calculate_discount()  <- Gemini calls a second tool
> tool_result event: {suggested_offer: 425000, ...}
> final_response event: JSON with the offer
>
> The agent loop is inside ADK. We just consume the events."

**4. Dual MCPToolsets in seller — 4 min**

Open `m4_adk/seller_adk.py`:

```python
# Pricing tools (shared with buyer)
pricing_tools, pricing_exit = await pricing_toolset.async_init_tools()

# Inventory tools (seller ONLY - has get_minimum_acceptable_price)
inventory_tools, inventory_exit = await inventory_toolset.async_init_tools()

# Merge: Gemini sees all four tools as one unified list
all_tools = list(pricing_tools) + list(inventory_tools)
```

> "The seller connects to BOTH MCP servers and merges the tool lists.
> Gemini sees all four tools — get_market_price, calculate_discount,
> get_inventory_level, AND get_minimum_acceptable_price.
>
> The buyer has no access to the last one. Same information asymmetry
> as Module 2 — controlled by which MCPToolset the agent connects to."

**5. Context manager lifecycle — 2 min**

```python
async with BuyerAgentADK(session_id=f"{session_id}_buyer") as buyer:
    async with SellerAgentADK(session_id=f"{session_id}_seller") as seller:
        # negotiation runs here
    # seller.__aexit__: MCP connections closed
# buyer.__aexit__: MCP connections closed
```

> "Both agents are async context managers. __aenter__ spawns the MCP servers.
> __aexit__ closes the connections — even if an exception occurred mid-negotiation.
> This is production-quality resource management.
> Without it: MCP subprocess orphans, file descriptor leaks."

#### Part C: Run and compare (3:35–3:50) — 15 min

```bash
python main_adk.py
```

**Watch specifically for:**
- `[Buyer ADK] Discovered MCP tools: [...]` — tool discovery happening
- `[Buyer ADK] Calling tool: get_market_price(...)` — Gemini autonomously deciding to call
- Compare: in the simple version, you saw `[Buyer] Calling MCP (pricing): get_market_price...`
  because WE told it to. Here Gemini decided.

**AFTER IT RUNS — compare with Module 3:**

| Observation | Simple Version | ADK Version |
|---|---|---|
| Who calls MCP tools? | buyer_node explicitly calls before LLM | Gemini decides mid-generation |
| Where is the loop? | LangGraph StateGraph | Manual loop in main_adk.py |
| Conversation memory | LLM messages list in BuyerAgent | ADK InMemorySessionService |
| Response format | response_format=json_object (strict) | Instruction prompt (best-effort) |
| Fallback on bad JSON | structured output guaranteed | _extract_json() 4-strategy parser |

**ASK the group — decision framework:**
> "You're building a legal document review agent. It needs to:
> - Check clause #7 for compliance
> - If non-compliant, check related clause #12
> - Based on #12, decide whether to flag or auto-approve
>
> Which would you use: explicit tool calls (simple version approach)
> or autonomous tool use (ADK approach)?"
>
> Answer: For high-stakes sequential logic — explicit. You need to audit
> exactly what data informed the decision.
> For exploratory tasks where the LLM should decide the investigation path — ADK.

**ASK:**
> "In our ADK version, what happens if Gemini doesn't call get_minimum_acceptable_price?
> The seller might counter below the floor. How does the code handle this?"
>
> Answer: parse_seller_response() in messaging_adk.py enforces the floor price.
> If the parsed counter_price < minimum_price, it corrects it.
> "Defense in depth: instruction tells Gemini to call the tool.
> Code enforces the constraint regardless. Never trust LLM output alone for hard limits."

**TRY the deadlock case on ADK:**
```bash
python main_adk.py --seller-minimum 470000 --buyer-budget 460000
```
> "Same clean termination as the LangGraph version — but implemented differently.
> NegotiationSession.is_concluded() instead of LangGraph conditional edges."

**ADK vs LangGraph — when to use which:**
```
Use LangGraph when:                       Use ADK when:
- Workflow has complex conditional        - Agent needs to decide its own
  routing you want to make explicit         tool-call sequence
- Multiple agents share state             - You want Gemini to handle
  that needs careful merging                multi-step reasoning autonomously
- You want graph-level termination        - Simpler orchestration, focus on
  guarantees (END node)                     agent behavior not workflow design
- Human-in-the-loop interrupts            - Free tier (Gemini vs GPT-4o)
  are needed
```

---

### WRAP-UP (3:50–4:00): Exercises + Q&A

```bash
start exercises/exercises.md    # Windows
open exercises/exercises.md     # Mac
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

**Q&A prompts if the group is quiet:**
- "If you had to add a third agent — a real estate attorney who reviews the final deal — where would it go in the LangGraph graph?"
- "The seller's floor price is enforced in parse_seller_response(). Is that the right place? What are the alternatives?"
- "How would you test whether the buyer agent behaves correctly? What would you mock?"
- "Our ADK version doesn't use LangGraph at all. Could you add LangGraph to orchestrate ADK agents? Why might you want to?"

---

## COMMON ISSUES AND FIXES

### "ModuleNotFoundError: No module named 'm3_agents'"
```bash
# Must run from negotiation_workshop/ directory
cd path/to/negotiation_workshop
python main_simple.py
```

### "OPENAI_API_KEY not set"
```bash
source .env              # bash/zsh
set -a; source .env; set +a    # if .env doesn't export automatically
```

### Gemini returns malformed JSON (ADK version)
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
| A2A | Structured agent ↔ agent messaging with state machine validation | `m3_agents/a2a_simple.py` |
| FSM | Termination guaranteed by empty transition sets on terminal states | `m1_baseline/state_machine.py` |
| LangGraph StateGraph | Declarative workflow graph with shared state and conditional routing | `m3_agents/langgraph_flow.py` |
| Annotated reducer | Append-not-overwrite pattern for lists in LangGraph state | `langgraph_flow.py` line ~110 |
| LlmAgent | ADK's agent object: model + instruction + tools (not a running process) | `m4_adk/buyer_adk.py` |
| MCPToolset | Connects to MCP server, discovers tools, converts to Gemini function schemas | `m4_adk/buyer_adk.py` |
| Runner | Executes ADK agent turns, returns async event stream | `m4_adk/buyer_adk.py` |
| InMemorySessionService | ADK's per-agent conversation memory | `m4_adk/buyer_adk.py` |
| Information Asymmetry | Seller knows its floor via inventory server; buyer infers from market data | `m2_mcp/inventory_server.py` |
| Context manager | Ensures MCP subprocess cleanup even on error | `m4_adk/buyer_adk.py` `__aenter__`/`__aexit__` |

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
│  server     │◄────────│ Gemini   │─────────► buyer_node         │
└─────────────┘         │          │         │   |                │
                        │  OFFER   │         │   v                │
External Data           └──────────┘         │ seller_node        │
┌─────────────┐                              │   |        |       │
│  pricing +  │ tools   ┌──────────┐         │ loop      END      │
│  inventory  │◄────────│ GPT-4o / │◄────────└────────────────────┘
│  server     │         │ Gemini   │  A2A
└─────────────┘         │          │
                        │  COUNTER │
                        └──────────┘
                         Seller Agent

MODULE 4: SAME AGENTS, ADK INSTEAD OF EXPLICIT TOOL CALLS
─────────────────────────────────────────────────────────
MCPToolset auto-discovers tools -> Gemini decides when to call them
Manual orchestration loop in main_adk.py instead of LangGraph StateGraph

MODULE 1: BASELINE (shows what breaks WITHOUT modules 2-4)
```

---

## TIMING NOTES FOR REPEAT SESSIONS

- **If running long on M2 (GitHub demo):** Skip the wire protocol section (Section 3 above). Jump straight from conceptual framing to the live demo.
- **If running long on M3 (LangGraph):** Skip Part A (philosophy). Go straight to code walkthrough. The code speaks for itself.
- **If running long on M4 (ADK):** Skip Part B items 3-4 (Runner/SessionService and dual MCPToolsets). Focus on the explicit vs autonomous tool call comparison — that's the key insight.
- **2-hour condensed version:** M1 Part 1 (15 min) + M2 GitHub demo (25 min) + M3 run only (30 min) + M4 compare (25 min) + Q&A (25 min). Skip M1 Part 2, M2 custom servers, and all deep dives.
- Negotiation outcomes are non-deterministic — run twice if the first run is uninteresting.
- GPT-4o is ~10x more expensive per token than Gemini free tier. Steer budget-conscious participants to the ADK version for experimentation.
