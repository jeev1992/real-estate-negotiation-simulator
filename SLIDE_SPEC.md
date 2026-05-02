# Combined Slide Deck Specification

**Workshop: Building Multi-Agent Systems with MCP, ADK & A2A**

A 4-hour hands-on workshop taught through one concrete project: an autonomous real estate negotiation between a Buyer Agent and a Seller Agent.

**Total slides:** 71 (Introduction: 5, Module 1: 8, Module 2: 17, Module 3: 38, Summary: 3)

---

# PART 0 — INTRODUCTION (Slides 1–5)

---

## Slide 1: Workshop Title

**Title:** Building Multi-Agent Systems — MCP · ADK · A2A

**Body:**

**One project. Three protocols. Four hours.**

You'll build a complete multi-agent real estate negotiation system — from an intentionally broken baseline to production-ready agents communicating over standardized protocols.

```
Module 1: Why Naive AI Agents Break          (45 min)
Module 2: MCP — External Data for Agents     (60 min)
Module 3: Google ADK + A2A Protocol          (90 min)
Wrap-up                                      (15 min)
```

**What you'll have built by the end:**
- A buyer agent and a seller agent, each with real market data from MCP servers
- A negotiation orchestrator that runs multi-round buyer ↔ seller negotiation
- All exposed as A2A network services discoverable via Agent Cards

---

## Slide 2: The Scenario

**Title:** 742 Evergreen Terrace — The Property

**Body:**

**Property:** 742 Evergreen Terrace, Austin, TX 78701
4 BR / 3 BA / 2,400 sqft / Single Family / Built 2005 / Listed at $485,000

| Party | Goal | Starting Position | Walk-Away |
|---|---|---|---|
| **Buyer Agent** (GPT-4o) | Buy at lowest price | Offer ~$425,000 | Over $460,000 |
| **Seller Agent** (GPT-4o) | Sell at highest price | Counter $477,000 | Below $445,000 |

**The Zone of Possible Agreement (ZOPA):** $445K–$460K

The negotiation runs for a maximum of **5 rounds**. Agents use real market data (via MCP) to justify every offer. The same property, the same constraints — across all three modules.

---

## Slide 3: Three Protocols, One System

**Title:** MCP + ADK + A2A — How They Fit Together

**Body:**

| Protocol | What it connects | Analogy |
|----------|-----------------|---------|
| **MCP** (Model Context Protocol) | Agent ↔ Tool | "What tools do you have? Call this one." |
| **ADK** (Agent Development Kit) | Agent framework | "Build agents with tools, state, and orchestration." |
| **A2A** (Agent-to-Agent) | Agent ↔ Agent | "Who are you? Handle this task." |

**Diagram:**
```
                    A2A Protocol
        ┌──────────────────────────────┐
        │                              │
   ┌────▼─────┐                  ┌─────▼────┐
   │  Buyer    │                  │  Seller   │
   │  Agent    │                  │  Agent    │
   │  (ADK)    │                  │  (ADK)    │
   └────┬──────┘                  └─────┬────┘
        │ MCP                           │ MCP
        ▼                               ▼
   ┌──────────┐                  ┌──────────────┐
   │ Pricing  │                  │ Pricing +    │
   │ Server   │                  │ Inventory    │
   └──────────┘                  └──────────────┘
```

**Module 1** shows why you need all of this — by building a version that has NONE of it.

---

## Slide 4: Architecture Overview

**Title:** What We're Building — Layer by Layer

**Body:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Module 3: Orchestration (ADK + A2A)                            │
│                                                                  │
│  LoopAgent(SequentialAgent(buyer, seller), max_iterations=5)    │
│  + submit_decision tool + _check_agreement callback             │
│  + A2A Agent Cards + JSON-RPC message/send                      │
├─────────────────────────────────────────────────────────────────┤
│  Module 2: External Data (MCP)                                   │
│                                                                  │
│  pricing_server.py: get_market_price, calculate_discount        │
│  inventory_server.py: get_inventory_level,                      │
│                       get_minimum_acceptable_price (seller only) │
├─────────────────────────────────────────────────────────────────┤
│  Module 1: Baseline (The Intentionally Broken Version)           │
│                                                                  │
│  naive_negotiation.py: while True + regex + string matching     │
│  state_machine.py: FSM with guaranteed termination              │
└─────────────────────────────────────────────────────────────────┘
```

Each module builds ON TOP of the previous one. M2's MCP servers are consumed by M3's agents. M1's FSM concepts become M3's LoopAgent.

---

## Slide 5: How to Follow Along

**Title:** Setup & Running the Demos

**Body:**

```bash
# Clone and set up
git clone <repo> && cd real-estate-negotiation-simulator
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
cp .env.example .env   # add your OPENAI_API_KEY

# Module 1 — no API key needed for state_machine.py
python m1_baseline/naive_negotiation.py
python m1_baseline/state_machine.py

# Module 2 — MCP demos
python m2_mcp/demos/01_initialize_handshake.py
python m2_mcp/github_agent_client.py "Find MCP servers"

# Module 3 — ADK interactive
adk web m3_adk_multiagents/adk_demos/d01_basic_agent/
adk web m3_adk_multiagents/negotiation_agents/
adk web --a2a m3_adk_multiagents/negotiation_agents/
```

**Prerequisites:** Python 3.11+, `OPENAI_API_KEY`, Node.js (for GitHub MCP server only)

Each module has a `README.md` with per-demo instructions.

---

# PART 1 — MODULE 1: WHY NAIVE AI AGENTS BREAK (Slides 6–13)

---

## Slide 6: Module 1 Title

**Title:** Module 1 — Why Naive AI Agents Break

**Body:**

**The goal:** See exactly how a "simple" LLM negotiation fails — then fix it

By the end of this module you'll have:
- Watched a naive negotiation **work by luck** (Demo 1)
- Watched it **fail catastrophically** (Demo 2)
- Seen **5 concrete failure modes** with code examples
- Built a **finite state machine** that guarantees termination

Every problem in this module maps to a solution in Modules 2 and 3.

```bash
python m1_baseline/naive_negotiation.py   # requires OPENAI_API_KEY
python m1_baseline/state_machine.py       # no API key needed
```

---

## Slide 7: The 10 Problems

**Title:** 10 Ways Naive Agent Systems Fail

**Body:**

```python
# naive_negotiation.py — the "obvious" implementation
while True:                           # Problem #3: no state machine
    message = _call_llm(prompt)       # Problem #1: raw strings
    price = re.search(r'\$?(\d[\d,]*)', message)  # Problem #5: fragile regex
    if "DEAL" in message.upper():     # Problem #6: unreliable termination
        break
```

| # | Problem | What goes wrong | Fixed by |
|---|---------|----------------|----------|
| 1 | Raw strings | LLM returns anything | A2A structured messages (M3) |
| 2 | No schema | Can't validate response | Pydantic / A2A DataPart (M3) |
| 3 | No state machine | `while True` loop | FSM (this module) → LoopAgent (M3) |
| 4 | No turn limits | Can loop forever | `max_turns` → `max_iterations` (M3) |
| 5 | Fragile regex | Extracts wrong price | `price: float` field (M3) |
| 6 | No termination guarantee | "DEAL-breaker" matches "DEAL" | Terminal states / `submit_decision` (M3) |
| 7 | Silent failures | Bad parse → keeps going | Pydantic validation (M3) |
| 8 | Hardcoded prices | No market data | MCP servers (M2) |
| 9 | No observability | Can't audit what happened | ADK events / A2A lifecycle (M3) |
| 10 | No evaluation | Can't measure quality | Session analytics (M3) |

These aren't hypothetical — we'll see #5 and #6 happen live in the demo.

---

## Slide 8: Demo 1 — When It Works (By Luck)

**Title:** Demo 1 — "It Works!" (Fragile)

**Body:**

```bash
python m1_baseline/naive_negotiation.py
```

**Setup:** Buyer max $460K vs Seller min $445K — there IS overlap (ZOPA exists).

**What happened:**
```
[Turn 0] Buyer:  "I offer $424,580"
[Turn 1] Seller: "Counter-offer of $453,150"
[Turn 2] Buyer:  "ACCEPT at $453,150"
[Turn 3] Seller: "DEAL! Sale at $453,150"
```

**Looks great!** Deal in 3 turns, buyer saved $31,850. But notice:
- The buyer happened to say "ACCEPT" — what if it said "I agree"? No termination.
- The seller happened to say "DEAL!" — what if it said "Sold!"? Loop continues.
- The regex happened to grab the right price — what if the seller mentioned renovation costs first?

**This worked by luck, not by design.** The LLM's phrasing determined whether the code terminated correctly.

---

## Slide 9: Demo 2 — The Infinite Loop

**Title:** Demo 2 — When It Breaks (No ZOPA)

**Body:**

**Setup:** Buyer max $420K vs Seller min $450K — NO overlap. Agreement is **mathematically impossible**.

**What happened:**
```
[Turn 0] Buyer:  "$387,660"
[Turn 1] Seller: "Counter at $453,150"
[Turn 2] Buyer:  "Final offer $420,000"          ← hit max budget
[Turn 3] Seller: "Counter at $450,000"           ← hit floor
[Turn 4] Buyer:  "Final offer $420,000"           ← stuck
[Turn 5] Seller: "Counter at $450,000"            ← stuck
[Turn 6] Buyer:  "Final offer $420,000"           ← stuck
[Turn 7] Seller: "DEAL! Sale at $420,000"         ← WAIT WHAT?!
```

**The seller accepted $420,000 — which is BELOW its own minimum of $450,000.**

The LLM got tired of repeating itself and said "DEAL!" The string match `"DEAL" in message.upper()` triggered, and the negotiation "succeeded" at an impossible price.

**This is Failure Mode #6:** The LLM decides termination, not the code. The system has no way to enforce business rules. In production with `max_turns=100`, this would burn 100 LLM API calls for a negotiation that was doomed from turn 1.

---

## Slide 10: 5 Concrete Failure Modes

**Title:** Failure Modes — What Goes Wrong and What Fixes It

**Body:**

**Failure 1 — Wrong price extracted:**
```
LLM: "I spent $350,000 on renovations, my counter is $477,000"
Regex: $350,000  ← WRONG! Got renovation cost, not the offer
Fix:  submit_decision(action="COUNTER", price=477000) — typed field (M3)
```

**Failure 2 — Silent parse failure:**
```
LLM: "I'd like to offer four hundred and thirty thousand dollars"
Regex: None  ← negotiation continues on corrupted data, no error raised
Fix:  Pydantic validation / structured tool parameters (M3)
```

**Failure 3 — Hardcoded prices:**
```python
SELLER_MIN_PRICE = 445_000  # visible in source code, stale
Fix:  get_minimum_acceptable_price() from MCP server (M2)
```

**Failure 4 — Infinite loop (no ZOPA):**
```
Buyer max: $430K | Seller min: $450K → can NEVER agree. while True runs forever.
Fix:  FSM max_turns (M1) → LoopAgent max_iterations (M3)
```

**Failure 5 — String matching is unreliable:**
```
"DEAL-breaker — I won't go lower"  →  matches "DEAL"  ← FALSE POSITIVE
"I think we're close, let's finalize"  →  no match    ← MISSED AGREEMENT
Fix:  submit_decision tool — structured signal, not text parsing (M3)
```

---

## Slide 11: The FSM Fix

**Title:** Finite State Machine — Guaranteed Termination

**Body:**

```python
class NegotiationState(Enum):
    IDLE        = auto()
    NEGOTIATING = auto()
    AGREED      = auto()   # Terminal ✓
    FAILED      = auto()   # Terminal ✗

