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
python m1_baseline/state_machine.py        # Should print FSM demo, no API key needed
python m1_baseline/naive_negotiation.py    # Requires OPENAI_API_KEY — Demo 1 should close ~$453K in 3 turns; Demo 2 should run 8 turns (demo cap; production default is 100) then emergency exit
pytest tests/ -v                           # All tests should pass, no API keys needed
python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102
python m3_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 1
```

### What to have on screen when participants arrive
- Terminal open in `negotiation_workshop/`
- This guide visible in a second window
- README.md open showing architecture diagram

### Opening repo structure callout (first 2–3 min)

At the start of the workshop, explicitly orient learners to the repo layout:

- Each module folder (`m1_baseline/`, `m2_mcp/`, `m3_adk_multiagents/`) has its own `README.md`.
- That module `README.md` explains what the module demonstrates and how to run it.
- Each module includes `exercises/` (learner tasks) and `solution/` (worked answers with code changes).
- Each module also has a `notes/` folder for deeper conceptual material.
- Modules 2 and 3 also ship a `demos/` folder of small, single-purpose runnable scripts that crack open the protocols on the wire (handshake bytes, task lifecycle, ADK workflow agents). Pair them with the `notes/` reference docs.
- Encourage participants to treat module `README.md` as the runbook and `notes/` + `demos/` as the reference and exploration sandbox.

---

## WORKSHOP SCHEDULE OVERVIEW

| Time        | Module | Topic                                                              | Key Command / File                              |
|-------------|--------|--------------------------------------------------------------------|-------------------------------------------------|
| 0:00–0:15   | Intro  | What we're building + architecture overview                        | Show README diagram                             |
| 0:15–0:30   | M1     | Why naive AI agents break (demo)                                   | `python m1_baseline/naive_negotiation.py`       |
| 0:30–0:45   | M1     | FSM: the termination fix                                           | `python m1_baseline/state_machine.py`           |
| 0:45–1:30   | M2     | MCP deep dive: protocol internals + GitHub live demo               | `python m2_mcp/github_agent_client.py`           |
| 1:30–1:45   | Break  | —                                                                  | —                                               |
| 1:45–2:30   | M2     | MCP primitives, transports, security + custom servers              | `m2_mcp/notes/mcp_deep_dive.md`, `m2_mcp/pricing_server.py` |
| 2:30–3:15   | M3     | Google ADK deep dive: LlmAgent, workflow agents, sessions, callbacks | `m3_adk_multiagents/buyer_adk.py`, `m3_adk_multiagents/seller_adk.py`, `m3_adk_multiagents/notes/google_adk_overview.md` |
| 3:15–3:50   | M3     | A2A protocol: Agent Card, JSON-RPC, task lifecycle, streaming      | `m3_adk_multiagents/a2a_protocol_seller_server.py`, `m3_adk_multiagents/a2a_protocol_http_orchestrator.py` |
| 3:50–4:00   | Wrap   | Exercises + Q&A                                                    | `m1_baseline/exercises/`, `m2_mcp/exercises/`, `m3_adk_multiagents/exercises/` |

### Note Mapping

Notes live inside each module's `notes/` subfolder.

| Module | Notes location |
|---|---|
| M1 | `m1_baseline/notes/agents_fundamentals.md` |
| M2 | `m2_mcp/notes/mcp_deep_dive.md` |
| M3 | `m3_adk_multiagents/notes/a2a_protocols.md` |
| M3 | `m3_adk_multiagents/notes/adk_quick_reference.md` |
| M3 | `m3_adk_multiagents/notes/google_adk_overview.md` |

---

## PRE-CODE CONCEPT PRIMER (M2 + M3)

Use this as a 8–12 minute primer before opening Module 2 deep dive and Module 3 code.

### Shared baseline (teach before both modules)

- Agent = **model + tools + memory + control flow + termination logic**
- MCP = agent ↔ external tools/data; A2A = agent ↔ agent communication
- Orchestration is separate from both MCP and A2A (it controls turn-taking and stopping)
- Negotiation state vocabulary: round, status, terminal outcomes (`agreed`, `deadlocked`, `buyer_walked`, `seller_rejected`)
- Bounded loops and terminal checks are non-negotiable in production systems

### MCP concepts to introduce before the M2 deep dive

1. Protocol internals
  - JSON-RPC 2.0 envelope (`id`, `method`, `params`, `result` / `error`)
  - Initialize handshake, capability negotiation, lifecycle

2. Tool calling loop
  - `tools/list` → model picks → `tools/call` → result back into context → loop

3. Primitives: Tools, Resources, Prompts
  - Tools = side-effecting actions invoked by the model
  - Resources = read-only context the host fetches
  - Prompts = parameterized templates the host can pin

4. Content types
  - `TextContent`, `ImageContent`, embedded resources, structured content

5. Transports
  - stdio (local subprocess), SSE / streamable HTTP (remote)

6. Security and authentication
  - Auth headers on HTTP transports, OAuth flows for hosted servers
  - Trust boundaries: who can call which tools

7. Client- and server-side patterns
  - Server: `@mcp.tool()` registration, error envelopes
  - Client: dynamic discovery, allowlisting, retry semantics

### Google ADK concepts to introduce before showing Module 3 code

1. ADK runtime primitives
  - `LlmAgent` (agent definition)
  - `Runner` (executes turns)
  - `SessionService` (state/memory across turns)

2. Workflow agents (key new content)
  - `SequentialAgent`, `ParallelAgent`, `LoopAgent`
  - When to compose with sub_agents vs orchestrate over A2A

3. Tool abstraction via `MCPToolset`
  - Tool discovery and execution loop handled by ADK
  - Model decides when to call tools
  - `ToolContext` gives tools access to session state

4. Session memory and state deltas
  - Per-session continuity, `EventActions(stateDelta=...)`
  - Event stream as the observability backbone

5. Callbacks
  - `before_model`, `after_model`, `before_tool`, `after_tool`
  - Use cases: redaction, guardrails, human-in-the-loop

6. Provider model clarity (important for this workshop)
  - Google ADK is a framework layer
  - In this repo, ADK uses OpenAI model IDs (`openai/gpt-4o`)

7. Protocol boundary discipline
  - Strict JSON envelopes at A2A boundary
  - Parse/validate early; fail fast on malformed payloads

### A2A concepts to introduce before showing Module 3 code

1. JSON-RPC message structure (`message/send`, `message/stream`, `tasks/get`, `tasks/cancel`)
2. Task lifecycle states (`submitted` → `working` → `input-required` → `completed` / `failed` / `canceled`)
3. `Message`, `Part` (TextPart / FilePart / DataPart), and `Artifact` distinction
4. Streaming: SSE event types and partial updates
5. Context IDs and threading across turns
6. Agent Card schema depth: skills, capabilities, security schemes
7. Authentication: Bearer, OAuth2, mTLS
8. A2A ↔ MCP relationship: A2A often wraps MCP-using agents; MCP is for tools, A2A is for peer agents

### While showing Module 3 code (teaching flow)

1. Start at the network boundary first
  - Agent Card discovery (`/.well-known/agent-card.json`)
  - HTTP JSON-RPC `message/send`
  - Envelope contract and task lifecycle

2. Then show ADK internals
  - buyer/seller ADK agent setup
  - MCP tool usage via `MCPToolset`
  - session state continuity and event stream

3. Emphasize decoupling
  - No shared in-process state between buyer/seller
  - Interop via protocol contract, not imports

### Suggested mini-sequence (if learners need extra framing)

- 3–4 min: MCP vs A2A vs orchestration recap
- 4–5 min: ADK runtime + workflow agents + provider model clarification
- 4–5 min: A2A task lifecycle + Agent Card walkthrough
- Then open code and map each concept directly to concrete lines

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
> We're building this progressively across three modules so you can see two
> implementation styles: a broken naive baseline, then a production-style
> stack — OpenAI + Google ADK over the A2A protocol. Same negotiation,
> same MCP servers, two levels of rigor."

**EXPLAIN CLEARLY WHAT EACH MODULE DOES (say this explicitly):**
- **Module 1 (`m1_baseline/`)**: intentionally naive baseline that exposes failure modes (fragile parsing, weak stopping logic), then introduces FSM-based termination guarantees.
- **Module 2 (`m2_mcp/`)**: adds MCP so agents can call external tools for real data (pricing/inventory) instead of relying on hardcoded prompt knowledge — with a deep dive on protocol internals, primitives, transports, and security.
- **Module 3 (`m3_adk_multiagents/`)**: builds the buyer and seller using Google ADK (LlmAgent, workflow agents, sessions, callbacks, MCPToolset) and exposes them over networked A2A (Agent Card discovery, JSON-RPC `message/send`, task lifecycle, streaming).

**SHOW:** README.md — architecture diagram.

**KEY TALKING POINTS:**
- Every layer of the architecture solves a specific failure mode from the naive version
- MCP = agent ↔ external tools/data. A2A = agent ↔ agent. ADK = the agent framework that runs both sides.
- Google ADK is the agent framework (not a Gemini-only wrapper). In this workshop's ADK code, we use OpenAI models (`openai/gpt-4o`).
- Why real estate: concrete domain, clear adversarial agents, obvious information asymmetry

---

### MODULE 1 — Part 1 (0:15–0:30): "Why Naive AI Agents Break"

```bash
python m1_baseline/naive_negotiation.py
```

**SAY before running:**
> "This is what most people build first. It uses a real LLM — GPT-4o —
> but with no schema, no state machine, just raw strings and a regex parser.
> Watch what happens."

**WATCH FOR:**
- Demo 1: Closes in ~3 turns at ~$453K — looks fine. But it only worked because the LLM happened to write the price in a format the regex could grab
- Demo 2: RUNS 8 TURNS (demo cap) on an impossible agreement — buyer max $420K, seller min $450K, they can NEVER agree. Every call is wasted. In production the cap is 100 turns.
- Demo 3: The 10 failure modes with concrete examples — no LLM needed, purely deterministic bugs

**SAY after Demo 2:**
> "8 turns in this demo. In production the emergency exit is at 100 turns —
> potentially $1+ in API costs for a negotiation that was doomed from round 1.
> And there is no mathematical guarantee it stops. The 'while True' is the problem."

**WALK THROUGH the code:**
```python
while True:                                      # no guarantee of termination
    if "DEAL" in current_message.upper():        # string matching — "deal-breaker" triggers this!
    if turn > max_turns: break                   # emergency exit, not a proof
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
> "Google ADK has a `LoopAgent` whose body keeps running until a terminal signal is set in session state.
> Does that structure look familiar?"
> (Answer: it's the same FSM termination guarantee, applied at the agent-orchestration level. Preview for Module 3.)

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
python m2_mcp/github_agent_client.py
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

> "These tests validate the FSM termination guarantee from Module 1 — the same guarantee
> that ADK's `LoopAgent` provides at the agent-orchestration level."

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

### MODULE 2 DEEP DIVE (1:45–2:30): "MCP Internals, Primitives, Transports, Security"

The reallocated 45-minute slot from the removed LangGraph module. Use this time
to take learners through `m2_mcp/notes/mcp_deep_dive.md` and the live servers in
`m2_mcp/pricing_server.py` and `m2_mcp/inventory_server.py`.

#### Part A: Tool calling loop + protocol internals (1:45–2:00) — 15 min

**SAY:**
> "MCP gives the model three operations: list tools, get a schema, call a tool.
> The agent loop is: model emits a tool call → host runs it on the MCP server
> → result goes back to the model → repeat until the model returns a final answer."

Walk through one full request/response on the wire:
1. Client startup: `initialize` handshake (capabilities + protocol version)
2. `tools/list` — server returns JSON schemas for every tool
3. Model emits a function call → host translates to `tools/call`
4. Server returns a `CallToolResult` (text/image/resource content blocks)
5. Host hands result back to the model

Open `m2_mcp/pricing_server.py` and trace one `@mcp.tool()` decorator end-to-end.

**Live deep-dive demos (run as you narrate — these print the wire frames):**

```bash
python m2_mcp/demos/01_initialize_handshake.py   # raw JSON-RPC handshake bytes
python m2_mcp/demos/02_tool_loop_trace.py        # narrated model ↔ host ↔ server loop with timestamps
```

> "Demo 01 prints the four `initialize` / `tools/list` frames you just saw on the whiteboard —
> with no SDK in the way. Demo 02 then layers OpenAI function calling on top so you can see
> exactly when the model decides to call a tool and when it stops."

#### Part B: Primitives — Tools, Resources, Prompts (2:00–2:10) — 10 min

**SAY:**
> "MCP has three primitive types. We use Tools heavily. Resources are read-only
> data the agent can fetch (think: documents, files). Prompts are server-supplied
> templates the agent can request. Knowing all three matters even if today we only ship Tools."

Show the difference using `m2_mcp/notes/mcp_deep_dive.md`. Whiteboard a comparison table:
| Primitive | Direction | Example |
|-----------|-----------|---------|
| Tool      | Model invokes | `get_price_estimate(...)` |
| Resource  | Model reads   | `inventory://floor-prices` |
| Prompt    | Model requests | `negotiation-tactics` |

**Live deep-dive demos:**

```bash
python m2_mcp/demos/03_list_all_primitives.py   # lists Tools, Resources, and Prompts from both servers
python m2_mcp/demos/04_content_types.py         # text / image / embedded resource content blocks
```

> "Demo 03 proves our own servers ship more than just tools — the inventory server now exposes a Resource
> and the pricing server exposes a Prompt. Demo 04 shows the JSON shape of every content-block kind
> using a tiny inline server."

#### Part C: Transports — stdio vs SSE vs HTTP (2:10–2:20) — 10 min

**SAY:**
> "Transport is independent of the protocol. Same `tools/call` JSON works over a
> subprocess pipe (stdio), an SSE stream, or plain HTTP. Pick based on deployment."

- **stdio** — what we use locally; subprocess + JSON-RPC over stdin/stdout
- **SSE** — `m2_mcp/sse_agent_client.py` shows a streaming HTTP variant
- **Streamable HTTP / HTTP** — for hosted/multi-tenant servers

Run the SSE client briefly so they see a different transport delivering the same protocol.

**Live deep-dive demo (Streamable HTTP):**

```bash
# Terminal 1
python m2_mcp/demos/05_streamable_http_transport.py --serve --port 8765
# Terminal 2
python m2_mcp/demos/05_streamable_http_transport.py --client --port 8765
```

> "This is the spec's recommended replacement for raw SSE — same MCP protocol, HTTP transport,
> identical client code from the model's point of view."

#### Part D: Security, auth, client/server patterns (2:20–2:30) — 10 min

**SAY:**
> "MCP servers run with the credentials of the host. There is no built-in auth
> between model and server — the host is responsible for sandboxing, rate limits,
> tool allowlisting, and credential injection."

Cover:
- Tool allowlisting (which tools a given agent is allowed to call)
- Credential injection patterns (env vars vs OAuth-passthrough)
- Information asymmetry by design: buyer host gets pricing only; seller host gets pricing + inventory
- Pattern: one server per data domain → compose multiple via `MCPToolset` later in M3

**ASK:**
> "If the seller's inventory server were exposed over HTTP instead of stdio,
> what's the first security control you would add?"
> (Answer: authentication on the transport — bearer token, mTLS, or OAuth — plus per-tool authorization.)

---

### MODULE 3 ADK DEEP DIVE (2:30–3:15): "Google ADK — LlmAgent, Workflow Agents, Sessions"

The other half of the reallocated time. Cover Google ADK as a framework before
showing it carry the buyer/seller in the next slot.

#### Part A: ADK mental model (2:30–2:40) — 10 min

**SAY:**
> "ADK is Google's agent framework. It is model-agnostic — we configure it to use
> OpenAI `gpt-4o`, not Gemini. The unit of composition is `LlmAgent` (model +
> instruction + tools). The runtime is `Runner` (executes turns, emits events).
> The memory is `SessionService` (per-conversation state)."

Open `m3_adk_multiagents/notes/google_adk_overview.md` and walk the ecosystem diagram.

```python
# Raw Python approach
buyer_response = buyer_agent(initial_prompt)
seller_response = seller_agent(buyer_response)
buyer_response = buyer_agent(seller_response)
# ... repeat manually
```

Whiteboard:
```
                ADK MENTAL MODEL
                ================
LlmAgent  (model + instruction + tools, declarative)
   |
   v
Runner    (executes turns, emits events: text, tool_call, tool_result)
   |
   v
Session   (per-conversation state, owned by SessionService)

Workflow agents = LlmAgents composed:
   SequentialAgent  -> agents run in order, share session state
   ParallelAgent    -> agents fan out concurrently, results merged
   LoopAgent        -> body re-runs until a terminal signal in state
```

#### Part B: LlmAgent + MCPToolset code walkthrough (2:40–2:55) — 15 min

Open `m3_adk_multiagents/buyer_adk.py`. Walk:
1. `MCPToolset(StdioServerParameters(...))` — auto-discovers tools, no hand-rolled `tools/list`/`tools/call` plumbing.
2. `LlmAgent(model="openai/gpt-4o", instruction=BUYER_INSTRUCTION_TEMPLATE, tools=[pricing_toolset])` — declarative.
3. `InMemorySessionService` + `Runner.run_async(...)` — the actual execution loop.
4. The async event stream — `event.is_final_response()`, `event.content.parts[*].text`.
5. `__aenter__` / `__aexit__` — guarantees MCP subprocess cleanup.

Then open `m3_adk_multiagents/seller_adk.py` and contrast: **two** MCPToolsets (pricing + inventory) merged into one tools list. Same pattern, more data access.

#### Part C: Workflow agents, callbacks, ToolContext (2:55–3:10) — 15 min

Open `m3_adk_multiagents/notes/google_adk_overview.md` and `notes/adk_quick_reference.md`.

Cover:
- **`SequentialAgent`** — pipeline of sub-agents (e.g., research → draft → review).
- **`ParallelAgent`** — fan out N agents, gather results.
- **`LoopAgent`** — iterate until a sub-agent sets a termination key in session state. *This is the ADK analogue of the FSM termination guarantee from Module 1.*
- **`ToolContext`** — what a tool receives at call time: session state, invocation ID, callable for emitting intermediate events.
- **Callbacks** — `before_model_callback`, `after_tool_callback`, etc. Where you put PII redaction, audit logging, cost guards.
- **Events** — every Runner step emits an event; that's how UIs stream partial output.
- **Auth** — credential injection via `ToolContext` and the OAuth flows ADK ships.

**Live deep-dive demos (each is a single self-contained script — no seller server needed):**

```bash
python m3_adk_multiagents/demos/06_sequential_agent.py    # market_brief → offer_drafter → message_polisher
python m3_adk_multiagents/demos/07_parallel_agent.py      # fan-out into different state keys
python m3_adk_multiagents/demos/08_loop_agent.py          # haggler + judge; judge escalates to break the loop
python m3_adk_multiagents/demos/09_agent_as_tool.py       # AgentTool: wrap an agent as a callable tool
python m3_adk_multiagents/demos/10_tool_context.py        # ToolContext: scoped session state across turns
python m3_adk_multiagents/demos/11_callbacks.py           # before_model PII redact + before_tool allowlist + after_tool log
```

> "Run any one or two of these as a live demo — they each isolate one ADK primitive so learners
> can see the building blocks before reading `buyer_adk.py` / `seller_adk.py` where everything
> is composed together."

**ASK:**
> "Where in this architecture would you enforce a per-agent budget cap (max dollars of LLM spend per session)?"
> (Answer: a `before_model_callback` that reads cost from session state and aborts the turn if exceeded.)

#### Part D: Set up for A2A (3:10–3:15) — 5 min

Transition: "Now we wrap these ADK agents behind A2A so they can run as independent network services."

---

### MODULE 3 A2A (3:15–3:50): "True A2A Protocol — Networked Agents"

This module shows what production multi-agent systems look like: two agents running
as independent HTTP services, communicating over the A2A protocol standard.

**THE BIG PICTURE:**
> "Up to this point both ADK agents lived in the same Python process.
> The buyer called the seller like a function.
> In the real world, agents run on different machines, owned by different teams,
> possibly written in different languages.
> The A2A protocol is the standard that makes that possible.
> This module shows the exact same negotiation — but now the seller is an HTTP server
> and the buyer calls it over the network."

**IMPORTANT CLARIFICATION (say this explicitly):**
> "Google ADK is the framework layer. It can run different LLM providers.
> In our code here, ADK is configured to use OpenAI (`openai/gpt-4o`) — not Gemini."

**DRAW the architecture shift:**
```
IN-PROCESS BASELINE (same process):
  one Python script runs both ADK agents
    buyer_runner ----calls----> seller_runner
    (function call — same memory, same machine)

NETWORKED A2A:
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

Open `m3_adk_multiagents/buyer_adk.py` and `m3_adk_multiagents/seller_adk.py`.

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
    instruction=buyer_instruction,   # built dynamically from discovered tool names
    tools=tools,   # model can now call MCP tools autonomously
)
```

> "MCPToolset replaces all the manual `stdio_client` / `call_tool` plumbing you'd write by hand.
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

Open `m3_adk_multiagents/a2a_protocol_seller_server.py`.

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

Open `m3_adk_multiagents/a2a_protocol_buyer_client_demo.py`.

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
> "In a naive in-process design, the buyer and seller would share a single Python state dict.
> In Module 3, what does the buyer know about the seller's internal state?"
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
python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102
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
python m3_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 5
```

**Optional single-turn demo:**
```bash
python m3_adk_multiagents/a2a_protocol_buyer_client_demo.py --seller-url http://127.0.0.1:9102
```

**Live deep-dive demos against the same running seller server (any subset — each prints the raw A2A wire shape):**

```bash
python m3_adk_multiagents/demos/01_handcraft_message_send.py --seller-url http://127.0.0.1:9102   # JSON-RPC body by hand, no A2A SDK
python m3_adk_multiagents/demos/02_task_lifecycle.py        --seller-url http://127.0.0.1:9102   # submitted → working → completed/failed
python m3_adk_multiagents/demos/03_parts_and_artifacts.py   --seller-url http://127.0.0.1:9102   # multi-part Message + negotiation-summary Artifact
python m3_adk_multiagents/demos/04_streaming_negotiation.py --seller-url http://127.0.0.1:9102   # message/stream incremental updates
python m3_adk_multiagents/demos/05_context_threading.py     --seller-url http://127.0.0.1:9102   # contextId reuse across rounds
```

> "Use these to make A2A concrete after the orchestrator runs — demo 01 strips away the A2A SDK so
> learners see the raw JSON-RPC body, demo 02 forces a `failed` task on purpose, and demo 04 shows
> the streaming variant the seller's Agent Card now advertises."

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
start m1_baseline/exercises                 # Windows
open m1_baseline/exercises                  # Mac
```

Then quickly point learners to all module exercise folders.

Exercises use difficulty labels: `[Starter]` (15 min), `[Core]` (30–45 min), `[Stretch]` (60+ min). Each exercise includes "What to look for" context and a reflection question.

**RECOMMENDED PATH — assign by time available:**

**If 15–20 min remaining (pick one):**
- M2 Exercise 1 `[Starter]` — Add a new MCP tool to the pricing server
- M1 Exercise 2 `[Core]` — Compare naive vs FSM failure modes (requires OPENAI_API_KEY to run naive demo; analysis/table-fill exercise)

**If 30–45 min remaining (pick two):**
- M1 Exercise 1 `[Core]` — Add a TIMEOUT terminal state to the FSM (no API keys, teaches transition tables)
- M2 Exercise 2 `[Core]` — Wire the new MCP tool into the ADK buyer agent (builds on M2 ex01)
- M3 Exercise 1 `[Core]` — Fetch and inspect the A2A Agent Card (teaches A2A discovery)

**If 45–60 min remaining (core + challenge):**
- M3 Exercise 1 `[Core]` — Fetch and inspect the A2A Agent Card (teaches A2A discovery)
- M3 Exercise 2 `[Core]` — Add a negotiation history endpoint (FastAPI + A2A server extension)

**For take-home / self-paced learners (Stretch exercises):**
- M1 Exercise 3 `[Stretch]` — Reimplement the FSM in TypeScript
- M2 Exercise 3 `[Stretch]` — Build an appraisal MCP server from scratch
- M3 Exercise 3 `[Stretch]` — Deploy seller to Docker, run networked negotiation

**Solution lookup:**
- Match each exercise with its paired file in the module's `solution/` folder.

**Prerequisites for exercises requiring API keys:**
```bash
# Ensure OPENAI_API_KEY is set for M2 ex02 and M3 exercises
source .env
```

**Q&A prompts if the group is quiet:**
- "If you had to add a third agent — a real estate attorney who reviews the final deal — how would you compose it with the existing buyer/seller? Sub-agent of a `SequentialAgent`? Separate A2A service?"
- "The seller's floor price is enforced in parse_seller_response(). Is that the right place? What are the alternatives?"
- "How would you test whether the buyer agent behaves correctly? What would you mock?"
- "Right now the buyer talks to one seller. How would you let the buyer discover and choose between multiple competing seller A2A endpoints?"

---

## COMMON ISSUES AND FIXES

### "ModuleNotFoundError: No module named 'm2_mcp'" or 'm3_adk_multiagents'
```bash
# Must run from negotiation_workshop/ directory
cd path/to/negotiation_workshop
python m3_adk_multiagents/a2a_protocol_seller_server.py
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

### Module 3 exercise run fails with provider quota / rate-limit errors
This usually means provider quota is exhausted for the active project or API key limits are reached.

```bash
# Retry later, or use a key/project with available quota.
# Example affected command:
python m3_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 1
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
| A2A (workshop) | Structured JSON envelopes exchanged over HTTP JSON-RPC between buyer and seller agents | `m3_adk_multiagents/a2a_protocol_http_orchestrator.py`, `m3_adk_multiagents/a2a_protocol_seller_server.py` |
| A2A (bonus demo) | True networked A2A protocol server (Agent Card + JSON-RPC via a2a-sdk) | `m3_adk_multiagents/a2a_protocol_seller_server.py` + `a2a_protocol_buyer_client_demo.py` |
| FSM | Termination guaranteed by empty transition sets on terminal states | `m1_baseline/state_machine.py` |
| LlmAgent | ADK's agent object: model + instruction + tools (not a running process) | `m3_adk_multiagents/buyer_adk.py` |
| MCPToolset | Connects to MCP server, discovers tools, converts to model function schemas | `m3_adk_multiagents/buyer_adk.py` |
| Runner | Executes ADK agent turns, returns async event stream | `m3_adk_multiagents/buyer_adk.py` |
| InMemorySessionService | ADK's per-agent conversation memory | `m3_adk_multiagents/buyer_adk.py` |
| Workflow agents | `SequentialAgent`, `ParallelAgent`, `LoopAgent` for bounded multi-agent orchestration | `m3_adk_multiagents/notes/google_adk_overview.md` |
| Information Asymmetry | Seller knows its floor via inventory server; buyer infers from market data | `m2_mcp/inventory_server.py` |
| Context manager | Ensures MCP subprocess cleanup even on error | `m3_adk_multiagents/buyer_adk.py` `__aenter__`/`__aexit__` |

---

## ARCHITECTURE DIAGRAM (for whiteboard)

```
                    WORKSHOP ARCHITECTURE
                    =====================

MODULE 2: MCP                MODULE 3: AGENTS + ORCHESTRATION (ADK + A2A)
───────────────────────       ───────────────────────────────────────────

External Data                Buyer Agent (BuyerAgentADK)
┌─────────────┐                ┌────────────────────────┐      A2A JSON-RPC
│  pricing    │ tools          │ LlmAgent + MCPToolset      │   ───────────────────────────
│  server     ◄───────────────│ (model: openai/gpt-4o)     │   ───────────────────────────
└─────────────┘                │ Runner + SessionService    │
                                └────────────────────────┘
External Data                                                       v
┌─────────────┐                Seller Agent (SellerAgentADK)
│  pricing +  │ tools          ┌────────────────────────┐
│  inventory  ◄───────────────│ LlmAgent + MCPToolset      │
│  server     │                │ (model: openai/gpt-4o)     │
└─────────────┘                │ Workflow agent + Runner    │
                                └────────────────────────┘

MODULE 3: TRUE A2A PROTOCOL — NETWORKED AGENTS
──────────────────────────────────────────────
Terminal 1: a2a_protocol_seller_server.py   (HTTP server, port 9102)
  [Agent Card at /.well-known/agent-card.json]
  [SellerAgentADK: OpenAI + MCPToolset (pricing + inventory)]

Terminal 2: a2a_protocol_buyer_client_demo.py / a2a_protocol_http_orchestrator.py
  [BuyerAgentADK: OpenAI + MCPToolset (pricing only)]
       |
       | 1. make offer via ADK (OpenAI + MCP)
       | 2. A2ACardResolver.get_agent_card()  -> GET /.well-known/agent-card.json
       | 3. A2AClient.send_message()          -> POST / (message/send JSON-RPC)
       | 4. receive counter-offer in response <-

MODULE 1: BASELINE (shows what breaks WITHOUT modules 2 and 4)
```

---

## TIMING NOTES FOR REPEAT SESSIONS

- **If running long on M2 (GitHub demo):** Skip the wire protocol section (Section 3 above). Jump straight from conceptual framing to the live demo.
- **If running long on M2 deep dive:** Cut the security/auth subsection — cover it as a take-home reading from `m2_mcp/notes/mcp_deep_dive.md`.
- **If running long on M3 (ADK):** Cut callbacks and event-stream details, keep `LlmAgent` + `MCPToolset` + `Runner` + workflow agents.
- **If running long on M3 (A2A):** Skip the streaming and `tasks/get` subsections — keep Agent Card discovery + `message/send` + task lifecycle.
- **2-hour condensed version:** M1 Part 1 (15 min) + M2 GitHub demo (25 min) + M2 protocol primitives (15 min) + M3 ADK + A2A end-to-end (40 min) + Q&A (25 min). Skip M1 Part 2, M2 transports/security deep dive, and M3 callbacks/streaming detail.
- Negotiation outcomes are non-deterministic — run twice if the first run is uninteresting.
- Costs vary by provider and plan. For workshops, keep prompts short and rounds low to control spend.