TRANSITIONS = {
    IDLE:        {NEGOTIATING, FAILED},
    NEGOTIATING: {NEGOTIATING, AGREED, FAILED},
    AGREED:      set(),    # ← EMPTY = no way out
    FAILED:      set(),    # ← EMPTY = no way out
}
```

**Diagram:**
```
         IDLE
          │
    start()
          │
          ▼
    ┌──────────┐
    │NEGOTIATING│◄─── process_turn() loops here
    └────┬─────┘      (turn_count increments each time)
         │
    ┌────┼────┐
    │         │
accept()  reject() / max_turns
    │         │
    ▼         ▼
 AGREED    FAILED
 set()     set()     ← EMPTY = terminal, locked forever
```

**Why it MUST stop:**
1. Terminal states have **empty transition sets** — once entered, can't leave
2. Every turn increments `turn_count`, capped at `max_turns`
3. Either an agent reaches AGREED/FAILED, or the cap forces FAILED

---

## Slide 12: FSM Demo Results

**Title:** FSM — What Actually Happened

**Body:**

```bash
python m1_baseline/state_machine.py   # no API key needed
```

**Scenario 1 — Deal reached (round 3 of 5):**
```
IDLE → NEGOTIATING → round 1 → round 2 → round 3 → AGREED ($449,000)
is_terminal(): True  |  Invariants: PASS
```

**Scenario 2 — Buyer walks away (round 2):**
```
IDLE → NEGOTIATING → round 1 → round 2 → reject() → FAILED
accept() after reject: returned False  ← state is LOCKED
```

**Scenario 3 — Max turns exceeded:**
```
Round 1: True → Round 2: True → ... → Round 5: False → FAILED
failure_reason: MAX_TURNS_EXCEEDED
```

**The key guarantee:** In Demo 2 (no ZOPA, $420K vs $450K), the naive version ran 7+ turns and "agreed" at an impossible price. The FSM would hit `max_turns=5` → FAILED. Zero wasted API calls after that.

---

## Slide 13: M1 → What's Next

**Title:** From FSM to Production — What's Still Missing

**Body:**

| M1 FSM | M3 ADK |
|--------|--------|
| `NegotiationState` enum | `LoopAgent` + `SequentialAgent` |
| `max_turns = 5` | `max_iterations = 5` |
| `is_terminal()` | `escalate = True` |
| `TRANSITIONS[AGREED] = set()` | `_check_agreement` callback |
| `process_turn()` increments counter | LoopAgent tracks iteration count |
| No LLM, pure logic | Real LLM + MCP tools |

**The FSM is the conceptual foundation.** ADK's LoopAgent is the same idea — bounded iteration with explicit terminal conditions — but at the scale of real agents with tools, state, and network communication.

**What the FSM doesn't solve** (and M2/M3 do):
- Problem #8: Hardcoded prices → **MCP servers** (M2)
- Problem #1: Raw strings → **A2A structured messages** (M3)
- Problem #5: Fragile regex → **`submit_decision` tool** (M3)
- Problem #9: No observability → **ADK event stream** (M3)

---

# PART 2 — MODULE 2: MCP — EXTERNAL DATA FOR AGENTS (Slides 14–30)

---

## Slide 14: Module 2 Title

**Title:** Module 2 — MCP: External Data for Agents

**Body:**

**The problem from M1:** Prices were hardcoded (`SELLER_MIN_PRICE = 445_000`). Agents had no real market data — they made up numbers.

**MCP fixes this.** Model Context Protocol is a standard that lets agents call external tools without knowing where the data comes from.

```
Agent: "What tools do you have?"    → list_tools
Server: "get_market_price, ..."     → tool schemas (JSON Schema)
Agent: "Call get_market_price(...)" → call_tool
Server: {estimated_value: 462000}   → structured result
```

By the end of this module:
- You'll understand the MCP protocol (handshake, tools, resources, prompts)
- You'll have seen a live agent use GitHub MCP tools
- You'll have built and inspected custom MCP servers
- You'll understand stdio vs SSE vs Streamable HTTP transports

---

## Slide 15: API vs CLI vs MCP

**Title:** Three Paths to External Systems

**Body:**

> "Agents are only as useful as the systems they can reach."
> — Anthropic

| Path | How it works | Limitation |
|------|-------------|------------|
| **Direct API** | Agent calls HTTP endpoints directly | M×N integration problem — each agent-service pair is bespoke |
| **CLI** | Agent runs shell commands | No reach to web/mobile/cloud — needs a filesystem |
| **MCP** | Standard protocol — discovery + invocation + auth | Upfront investment, but portable across all clients |

**Why MCP wins for production:**
- One remote server reaches **any compatible client** (Claude, ChatGPT, Cursor, VS Code, ADK)
- Auth, discovery, and rich semantics are standardized
- 300M+ SDK downloads/month
- Build once, use everywhere

In our workshop: M1 used hardcoded prices. M2 introduces MCP. M3 consumes MCP servers from ADK agents.

---

## Slide 16: What is MCP?

**Title:** MCP — Model Context Protocol

**Body:**

**Three operations (like a REST API for AI tools):**
1. **Discovery:** `list_tools` — "What can you do?" → returns JSON Schema for each tool
2. **Invocation:** `call_tool(name, args)` — "Do this" → returns structured result
3. **Protocol handshake:** `initialize` — capability negotiation (versions, features)

**Diagram:**
```
  AGENT (Host)                 MCP Protocol              SERVER
  ────────────────             ──────────────            ──────────────
  "What tools exist?"
  session.list_tools() ──────────────────────────────►  Returns schemas
                                                        [{name, description,
                                                          inputSchema}]

  "Call this tool"
  session.call_tool(   ──────────────────────────────►  Executes Python fn
    "get_market_price",
    {"address": "742..."}
  )                    ◄──────────────────────────────  Returns result dict

  LLM reasons about result → calls more tools or answers
```

**The key insight:** The agent never imports your Python functions. It talks to the server over a protocol. The server could be local, remote, in another language — the agent doesn't care.

---

## Slide 17: MCP Primitives & Content Types

**Title:** Four Primitives, Three Content Types

**Body:**

**Primitives — what a server can expose:**

| Primitive | Direction | Our workshop example |
|-----------|-----------|---------------------|
| **Tools** | Client → Server | `get_market_price`, `calculate_discount` |
| **Resources** | Client → Server | `inventory://floor-prices` catalog |
| **Prompts** | Client → Server | `negotiation-tactics` template |
| **Sampling** | Server → Client | Not used (requires sampling-capable host) |

Tools are 90% of MCP usage. Resources and prompts are bonus capabilities.

**Content types — what a tool can return:**

| Type | JSON shape | When to use |
|------|-----------|-------------|
| **TextContent** | `{"type": "text", "text": "..."}` | Most common — tool results |
| **ImageContent** | `{"type": "image", "data": "base64..."}` | Charts, screenshots |
| **EmbeddedResource** | `{"type": "resource", "resource": {...}}` | References to stored data |

`@mcp.tool()` returning a string or dict → TextContent automatically. In our workshop, all tools return TextContent.

---

## Slide 18: Three Transports

**Title:** Same Protocol, Different Wire

**Body:**

| Transport | How it works | When to use |
|-----------|-------------|-------------|
| **stdio** | Server is a subprocess, pipes stdin/stdout | Single client, local dev |
| **SSE** | HTTP server, Server-Sent Events | Multiple clients, remote |
| **Streamable HTTP** | HTTP POST + streaming (spec's recommended) | Production |

**The protocol is the same.** Only the delivery mechanism changes.

```
stdio:            Agent spawns server → pipes stdin/stdout → JSON-RPC
SSE:              Agent connects to http://host:port/sse → JSON-RPC over SSE
Streamable HTTP:  Agent POSTs to http://host:port/mcp → JSON-RPC over HTTP
```

**Diagram:**
```
stdio (1:1):                        SSE / HTTP (1:many):
┌────────┐  stdin/stdout  ┌──────┐  ┌────────┐  HTTP   ┌──────┐
│ Agent  │──────pipe──────│Server│  │ Agent1 │───GET──►│Server│
└────────┘                └──────┘  │ Agent2 │───GET──►│:8001 │
  spawns subprocess                 └────────┘         └──────┘
  dies when agent dies              server lives independently
```

> "Build remote servers for maximum reach." — Anthropic. stdio for dev, HTTP for production.

---

## Slide 19: Demo 01 — The MCP Handshake

**Title:** Demo 01 — What Happens on the Wire

**Body:**

```bash
python m2_mcp/demos/01_initialize_handshake.py   # no API key needed
```

Raw JSON-RPC frames — no SDK, no abstraction:

```
>>> client → server: initialize
    {"jsonrpc": "2.0", "method": "initialize",
     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "demo-client", "version": "0.1"}}}

<<< server → client: initialize result
    {"result": {"protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "prompts": {}, "resources": {}},
                "serverInfo": {"name": "real-estate-pricing", "version": "1.27.0"}}}

>>> notifications/initialized
>>> tools/list
<<< tools/list result → 2 tools with full JSON schemas
```

**5 frames total.** After this handshake, the client knows what tools exist and can call them. JSON Schema is generated from Python type hints — no manual schema writing.

---

## Slide 20: Demo 02 — The Tool Loop

**Title:** Demo 02 — Model ↔ Host ↔ Server

**Body:**

```bash
python m2_mcp/demos/02_tool_loop_trace.py   # requires OPENAI_API_KEY
```

```
[t= 0.00s] HOST    connecting to MCP server (stdio subprocess)
[t= 3.18s] HOST    tools/list → 2 tools discovered
[t= 3.67s] MODEL   receiving prompt + tool catalog
[t= 6.77s] MODEL   emitted tool_use(get_market_price)
[t= 6.77s] HOST    translating tool_use → tools/call
[t= 6.77s] SERVER  returned CallToolResult
[t= 6.77s] HOST    injecting tool_result into model context
[t=10.42s] MODEL   emitted final assistant text
```

**Three actors, clear roles:**

| Actor | What it does |
|-------|-------------|
| **Model** (GPT-4o) | Decides WHICH tools to call based on query + schemas |
| **Host** (your Python code) | Translates between OpenAI format and MCP format |
| **Server** (pricing_server.py) | Executes the tool and returns structured data |

The host is the **bridge**. In M3, ADK's `MCPToolset` IS the host — it does the translation automatically.

---

## Slide 21: Demo 03 — List All Primitives

**Title:** Demo 03 — Tools, Resources, and Prompts

**Body:**

```bash
python m2_mcp/demos/03_list_all_primitives.py   # no API key needed
```

**What it prints:**

```
=== PRICING SERVER ===
[tools] 2      [resources] 0      [prompts] 1

=== INVENTORY SERVER ===
[tools] 2      [resources] 1      [prompts] 0
```

**What to point out live:**
- MCP exposes more than tools; resources and prompts are first-class primitives too
- `inventory://floor-prices` is readable data, not a callable function
- `negotiation-tactics` is a prompt template the host can expand into the conversation

This slide is the concrete proof for Slide 17's primitives table.

---

## Slide 22: Demo 04 — Content Types

**Title:** Demo 04 — Text, Image, and Embedded Resource

**Body:**

```bash
python m2_mcp/demos/04_content_types.py   # no API key needed
```

**Actual output shape:**

```
=== get_text ===     type=text
=== get_image ===    type=image
=== get_resource === type=resource
```

**Why it matters:**
- Most workshop tools return `TextContent`, but MCP can also return images and embedded resources
- The protocol standardizes result blocks, so the host can render them consistently
- Demo 04 makes the JSON shape visible before students ever need to debug it in M3

This slide is the concrete proof for Slide 17's content-types table.

---

## Slide 23: Custom MCP Servers

**Title:** Building Your Own MCP Server

**Body:**

```python
# pricing_server.py — 5 lines to expose a tool
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("real-estate-pricing")

@mcp.tool()
def get_market_price(address: str, property_type: str = "single_family") -> dict:
    """Get market price analysis for a property."""
    return {"estimated_value": 462_000, "comparable_sales": [...], ...}
```

**What `@mcp.tool()` does:**
- Reads the function signature → JSON Schema (`inputSchema`)
- Reads the docstring → tool `description`
- Registers as a callable MCP tool

> "Group tools around intent, not endpoints." A single `get_market_price` beats `get_comps` + `get_sqft` + `get_days_on_market` + `calculate_value`. — Anthropic

**Two servers in this workshop:**

| Server | Tools | Who uses it (M3) |
|--------|-------|-------------------|
| `pricing_server.py` | `get_market_price`, `calculate_discount` | Both buyer and seller |
| `inventory_server.py` | `get_inventory_level`, `get_minimum_acceptable_price` | **Seller only** |

---

## Slide 24: Information Asymmetry via MCP

**Title:** Different Agents, Different Tools

**Body:**

```
BUYER sees:                         SELLER sees:
┌─────────────────────┐            ┌─────────────────────┐
│ pricing_server      │            │ pricing_server      │
│  get_market_price   │            │  get_market_price   │
│  calculate_discount │            │  calculate_discount │
└─────────────────────┘            ├─────────────────────┤
                                   │ inventory_server    │
                                   │  get_inventory_level│
                                   │  get_minimum_       │
                                   │   acceptable_price  │ ← SECRET
                                   └─────────────────────┘
```

**The floor price ($445K) lives in the server, not the code.**
- M1: `SELLER_MIN_PRICE = 445_000` — hardcoded, visible to everyone
- M2: `get_minimum_acceptable_price()` — returned by MCP at runtime, only accessible to seller (enforced in M3)

This is how real production systems work. Different agents get different tool access. The protocol is the same — the authorization is different.

---

## Slide 25: GitHub MCP Agent (Live Demo)

**Title:** Live Demo — An LLM Agent Using GitHub via MCP

**Body:**

```bash
python m2_mcp/github_agent_client.py "Find popular MCP server implementations"
```

**What happens:**
1. Agent spawns GitHub's MCP server via `npx @modelcontextprotocol/server-github`
2. Discovers 20+ tools (search repos, read files, list issues, etc.)
3. GPT-4o reads your query, picks tools, calls them via MCP
4. Feeds results back, calls more tools or produces final answer

**The agentic loop:**
```python
for iteration in range(max_iterations):
    response = await openai.create(messages=messages, tools=openai_tools)
    if response.tool_calls:
        for call in response.tool_calls:
            result = await session.call_tool(call.name, call.args)  # MCP
            messages.append({"role": "tool", "content": result})
    else:
        return response.content  # final answer
```

**This is the pattern ADK automates.** In M3, `MCPToolset` + `LlmAgent` replaces this entire loop with one declaration: `tools=[MCPToolset(...)]`.

---

## Slide 26: SSE MCP Agent (Live Demo)

**Title:** SSE Agent — Same Loop, HTTP Transport

**Body:**

```bash
# Terminal 1: start MCP servers in SSE mode
python m2_mcp/pricing_server.py --sse --port 8001
python m2_mcp/inventory_server.py --sse --port 8002

# Terminal 2: run the agent
python m2_mcp/sse_agent_client.py "What is 742 Evergreen Terrace worth?"

# With both servers:
python m2_mcp/sse_agent_client.py --both "What's the seller's minimum price?"
```

**What happens:**
1. Agent connects to pricing server (and optionally inventory server) via SSE
2. Discovers tools from each server, merges into one unified tool list
3. GPT-4o reads query, picks tools, calls them via MCP-over-SSE
4. Feeds results back, produces final answer

**github_agent_client.py vs sse_agent_client.py:**

| | github_agent_client | sse_agent_client |
|---|---|---|
| Transport | stdio (subprocess) | SSE (HTTP) |
| Server | GitHub's MCP server (TypeScript) | Our `pricing_server.py` + `inventory_server.py` |
| Multi-server | No | Yes (`--both` merges 4 tools from 2 servers) |
| Tool loop | Identical | Identical |

**The agent loop is identical.** Only the connection setup changes. This proves transport is pluggable — the agent doesn't care how it connects to the server.

**`--both` reveals the information asymmetry:** With both servers, the agent can see the seller's floor price ($445K) via `get_minimum_acceptable_price`. In M3, the buyer's allowlist blocks this tool.

---

## Slide 27: SSE vs stdio vs Streamable HTTP

**Title:** Three Transports Side by Side

**Body:**

**stdio (Demos 01–04):**
```python
server_params = StdioServerParameters(command="python", args=["pricing_server.py"])
async with stdio_client(server_params) as (read, write):
    # server is a subprocess — dies when you disconnect
```

**SSE (sse_agent_client.py):**
```bash
# Terminal 1: start server
python m2_mcp/pricing_server.py --sse --port 8001

# Terminal 2: connect agent
python m2_mcp/sse_agent_client.py "What is 742 Evergreen Terrace worth?"
```

**Streamable HTTP (Demo 05):**
```bash
# Terminal 1: server
python m2_mcp/demos/05_streamable_http_transport.py --serve --port 8765

# Terminal 2: client
python m2_mcp/demos/05_streamable_http_transport.py --client --port 8765
```

**The agent code is identical** — only the connection setup changes. `list_tools()` and `call_tool()` work the same way regardless of transport. This is the whole point of a protocol standard.

---

## Slide 28: Demo 05 — Streamable HTTP Results

**Title:** Demo 05 — HTTP Transport in Action

**Body:**

```bash
# Terminal 1:
python m2_mcp/demos/05_streamable_http_transport.py --serve --port 8765

# Terminal 2:
python m2_mcp/demos/05_streamable_http_transport.py --client --port 8765
```

**Client output:**
```
Connecting client to http://127.0.0.1:8765/mcp
discovered tools: ['echo']
response: echo: hello over HTTP
```

**The server is 5 lines:**
```python
mcp = FastMCP("http-transport-demo")

@mcp.tool()
def echo(text: str) -> str:
    """Echo back the supplied text."""
    return f"echo: {text}"

mcp.run(transport="streamable-http")
```

**Same `session.list_tools()`, same `session.call_tool()`.** Only the import changes. The server is an independent HTTP process — survives client disconnection, multiple clients can connect simultaneously.

---

## Slide 29: M2 Key Concepts Summary

**Title:** Module 2 — What You Learned

**Body:**

| Concept | What it means | Where we saw it |
|---------|--------------|----------------|
| **MCP Protocol** | JSON-RPC handshake + tool discovery + invocation | Demo 01 (raw frames) |
| **Three actors** | Model (decides), Host (bridges), Server (executes) | Demo 02 (timestamped trace) |
| **Four primitives** | Tools, Resources, Prompts, Sampling | Demo 03 (list all) |
| **Content types** | TextContent, ImageContent, EmbeddedResource | Demo 04 |
| **Three transports** | stdio (1:1 local), SSE (1:many HTTP), Streamable HTTP (production) | Demos 01–04 (stdio), SSE agent, Demo 05 (HTTP) |
| **Tool design** | Group around intent, not endpoints | `get_market_price` (one call, all data) |
| **Information asymmetry** | Different agents see different tools | Buyer vs seller server access |
| **Agentic loop** | LLM + tool schemas → decide → call → reason | `github_agent_client.py`, `sse_agent_client.py` |

**What carries forward to M3:**
- `pricing_server.py` and `inventory_server.py` are used directly by buyer/seller agents
- The agentic loop pattern is replaced by `MCPToolset` + `LlmAgent`
- Information asymmetry is enforced by `before_tool_callback` allowlists

---

## Slide 30: From M2 to M3

**Title:** M2 → M3 — What Changes

**Body:**

**In M2, you write the tool loop manually (~60 lines):**
```python
tools = await session.list_tools()
openai_tools = mcp_tools_to_openai_functions(tools)
for iteration in range(max_iterations):
    response = await openai.create(messages=messages, tools=openai_tools)
    if response.tool_calls:
        for call in response.tool_calls:
            result = await session.call_tool(call.name, call.args)
            messages.append({"role": "tool", "content": result})
    else:
        return response.content
```

**In M3, one line replaces all of that:**
```python
root_agent = LlmAgent(
    tools=[MCPToolset(connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(command="python", args=["pricing_server.py"])
    ))]
)
```

**ADK's `MCPToolset`** spawns the server, runs the handshake, converts schemas, executes tool calls, feeds results back — all automatically.

**M2 teaches you what's happening inside. M3 lets you stop writing it.**

---

# PART 3 — MODULE 3: GOOGLE ADK + A2A (Slides 31–68)

---

## Slide 31: Module 3 Title

**Title:** Module 3 — Google ADK + A2A Protocol

**Body:**

**The goal:** Build a complete multi-agent negotiation system using Google ADK

By the end of this module you'll have:
- A **buyer agent** with MCP pricing tools
- A **seller agent** with MCP pricing + inventory tools (information asymmetry)
- A **negotiation orchestrator** that runs multi-round buyer ↔ seller negotiation
- All exposed as **A2A network services** with auto-generated Agent Cards

**Architecture:**
```
┌─────────────────────────────────────────────────────┐
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐   │
│  │  buyer    │    │  seller   │    │ negotiation   │   │
│  │  LlmAgent │    │ LlmAgent │    │  LoopAgent   │   │
│  │  +MCP     │    │ +MCP×2   │    │  +Sequential │   │
│  │  pricing  │    │ pricing  │    │  (buyer→     │   │
│  │          │    │ +inventory│    │   seller)    │   │
│  └──────────┘    └──────────┘    └──────────────┘   │
│       │ MCP           │ MCP                          │
│       ▼               ▼                              │
│  pricing_server   pricing_server + inventory_server  │
│  (from M2)        (from M2)                          │
└─────────────────────────────────────────────────────┘
```

Every concept is taught through a demo first, then composed into the final system.

---

## Slide 32: The Final System

**Title:** negotiation_agents/ — The Heart of Module 3

**Body:**

```
negotiation_agents/
  buyer_agent/agent.py     → LlmAgent + MCPToolset (pricing only)
  seller_agent/agent.py    → LlmAgent + MCPToolset (pricing + inventory)
  negotiation/agent.py     → LoopAgent(SequentialAgent(buyer, seller))
```

```bash
# Chat with them interactively
adk web m3_adk_multiagents/negotiation_agents/

# Expose as A2A network services
adk web --a2a m3_adk_multiagents/negotiation_agents/
```

Before we build this, we'll learn each piece through 9 interactive demos.

---

## Slide 33: Learning Path

**Title:** 9 Demos → 4 A2A Scripts → 1 Complete System

**Body:**

| # | Demo | Concept | Builds toward |
|---|------|---------|--------------|
| d01 | Basic Agent | `LlmAgent` + function tool | buyer/seller agent definition |
| d02 | MCP Tools | `MCPToolset` auto-discovery | buyer/seller MCP connections |
| d03 | Sessions & State | `ToolContext` + state persistence | negotiation round tracking |
| d04 | Sequential | Pipeline: A → B → C | buyer → seller per round |
| d05 | Parallel | Fan-out: A, B, C concurrent | research signals |
| d06 | Loop | Iterate until escalation | negotiation rounds |
| d07 | Agent-as-Tool | Agent wrapped as function | hierarchical delegation |
| d08 | Callbacks | PII, allowlists, logging | tool access control |
| d09 | Event Stream | State deltas + tool calls | observability |
| 10–13 | A2A Protocol | Wire format, threading, streaming | network deployment |

d01–d09 run in `adk web` (interactive chat). 10–13 are terminal scripts against `adk web --a2a`.

---

## Slide 34: Demo 01 — Basic LlmAgent (Concept)

**Title:** Demo 01 — The Simplest ADK Agent

**Body:**

```python
root_agent = LlmAgent(
    name="basic_agent",
    model="openai/gpt-4o",
    instruction="Use get_quick_estimate when asked about properties.",
    tools=[get_quick_estimate],    # plain Python function
)
```

**Key concepts:**
- `LlmAgent` = model + instruction + tools
- `root_agent` = the variable `adk web` discovers
- Function tools: ADK reads type hints + docstring → JSON schema
- The LLM decides WHETHER to call tools — not scripted

**Diagram: Agent Loop**
```
  User message
       │
       ▼
  ┌─────────┐
  │ GPT-4o  │──── sees tool schemas
  └────┬────┘
       │
   tool call?  ───NO──→  final text response
       │
      YES
       │
       ▼
  ┌──────────────┐
  │ ADK executes │
  │ Python func  │
  └──────┬───────┘
       │
       ▼
  ┌─────────┐
  │ GPT-4o  │──── sees tool result → final text response
  └─────────┘
```

**Try these:**

| Question | Expected |
|----------|----------|
| "What's 742 Evergreen Terrace worth?" | Calls tool → $462K, high confidence |
| "What about 999 Unknown Ave?" | Calls tool → $450K, LOW confidence |
| "What's the best neighborhood in Austin?" | NO tool call — LLM knowledge |

The LLM decides when tools are relevant. Question 3 proves it — the model doesn't call a tool for a non-property question.

---

## Slide 35: Demo 01 — Results

**Title:** Demo 01 — What Happened

**Body:**

**Tool call flow (4 events per property question):**
```
User → LLM decides tool → ADK executes function → LLM summarizes result
```

**No tool call flow (2 events):**
```
User → LLM answers from knowledge (no tool needed)
```

**session.db:** Only `__session_metadata__` in state — no state writes in this demo.

**Key takeaway:** Compare to M2's `github_agent_client.py` — there you hand-wrote the tool loop (call LLM → check for tool_calls → execute → feed back). Here, `tools=[fn]` and ADK does the rest.

The contrast with M2 is the most important point. ADK replaces ~60 lines of manual tool loop with one declaration.

---

## Slide 36: Demo 02 — MCP Tools in ADK (Concept)

**Title:** Demo 02 — Auto-Discover Tools from MCP Servers

**Body:**

```python
root_agent = LlmAgent(
    name="mcp_tools_agent",
    model="openai/gpt-4o",
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=["m2_mcp/pricing_server.py"],
                )
            )
        )
    ],
)
```

**d01 vs d02:**
- d01: `tools=[get_quick_estimate]` — you wrote the function
- d02: `tools=[MCPToolset(...)]` — ADK spawns server, discovers tools via MCP

The LLM sees identical function schemas in both cases.

**Diagram: d01 vs d02**
```
d01:  LlmAgent → tools=[Python fn]     → ADK calls function directly
d02:  LlmAgent → tools=[MCPToolset]    → ADK spawns server → MCP protocol → server runs fn
                                         ▲
                                         │
                                    pricing_server.py (from M2)
```

**Try these:**

| Question | Expected |
|----------|----------|
| "What's 742 Evergreen Terrace worth?" | Calls `get_market_price` → rich MCP data |
| "What are the taxes on 742 Evergreen?" | NO tool call — tax tool is commented out |

Question 2 is the key moment. `get_property_tax_estimate` is commented out in the server. The LLM correctly knows it has no tax tool — proves auto-discovery is real, not hardcoded.

---

## Slide 37: Demo 02 — Results

**Title:** Demo 02 — Auto-Discovery Proven

**Body:**

**The tax question proves it:**
- Instruction does NOT name any tools
- LLM checked its available tools → no tax tool found → declined honestly
- After M2 Exercise 01 (uncomment the tool), the same question works

**MCPToolset lifecycle:**
```
adk web starts → spawns pricing_server.py → initialize + tools/list
  → discovers: get_market_price, calculate_discount
  → LLM can call them autonomously
adk web stops → kills subprocess
```

**Key takeaway:** Add a `@mcp.tool()` to the server → restart `adk web` → LLM can call it. Zero agent code changes.

This is what the buyer/seller agents do. Same MCPToolset pattern — just pointed at different servers.

---

## Slide 38: Demo 03 — Sessions & State (Concept)

**Title:** Demo 03 — Tools That Remember

**Body:**

```python
def record_offer(price: int, tool_context: ToolContext) -> dict:
    history = tool_context.state.get("offer_history", [])
    history.append(price)
    tool_context.state["offer_history"] = history          # session-scoped
    tool_context.state["user:total_offers"] = len(history) # user-scoped
```

**State scoping:**

| Prefix | Stored in | Lifetime |
|--------|-----------|----------|
| (none) | `sessions` table | Cleared on "New Session" |
| `user:` | `user_states` table | Survives across sessions |
| `app:` | `app_states` table | Global, all users |
| `temp:` | Memory only | One turn |

**Diagram: State Scoping**
```
                    session.db
┌──────────────────────────────────────┐
│  sessions table     ← no prefix     │  cleared on New Session
│  ┌──────────────────────────────┐    │
│  │ offer_history: [430K, 445K]  │    │
│  └──────────────────────────────┘    │
│                                      │
│  user_states table  ← user: prefix  │  survives New Session
│  ┌──────────────────────────────┐    │
│  │ total_offers: 3              │    │
│  └──────────────────────────────┘    │
│                                      │
│  app_states table   ← app: prefix   │  global (empty in demos)
│  └──────────────────────────────┘    │
└──────────────────────────────────────┘
```

**Try these (in order, same session):**

| Question | Expected |
|----------|----------|
| "Offer $430,000" | Records, total=1 |
| "Offer $445,000" | total=2, best=$445K |
| "Offer $440,000" | Regression warning! |
| New Session → "How many offers?" | session=0, total=3 |

The last question is the proof. Session state resets (offers=[]), but user:total_offers persists (=3). Watch the State tab live.

---

## Slide 39: Demo 03 — Results

**Title:** Demo 03 — State Scoping Proven

**Body:**

**After "New Session" → "How many offers?":**
> "3 offers across all sessions, none in current session"

| Scope | Key | Value | What happened |
|-------|-----|-------|---------------|
| Session | `offer_history` | `[]` | Reset on New Session |
| User | `user:total_offers` | `3` | Persisted! |

**session.db `user_states` table — first time with data:**
```json
{"total_offers": 3}
```

**Key takeaway:** `ToolContext.state` is the bridge between tools and session memory. State scoping controls what survives.

In adk web, user_id defaults to "user" so user: and app: behave the same. The distinction matters in production with multiple users.

---

## Slide 40: Demo 04 — SequentialAgent (Concept)

**Title:** Demo 04 — Pipeline: A → B → C

**Body:**

```python
market_brief = LlmAgent(output_key="market_summary", ...)
offer_drafter = LlmAgent(output_key="offer_text",
    instruction="Read {market_summary} and draft an offer...")
polisher = LlmAgent(output_key="final_email",
    instruction="Polish {offer_text} into a professional email...")

root_agent = SequentialAgent(
    sub_agents=[market_brief, offer_drafter, polisher],
)
```

**Data flow via state:**
```
market_brief writes "market_summary"
  → offer_drafter reads {market_summary}, writes "offer_text"
    → polisher reads {offer_text}, writes "final_email"
```

**Diagram: Sequential Pipeline**
```
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │ market_brief  │────▶│ offer_drafter │────▶│   polisher    │
  │              │     │              │     │              │
  │ writes:      │     │ reads:       │     │ reads:       │
  │ market_      │     │ {market_     │     │ {offer_text} │
  │ summary      │     │  summary}    │     │              │
  │              │     │ writes:      │     │ writes:      │
  │              │     │ offer_text   │     │ final_email  │
  └──────────────┘     └──────────────┘     └──────────────┘
          SequentialAgent runs left → right
```

**Try:** Send any message → check State tab for all 3 keys

SequentialAgent is NOT an LlmAgent. It doesn't call a model. It just runs children in order. output_key + {placeholder} is the data pipeline.

---

## Slide 41: Demo 04 — Results

**Title:** Demo 04 — Three Agents, One Pipeline

**Body:**

**Events (4 total):**
```
Event 1 | user           → "Research this property"
Event 2 | market_brief   → "Austin 78701 median price..."
Event 3 | offer_drafter  → "We extend an offer of $460,000..."
Event 4 | message_polisher → "Subject: Initial Offer..."
```

**State tab after run:**
- `market_summary`: "Austin 78701..."
- `offer_text`: "$460K offer..."
- `final_email`: Full professional email

**Key takeaway:** Each agent saw ONLY what it needed. offer_drafter read `{market_summary}` — it didn't see the polisher's output. State keys create scoped visibility.

This is half of the negotiation orchestrator. negotiation/agent.py uses SequentialAgent(buyer, seller) — same pattern.

---

## Slide 42: Demo 05 — ParallelAgent (Concept)

**Title:** Demo 05 — Fan-Out: A, B, C Run Concurrently

**Body:**

```python
schools = LlmAgent(output_key="schools", ...)
comps = LlmAgent(output_key="comps", ...)
inventory = LlmAgent(output_key="inventory", ...)

root_agent = ParallelAgent(
    sub_agents=[schools, comps, inventory],  # all at once
)
```

**d04 vs d05:**
- d04 Sequential: A feeds B feeds C (pipeline)
- d05 Parallel: A, B, C run simultaneously (fan-out)

**Diagram: Sequential vs Parallel**
```
d04 Sequential:          d05 Parallel:
  A ──▶ B ──▶ C           A ──▶ state["schools"]
  (ordered, dependent)    B ──▶ state["comps"]      (concurrent)
                          C ──▶ state["inventory"]
```

**Rule:** Each agent MUST write to a different `output_key`. Two agents writing the same key → last one wins (overwrite, no merge).

**Try:** Send any message → check State tab for all 3 keys appearing simultaneously

Combine them: Exercise 03 asks students to nest a ParallelAgent inside a SequentialAgent — parallel research first, then sequential strategy.

---

## Slide 43: Demo 05 — Results

**Title:** Demo 05 — Independent Signals Gathered

**Body:**

**State tab after run:**
```
schools:   "Austin ISD has strong academic programs..."
comps:     "Recent sales $700K–$1M range..."
inventory: "High inventory pressure, limited listings..."
```

**Same 4-event structure as d04** — but concurrent execution. State key order in the db differs from declaration order (proves concurrency — finish order varies).

**Key takeaway:** ParallelAgent = fan-out for independent tasks. SequentialAgent = pipeline for dependent tasks. Both use `output_key`.

No {placeholder} reading between agents — they're independent. That's why ParallelAgent works here.

---

## Slide 44: Demo 06 — LoopAgent (Concept)

**Title:** Demo 06 — Iterate Until Done

**Body:**

```python
def stop_when_in_range(callback_context: CallbackContext):
    price = int(callback_context.state.get("proposal", "0"))
    if 450_000 <= price <= 470_000:
        callback_context.actions.escalate = True  # ← breaks the loop

root_agent = LoopAgent(
    sub_agents=[haggler],
    max_iterations=5,  # bounded — NEVER runs more than 5
)
```

**Two stop conditions:**
1. `callback_context.actions.escalate = True` — early exit (price in range)
2. `max_iterations=5` — hard cap (same guarantee as M1's FSM)

**Try:** Send "start" → watch iteration count in Events

This is the ADK equivalent of M1's FSM termination guarantee. max_iterations = max_turns. escalate = terminal state. Same principle, different abstraction.

---

## Slide 45: Demo 06 — Results

**Title:** Demo 06 — Bounded Termination

**Body:**

**Connection to Module 1:**

| M1 FSM | ADK LoopAgent |
|--------|---------------|
| `max_turns` | `max_iterations` |
| `is_terminal = True` | `escalate = True` |
| Empty transition set | Loop stops |
| Guarantees termination | Guarantees termination |

**Diagram: LoopAgent Flow**
```
         ┌─────────────────────┐
         │     LoopAgent       │
         │  max_iterations=5   │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
    ┌───▶│     haggler         │
    │    │  proposes a price   │
    │    └──────────┬──────────┘
    │               │
    │    ┌──────────▼──────────┐
    │    │ after_agent_callback │
    │    │ price in range?     │
    │    └──────────┬──────────┘
    │           │        │
    │          NO       YES
    │           │        │
    └───────────┘   escalate=True
                        │
                     STOP
```

**`output_key` in a loop:** Each iteration OVERWRITES the same key. Only the last value survives (unlike d03's array accumulation).

**Key takeaway:** LoopAgent = bounded iteration + explicit escalation. No `while True`, no emergency exits.

negotiation/agent.py uses LoopAgent(sub_agents=[SequentialAgent(buyer, seller)], max_iterations=5). Each iteration is one negotiation round. seller's after_agent_callback checks for ACCEPT and escalates.

---

## Slide 46: Demo 07 — Agent-as-Tool (Concept)

**Title:** Demo 07 — Wrap an Agent as a Callable Tool

**Body:**

```python
valuator = LlmAgent(
    name="valuator",
    description="Estimates fair market value of Austin properties.",
)

root_agent = LlmAgent(
    name="coordinator",
    tools=[AgentTool(agent=valuator)],  # ← agent wrapped as tool
)
```

**Three delegation patterns:**

| Pattern | How it works | Control |
|---------|-------------|---------|
| AgentTool | Call agent as function → result returns to caller | Caller keeps control |
| sub_agents | Transfer to agent → it takes over | Full delegation |
| SequentialAgent | Fixed order, no runtime choice | No decision |

**Diagram: AgentTool Delegation**
```
  ┌─────────────────┐
  │   coordinator    │
  │   (LlmAgent)     │
  │                  │
  │  "I need a       │
  │   valuation"     │
  └────────┬─────────┘
           │ tool_call: valuator(...)
           ▼
  ┌─────────────────┐
  │    valuator      │  ← full LlmAgent (own model call)
  │   (AgentTool)    │
  │                  │
  │  "$750K–$900K"   │
  └────────┬─────────┘
           │ result returns to coordinator
           ▼
  ┌─────────────────┐
  │   coordinator    │
  │  writes final    │
  │  recommendation  │
  └─────────────────┘
```

**Try:**

| Question | Expected |
|----------|----------|
| "What should I offer on 742 Evergreen?" | Calls valuator → gets estimate → writes recommendation |
| "What's the weather?" | No valuator call — not relevant |

The valuator is a full LlmAgent with its own model call. The coordinator sees it as a function. Two LLM calls per delegation = more expensive but better separation of concerns.

---

## Slide 47: Demo 07 — Results

**Title:** Demo 07 — Delegation in Action

**Body:**

**Event flow:**
```
Event 1 | user        → "What should I offer?"
Event 2 | coordinator → tool_call: valuator({"request": "742 Evergreen..."})
Event 3 | coordinator → tool_result: "$750K–$900K, location is biggest factor"
Event 4 | coordinator → "I recommend offering within $750K–$900K range..."
```

**Notice:** Valuator estimated $750K–$900K (LLM knowledge). d02's MCP-backed `get_market_price` returned $462K. **This is why MCP matters** — without grounded data, the LLM hallucinated a price.

**Key takeaway:** AgentTool = explicit delegation. The coordinator decides WHEN to call the specialist.

description matters here. The coordinator reads valuator.description to decide when to call it — like a function docstring.

---

## Slide 48: Demo 08 — Callbacks (Concept)

**Title:** Demo 08 — Policy Without Prompts

**Body:**

Three callback hooks — enforce rules the LLM CAN'T bypass:

| Callback | When it fires | What it does |
|----------|-------------|-------------|
| `before_model_callback` | Before every LLM call | Redact PII (SSN regex) |
| `before_tool_callback` | Before every tool call | Block disallowed tools |
| `after_tool_callback` | After every tool returns | Log results for audit |

**Return values:**
- `None` = allow (continue normally)
- `dict` = block/replace (short-circuit)

**Try (watch terminal, not UI):**

| Question | Terminal output |
|----------|----------------|
| "My SSN is 123-45-6789. Estimate 742 Evergreen." | `[before_model] redacted PII` |
| "Call get_internal_admin('debug')" | `[before_tool] BLOCKED` or LLM declines |

Callbacks are deterministic — a regex WILL strip the SSN. The instruction "don't share SSNs" is suggestive — the LLM might still leak it. Callbacks can't be bypassed.

---

## Slide 49: Demo 08 — Results

**Title:** Demo 08 — Security Audit Trail

**Body:**

**Terminal output (the real story):**
```
[before_model] redacted PII from prompt     ← SSN stripped
[before_tool] allow get_quick_estimate(...)  ← on allowlist
[after_tool] get_quick_estimate -> {462000}  ← logged
[before_model] redacted PII from prompt     ← runs AGAIN (history has SSN)
```

**`before_model` fires on EVERY LLM call** — not just the first. Each turn has 2+ LLM calls (decide + summarize), and conversation history includes the original SSN message, so redaction runs every time.

**Key takeaway:** Callbacks = deterministic policy. This is what `buyer_agent` and `seller_agent` use for tool allowlists (`_enforce_buyer_allowlist`).

In production, swap print() for structured logging. The audit trail is the compliance layer.

---

## Slide 50: Demo 09 — Event Stream (Concept)

**Title:** Demo 09 — See What the Runner Produces

**Body:**

```python
def lookup_comps(address: str, tool_context: ToolContext) -> dict:
    tool_context.state["last_comp_lookup"] = address
    return {"comps": [...], "avg_comp_price": 465_000}

def estimate_offer(comp_avg: int, discount_pct: int, tool_context: ToolContext) -> dict:
    tool_context.state["latest_offer"] = int(comp_avg * (1 - discount_pct / 100))
    tool_context.state["offer_count"] = tool_context.state.get("offer_count", 0) + 1
```

**Focus on:** State tab (updates live) + left panel event inspector (state deltas)

**Try:** "What should I offer on 742 Evergreen Terrace?" → check State tab

This demo is about seeing state writes and event structure, not the chat response.

---

## Slide 51: Demo 09 — Results

**Title:** Demo 09 — Parallel Tool Pitfall

**Body:**

**What happened:**
```
LLM called BOTH tools in parallel:
  lookup_comps({"address": "742 Evergreen"})     → returned avg: $465K
  estimate_offer({"comp_avg": 300000, ...})       → used $300K (WRONG!)
```

**The LLM made up $300K** because it decided both arguments BEFORE seeing either result. Nobody told it to parallelize — GPT-4o chose to emit both calls in one response.

**The fix:** SequentialAgent (d04) when tool B depends on tool A's output, or more explicit instructions.

**Key takeaway:** Parallel tool calls are great for independent tasks (d05). Dangerous when there are data dependencies.

This is a known GPT-4o behavior. The instruction said "1. call lookup, 2. call estimate with the result" but the model ignored the dependency.

---

## Slide 52: What is A2A?

**Title:** A2A — Agent-to-Agent Protocol

**Body:**

**The problem:** So far, all our agents run in the SAME process. The buyer and seller are Python objects in the same `adk web` instance. What if they're on different machines, owned by different teams, written in different languages?

**A2A solves this.** It's an open protocol for agents to discover and communicate with each other over HTTP.

**Diagram: MCP vs A2A**
```
MCP = Agent ↔ Tool                    A2A = Agent ↔ Agent
┌─────────┐    ┌──────────────┐       ┌─────────┐    ┌─────────┐
│  Agent   │───▶│  MCP Server  │       │ Agent A │◀──▶│ Agent B │
│          │    │  (tools)     │       │         │    │         │
└─────────┘    └──────────────┘       └─────────┘    └─────────┘
  "What tools     "Here are 3          "Who are you?"  "I handle
   do you have?"   tools..."            "Send me this"  seller offers"
```

**Three operations (same pattern as MCP):**
1. **Discovery:** `GET /.well-known/agent-card.json` — "Who are you and what can you do?"
2. **Schema:** Agent Card — name, description, skills, capabilities
3. **Invocation:** `POST /` (JSON-RPC `message/send`) — "Handle this task"

MCP: agent discovers **tools**. A2A: agent discovers **other agents**.

---

## Slide 53: Why A2A Matters

**Title:** From In-Process to Network Services

**Body:**

**Without A2A (d01–d09):**
- Buyer and seller are Python objects in the same process
- They communicate via shared session state (`output_key`, `{placeholder}`)
- Tightly coupled — you must import both to run either

**With A2A:**
- Buyer runs on Machine A, seller runs on Machine B
- They communicate via HTTP JSON-RPC
- Neither knows how the other is built — only the Agent Card
- Could be different languages, different teams, different companies

**The real-world pattern:**
```
Your company's buyer agent  ──HTTP──▶  Partner company's seller agent
  (Python + ADK)                        (Java + Spring)
  knows: Agent Card URL                 exposes: Agent Card + JSON-RPC
  doesn't know: implementation          doesn't know: who's calling
```

This is what production multi-agent systems look like.

---

## Slide 54: Agent Card

**Title:** Agent Card = Agent's Business Card

**Body:**

Every A2A agent publishes a JSON document at `/.well-known/agent-card.json`:

```json
{
  "name": "seller_agent",
  "description": "Real estate seller agent for 742 Evergreen Terrace",
  "url": "http://localhost:8000/a2a/seller_agent",
  "capabilities": {"streaming": true},
  "skills": [{
    "id": "negotiation_response",
    "name": "Real Estate Seller Negotiation",
    "description": "Responds to buyer offers with counter-offers",
    "tags": ["real_estate", "seller", "negotiation"]
  }]
}
```

**What a client learns from the card:**
- What this agent does (description + skills)
- Where to send messages (url)
- What features are supported (streaming, push notifications)
- No documentation needed — self-describing, like MCP tool schemas

In our workshop, `agent.json` in each agent folder defines this card. `adk web --a2a` serves it automatically.

---

## Slide 55: A2A Demos Overview

**Title:** Demos 10–13 — A2A Protocol in Action

**Body:**

```bash
# Terminal 1: Start agents with A2A endpoints
adk web --a2a m3_adk_multiagents/negotiation_agents/

# Terminal 2: Run protocol demos
python adk_demos/a2a_10_wire_lifecycle.py
python adk_demos/a2a_11_context_threading.py
python adk_demos/a2a_12_parts_and_artifacts.py
python adk_demos/a2a_13_streaming.py
```

**What `--a2a` adds:**
- Agent Card at `/<agent>/.well-known/agent-card.json`
- JSON-RPC endpoint at `POST /<agent>/`
- No custom server code — ADK generates everything

**Diagram: adk web vs adk web --a2a**
```
adk web (without --a2a):           adk web --a2a:
┌────────────────┐                ┌────────────────────────────┐
│  Chat UI       │                │  Chat UI (same)            │
│  dropdown      │                │  dropdown                  │
│  session mgmt  │                │  session mgmt              │
└────────────────┘                │                            │
                                  │  + A2A endpoints:          │
                                  │  GET  /.well-known/        │
                                  │       agent-card.json      │
                                  │  POST / (message/send)     │
                                  │  POST / (message/stream)   │
                                  └────────────────────────────┘
```

These demos are terminal scripts, not adk web dropdown agents. They talk to the agents over HTTP.

---

## Slide 56: Demo 10 — A2A Wire Format (Concept)

**Title:** Demo 10 — Raw JSON-RPC + Task Lifecycle

**Body:**

**Three steps:**
1. `GET /a2a/seller_agent/.well-known/agent-card.json` — discover the agent
2. `POST /a2a/seller_agent` (valid offer $440K) — task: `completed`, counter-offer at $477K
3. `POST /a2a/seller_agent` (broken envelope) — task: still `completed` (LLM handled it gracefully)

**The JSON-RPC body:**
```json
{"jsonrpc": "2.0", "method": "message/send",
 "params": {"message": {"parts": [{"kind": "text", "text": "...offer JSON..."}]}}}
```

**Response contains:**
- `status: "completed"` — the agent processed the request
- `contextId` — reuse for round 2 (demo 11)
- `artifacts` — the counter-offer text as a durable output
- `history` — full message exchange

**Key insight:** `completed` means the PROTOCOL worked — not that the negotiation succeeded. Bad data → LLM says "please try again" (completed). Protocol error → `failed`. Business logic is in the content, not the status.

---

## Slide 57: Demo 10 — Results

**Title:** Demo 10 — What the Wire Looks Like

**Body:**

**Valid offer response:**
```
status: "completed"
contextId: "4f0fff3e-..."     ← reuse for round 2
artifacts: [{text: "Counter-offer at $477,000..."}]
history: [Message(user), Message(agent)]
```

**Broken envelope response:**
```
status: "completed" (NOT failed!)
artifacts: [{text: "Could you please resend your offer?"}]
```

**Why still completed?** The A2A protocol layer worked correctly — valid JSON-RPC, valid Message. The content was garbage, but the LLM coped. Tasks only `fail` on protocol errors or server crashes.

**The response structure:**

| Field | What it contains |
|-------|-----------------|
| `status` | Task state: completed/failed |
| `contextId` | Thread ID for multi-turn (demo 11) |
| `history` | All Messages exchanged |
| `artifacts` | Durable outputs (the counter-offer) |

---

## Slide 58: Demo 11 — Context Threading (Concept)

**Title:** Demo 11 — Multi-Turn Negotiations via contextId

**Body:**

Three rounds, same `contextId`, the seller remembers everything:

| Round | Offer | Seller's Response |
|-------|-------|------------------|
| 1 | $432K | "Below floor ($445K). Counter at $477K." |
| 2 | $440K | "STILL below $445K. Consider $477K." |
| 3 | $446K | **"Above $445K. We ACCEPT! Congratulations!"** |

```
Round 1: POST → server assigns contextId
Round 2: POST + contextId → seller remembers round 1
Round 3: POST + contextId → seller sees full history → ACCEPTS
```

Without `contextId`, the seller would counter at $477K every time — no memory of prior offers.

---

## Slide 59: Demo 11 — Results

**Title:** Demo 11 — Why Memory Matters

**Body:**

**Same contextId across all 3 rounds:** `4498d50f-a61e-4a17-8c84-0ea13d49a283`

The seller accepted in round 3 because it remembered:
- Round 1: MCP tool returned floor price = $445K
- Round 2: buyer came up from $432K to $440K (still below)
- Round 3: $446K > $445K → ACCEPT immediately

**contextId = A2A's session_id.** It ties independent HTTP requests into one coherent conversation. The same concept as ADK's session state (d03), but across network boundaries.

---

## Slide 60: Demo 12 — Parts & Artifacts (Concept)

**Title:** Demo 12 — Multi-Part Messages + Durable Outputs

**Body:**

Sent a message with TWO Parts — same offer in two formats:

```
parts[0] = TextPart("Final-and-best at $445k")     ← human-readable
parts[1] = DataPart({hint: "machine copy", offer: {...}})  ← structured JSON
```

| Part type | Purpose | Who reads it |
|-----------|---------|-------------|
| TextPart | Human-readable text | The LLM |
| DataPart | Structured JSON | Code / downstream systems |
| FilePart | Binary (PDF, image) | Not used in this demo |
| Artifact | Durable output on Task | Anyone who fetches the Task later |

Parts = conversational (in Messages). Artifacts = deliverables (on Tasks).

---

## Slide 61: Demo 12 — Results

**Title:** Demo 12 — Acceptance at $445K

**Body:**

**Response history showed the full agent processing:**
1. User message: 2 parts (TextPart + DataPart)
2. Agent MCP tool calls: 3 DataParts (get_market_price, get_minimum_acceptable_price, calculate_discount)
3. Agent tool results: 3 DataParts (structured responses)
4. Agent final text: "We accept your offer of $445,000!"

**Artifact:** Same acceptance text attached as durable output:
```json
{"artifactId": "f7ae8903-...", "parts": [{"kind": "text", "text": "We accept..."}]}
```

**$445K = exact floor → immediate acceptance.** MCP tool confirms min = $445K. Offer matches. Seller accepts.

Tool calls appear as DataParts in history — you can programmatically inspect what tools were called.

---

## Slide 62: Demo 13 — Streaming (Concept)

**Title:** Demo 13 — Real-Time Task Lifecycle via SSE

**Body:**

`message/stream` vs `message/send`:
- **send**: POST → wait → one JSON response
- **stream**: POST → SSE connection → events arrive incrementally

Requires `capabilities.streaming: true` in `agent.json`.

**What you get in real time:**
- Task state transitions (submitted → working → completed)
- Tool call intermediate results
- Token usage per LLM call
- Artifact delivery BEFORE task completes
- `final: true` marker on the last event

Streaming is for UX ("seller is thinking..."), not correctness — `message/send` gives the same result.

---

## Slide 63: Demo 13 — Results

**Title:** Demo 13 — 7 Events for One Request

**Body:**

| Event | Kind | State |
|-------|------|-------|
| 1 | status-update | **submitted** (task created) |
| 2 | status-update | **working** (agent started) |
| 3 | status-update | **working** (tool call + token usage) |
| 4 | status-update | **working** (tool results) |
| 5 | status-update | **working** (LLM reasoning) |
| 6 | **artifact-update** | counter-offer text delivered |
| 7 | status-update | **completed** (`final: true`) |

With `message/send` you'd see only the final result. Streaming shows every step:
- Each MCP tool call = one event
- Each LLM call = one event (with `promptTokenCount` in metadata)
- Artifact arrives BEFORE completion (event 6 before event 7)

---

## Slide 64: Buyer vs Seller — Information Asymmetry

**Title:** Information Asymmetry — The Design Point

**Body:**

The buyer and seller see DIFFERENT tools — that's the key architectural decision:

```
buyer_agent/agent.py                    seller_agent/agent.py
─────────────────────                   ─────────────────────
MCPToolset(pricing_server)              MCPToolset(pricing_server)
                                        MCPToolset(inventory_server)  ← EXTRA

_BUYER_ALLOWED_TOOLS = {                _SELLER_ALLOWED_TOOLS = {
  "get_market_price",                     "get_market_price",
  "calculate_discount",                   "calculate_discount",
  "get_property_tax_estimate",            "get_inventory_level",
}                                         "get_minimum_acceptable_price",  ← SECRET
                                        }
```

**What each side knows:**

| Data | Buyer | Seller |
|------|-------|--------|
| Market price ($462K) | Yes | Yes |
| Discount analysis | Yes | Yes |
| Inventory levels | No | Yes |
| **Floor price ($445K)** | **No** | **Yes** |

The seller knows the minimum acceptable price. The buyer has to guess. This mirrors real-world negotiations where each party has private information.

**How it's enforced:**
- `before_tool_callback` = allowlist (d08 pattern). Even if the LLM tries to call `get_minimum_acceptable_price`, the callback blocks it and returns `{"error": "not authorized"}`.
- The LLM can't bypass a callback — it's deterministic, not suggestive.

```bash
# Run both standalone agents:
adk web m3_adk_multiagents/negotiation_agents/
# Select buyer_agent or seller_agent from the dropdown
```

**Try these:**

| Agent | Question | Expected |
|-------|----------|----------|
| buyer_agent | "What's 742 Evergreen Terrace worth?" | Calls `get_market_price` → $462K |
| buyer_agent | "I want to make an offer. What do you recommend?" | Calls `calculate_discount` → ~$425K |
| seller_agent | "Buyer offers $440,000 with 30-day close" | Calls 3 tools in parallel, counters at $477K |
| seller_agent | "Buyer increases to $446,000" | Accepts (above $445K floor) |

---

## Slide 65: Buyer & Seller — Results

**Title:** Buyer & Seller — What We Observed

**Body:**

**Buyer agent (8 events, 2 queries):**
```
Query 1: "What's 742 Evergreen Terrace worth?"
  → get_market_price → $462K estimated value, $485K list price
  → "The estimated market value is $462,000..."

Query 2: "I want to make an offer. What do you recommend?"
  → calculate_discount(base=485K, balanced, 18 DOM, good condition)
  → "I recommend an initial offer of ~$425,000 (12% below asking)"
```

**Seller agent (6 events, 2 queries):**
```
Query 1: "Buyer offers $440,000 with 30-day close"
  → 3 tools called IN PARALLEL:
    get_market_price + get_inventory_level + get_minimum_acceptable_price
  → "The offer of $440,000 is below our minimum of $445,000.
     COUNTER at $477,000."

Query 2: "Buyer increases to $446,000"
  → NO tool calls (remembered floor from query 1)
  → "The offer of $446,000 is above $445,000. ACCEPT."
```

**Key observations:**
1. **Seller called 3 tools in ONE turn** — GPT-4o parallelized the independent lookups. Unlike d09 (where parallel was dangerous), here all 3 tools are truly independent.
2. **Seller remembered the floor on query 2** — session state kept the conversation history, so it didn't need to re-call `get_minimum_acceptable_price`.
3. **Buyer never saw the floor** — its allowlist only permits pricing tools, not inventory tools.

---

## Slide 66: Negotiation Orchestrator — Composition

**Title:** The Orchestrator — Every Demo in One File

**Body:**

```python
# negotiation/agent.py — the complete composition

# Structured decision tool — no text parsing
def submit_decision(action: str, price: int, tool_context: ToolContext) -> dict:
    tool_context.state["seller_decision"] = {"action": action.upper(), "price": price}
    return {"recorded": action.upper(), "price": price}

def _check_agreement(callback_context):
    decision = callback_context.state.get("seller_decision")
    if isinstance(decision, dict) and decision.get("action") == "ACCEPT":
        callback_context.actions.escalate = True

buyer = LlmAgent(output_key="buyer_offer",
    tools=[MCPToolset(pricing_server)], ...)     # ← real MCP tools
seller = LlmAgent(output_key="seller_response",
    tools=[MCPToolset(pricing), MCPToolset(inventory), submit_decision],
    after_agent_callback=_check_agreement, ...)  # ← reads structured state

root_agent = LoopAgent(sub_agents=[SequentialAgent([buyer, seller])],
    max_iterations=5)
```

**Every demo concept appears here:**

| Concept | Where |
|---------|-------|
| LlmAgent (d01) | buyer, seller |
| MCPToolset (d02) | buyer: pricing. seller: pricing + inventory |
| `output_key` + `{placeholder}` (d04) | buyer writes → seller reads |
| SequentialAgent (d04) | buyer → seller per round |
| LoopAgent + escalation (d06) | negotiation rounds |
| Callbacks (d08) | tool allowlists + agreement check |
| `submit_decision` tool | Structured signal — not text parsing |

**Diagram: How It All Connects**
```
         LoopAgent (d06)  max_iterations=5
         ┌───────────────────────────────────────────┐
         │  SequentialAgent (d04)                     │
         │  ┌───────────────┐  ┌───────────────────┐ │
    ┌───▶│  │ buyer (d01)   │─▶│ seller (d01)      │ │
    │    │  │ +MCPToolset   │  │ +MCPToolset ×2    │ │
    │    │  │  (d02)        │  │  (d02)            │ │
    │    │  │ +allowlist    │  │ +allowlist (d08)  │ │
    │    │  │  (d08)        │  │ +submit_decision  │ │
    │    │  └───────────────┘  └────────┬──────────┘ │
    │    │                              │            │
    │    │           after_agent_callback             │
    │    │           state["seller_decision"]         │
    │    │           == {"action": "ACCEPT"}?         │
    │    └───────────────────────────────────────────┘
    │                       │
    │                  escalate?
    │                  NO │  YES
    └─────────────────────┘    → STOP
```

**Why `submit_decision` instead of text parsing?** The seller's MCP tool returns "minimum acceptable price" — which contains "ACCEPT" as a substring. Text parsing (`"ACCEPT" in response`) would false-trigger on every counter-offer that mentions the floor. The `submit_decision` tool writes a structured dict to state — the callback reads `state["seller_decision"]["action"]`, not prose.

**The `{seller_response}` pitfall:** On round 1, the buyer's instruction has `{seller_response}` but no seller has responded yet. ADK throws `Context variable not found`. Fix: `before_agent_callback` initializes the key with a default value.

**Try:** Select `negotiation` from dropdown → type "Start negotiation for 742 Evergreen Terrace"

Watch Events for MCP tool calls + `submit_decision` calls. Check State tab for `seller_decision` dict.

---

## Slide 67: Negotiation — Live Run Results

**Title:** Negotiation — What Actually Happened

**Body:**

**2 negotiation rounds → agreement at $445,000 (with MCP tools + structured decisions):**

| Round | Buyer (MCP tools called) | Seller (MCP tools called) | Decision |
|-------|--------------------------|---------------------------|----------|
| 1 | $425,800 (`get_market_price` + `calculate_discount`) | `get_minimum_acceptable_price` + `get_inventory_level` → `submit_decision(COUNTER, 477000)` | COUNTER $477K |
| 2 | $445,000 (no tools — jumped to target) | `submit_decision(ACCEPT, 445000)` | **ACCEPT $445K** |

**Event flow (20 events):**
```
Event 1     | user   → "Start negotiation"
Event 3     | buyer  → tool_call: get_market_price + calculate_discount
Event 4     | buyer  → tool_results (market data)
Event 5     | buyer  → "Offer: $425,800..."             → state["buyer_offer"]
Event 6     | seller → tool_call: get_minimum_acceptable_price + get_inventory_level
Event 7     | seller → tool_results (floor=$445K, hot market)
Event 8     | seller → "COUNTER $477,000" + tool_call: submit_decision(COUNTER, 477000)
Event 9     | seller → tool_result: {recorded: COUNTER}  → callback: no escalation
Event 10    | seller → confirms counter
Event 11    | buyer  → "Offer: $445,000..."             → overwrites buyer_offer
Event 12    | seller → "Accepted" + tool_call: submit_decision(ACCEPT, 445000)
Event 13    | seller → tool_result: {recorded: ACCEPT}  → callback: ESCALATE!
Event 14    | seller → confirms acceptance
Event 15-20 | buyer/seller → post-acceptance chatter (current iteration completes)
```

**State tab after completion:**
```json
{"seller_decision": {"action": "ACCEPT", "price": 445000}}
```

**Observations:**
1. **MCP tools grounded every decision.** The buyer used `get_market_price` ($462K estimated) to justify $425K. The seller used `get_minimum_acceptable_price` ($445K floor) to set the COUNTER.
2. **`submit_decision` is the structured signal.** The callback reads `state["seller_decision"]["action"]` — a dict, not free text. No risk of "minimum acceptable price" false-triggering.
3. **Buyer jumped from $425K to $445K in round 2.** With MCP data, it had enough confidence to skip incremental increases.
4. **Post-acceptance chatter still occurs.** Escalation stops the NEXT iteration, not the current one — the remaining sub-agents in the SequentialAgent complete.

---

## Slide 68: A2A Orchestrated Negotiation

**Title:** Demo 14 — Full Negotiation Over A2A

**Body:**

```bash
# Terminal 1:
adk web --a2a m3_adk_multiagents/negotiation_agents/

# Terminal 2:
python m3_adk_multiagents/a2a_14_orchestrated_negotiation.py
```

The script discovers BOTH agents via Agent Cards, then orchestrates multi-round negotiation over HTTP:

```
Step 1: Discover agents
  GET buyer_agent/.well-known/agent-card.json   → skills: [Property Valuation]
  GET seller_agent/.well-known/agent-card.json  → skills: [Seller Negotiation]

Step 2: Multi-round negotiation
  Round 1: POST buyer_agent  → "Offer $425K"    (buyer calls MCP tools)
           POST seller_agent → "COUNTER $477K"  (seller calls MCP tools)
  Round 2: POST buyer_agent  → "Offer $445K"
           POST seller_agent → "ACCEPT $445K"   → DEAL REACHED
```

**Key A2A details:**
- **Separate contextIds** — buyer thread: `e4c33941...`, seller thread: `41036068...`
- **The script acts as matchmaker** — neither agent knows about the other
- **Each agent calls its own MCP tools** — buyer: pricing, seller: pricing + inventory
- **4 total A2A messages** for a complete negotiation

This is the production pattern: agents as network services, discovered via Agent Cards, communicating via JSON-RPC.

---

# PART 4 — SUMMARY & WRAP-UP (Slides 69–71)

---

## Slide 69: The Full Journey

**Title:** From `while True` to Production Agents

**Body:**

```
Module 1                Module 2                Module 3
─────────               ─────────               ─────────
while True              MCP servers             ADK + A2A
  ├ regex parsing         ├ list_tools            ├ LlmAgent
  ├ "DEAL" in msg         ├ call_tool             ├ MCPToolset
  └ hardcoded prices      ├ pricing_server        ├ LoopAgent
                          └ inventory_server      ├ submit_decision
                                                  ├ callbacks
                                                  ├ Agent Cards
                                                  └ message/send
    ▼                       ▼                       ▼
  BREAKS                  DATA LAYER              ORCHESTRATION
  (by design)             (external tools)        (production agents)
```

**The progression of the floor price:**
| Module | Where $445K lives | Who can see it |
|--------|-------------------|----------------|
| M1 | `SELLER_MIN_PRICE = 445_000` (Python constant) | Everyone reading source |
| M2 | `get_minimum_acceptable_price()` (MCP server) | Anyone who calls the tool |
| M3 | Same MCP tool + `before_tool_callback` allowlist | **Seller only** |

Same data. Increasingly better architecture.

---

## Slide 70: Problem → Solution Map

**Title:** Every M1 Problem, Solved

**Body:**

| # | Problem (M1) | Solution (M2/M3) |
|---|-------------|------------------|
| 1 | Raw strings | A2A TextPart + DataPart |
| 2 | No schema | Pydantic / JSON Schema from type hints |
| 3 | No state machine | LoopAgent + SequentialAgent |
| 4 | No turn limits | `max_iterations = 5` |
| 5 | Fragile regex | `submit_decision(price=445000)` typed field |
| 6 | No termination guarantee | `escalate = True` + `_check_agreement` |
| 7 | Silent failures | Pydantic validation + tool callbacks |
| 8 | Hardcoded prices | MCP `get_market_price()` + `get_minimum_acceptable_price()` |
| 9 | No observability | ADK event stream + A2A task lifecycle |
| 10 | No evaluation | Session analytics via `session.db` |

**The `submit_decision` origin story:** In M3 development, `"ACCEPT" in response` matched "minimum acceptable price" — the exact same false positive as M1's `"DEAL" in message`. Textbook M1 → M3 connection.

---

## Slide 71: Three Protocols Cheat Sheet

**Title:** MCP · ADK · A2A — Quick Reference

**Body:**

| | MCP | A2A |
|---|---|---|
| **Connects** | Agent ↔ Tool | Agent ↔ Agent |
| **Discovery** | `list_tools` → JSON Schema | Agent Card → skills |
| **Invocation** | `call_tool(name, args)` | `message/send` (JSON-RPC) |
| **Wire format** | JSON-RPC 2.0 | JSON-RPC 2.0 |
| **Transport** | stdio / SSE / Streamable HTTP | HTTP |
| **State** | Stateless | `contextId` threads |
| **SDK** | `mcp` Python package | `a2a-sdk` Python package |

**ADK connects them:**

| ADK Component | What it does |
|---------------|-------------|
| `LlmAgent` | Model + instruction + tools |
| `MCPToolset` | Auto-discover + call MCP tools |
| `SequentialAgent` | Pipeline: A → B → C |
| `ParallelAgent` | Fan-out: A, B, C concurrent |
| `LoopAgent` | Iterate until escalation |
| `AgentTool` | Agent wrapped as function |
| Callbacks | Deterministic policy enforcement |
| `adk web --a2a` | Auto-generate A2A endpoints |


