# Module 3 — Slide Deck Specification

---

## Slide 1: Module 3 Title

**Title:** Module 3 — Google ADK + A2A Protocol

**Body:**

**The goal:** Build a complete multi-agent negotiation system using Google ADK

By the end of this module you'll have:
- A **buyer agent** with MCP pricing tools
- A **seller agent** with MCP pricing + inventory tools (information asymmetry)
- A **negotiation orchestrator** that runs multi-round buyer ↔ seller negotiation
- All exposed as **A2A network services** with auto-generated Agent Cards

Every concept is taught through a demo first, then composed into the final system.

**Diagram: Module 3 Architecture**
```
┌─────────────────────────────────────────────────────┐
│              negotiation_agents/                     │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐   │
│  │  buyer    │    │  seller   │    │ negotiation   │   │
│  │  agent    │    │  agent    │    │ orchestrator  │   │
│  │          │    │          │    │              │   │
│  │ LlmAgent │    │ LlmAgent │    │  LoopAgent   │   │
│  │ +MCP     │    │ +MCP×2   │    │  +Sequential │   │
│  │ pricing  │    │ pricing  │    │  (buyer→     │   │
│  │          │    │ +inventory│    │   seller)    │   │
│  └──────────┘    └──────────┘    └──────────────┘   │
│       │               │                             │
│       │    MCP         │    MCP                      │
│       ▼               ▼                             │
│  pricing_server   pricing_server                     │
│  (M2)             + inventory_server (M2)            │
└─────────────────────────────────────────────────────┘
         │
         │  adk web --a2a
         ▼
   A2A endpoints + Agent Cards (auto-generated)
```

---

## Slide 2: The Final System (What We're Building Toward)

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

## Slide 3: Learning Path — Demo by Demo

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

## Slide 4: Demo 01 — Basic LlmAgent (Concept)

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

## Slide 5: Demo 01 — Results

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

## Slide 6: Demo 02 — MCP Tools in ADK (Concept)

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

## Slide 7: Demo 02 — Results

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

## Slide 8: Demo 03 — Sessions & State (Concept)

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

## Slide 9: Demo 03 — Results

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

## Slide 10: Demo 04 — SequentialAgent (Concept)

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

## Slide 11: Demo 04 — Results

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

## Slide 12: Demo 05 — ParallelAgent (Concept)

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

## Slide 13: Demo 05 — Results

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

## Slide 14: Demo 06 — LoopAgent (Concept)

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

## Slide 15: Demo 06 — Results

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

## Slide 16: Demo 07 — Agent-as-Tool (Concept)

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

## Slide 17: Demo 07 — Results

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

## Slide 18: Demo 08 — Callbacks (Concept)

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

## Slide 19: Demo 08 — Results

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

## Slide 20: Demo 09 — Event Stream (Concept)

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

## Slide 21: Demo 09 — Results

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

## Slide 22: What is A2A?

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

## Slide 23: Why A2A Matters

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

## Slide 24: Agent Card — The A2A Discovery Document

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

## Slide 25: A2A Demos Overview

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

## Slide 26: Demo 10 — A2A Wire Format

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

## Slide 27: Demo 10 — Results

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

## Slide 28: Demo 11 — Context Threading (Concept)

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

## Slide 29: Demo 11 — Results

**Title:** Demo 11 — Why Memory Matters

**Body:**

**Same contextId across all 3 rounds:** `4498d50f-a61e-4a17-8c84-0ea13d49a283`

The seller accepted in round 3 because it remembered:
- Round 1: MCP tool returned floor price = $445K
- Round 2: buyer came up from $432K to $440K (still below)
- Round 3: $446K > $445K → ACCEPT immediately

**contextId = A2A's session_id.** It ties independent HTTP requests into one coherent conversation. The same concept as ADK's session state (d03), but across network boundaries.

---

## Slide 30: Demo 12 — Parts & Artifacts (Concept)

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

## Slide 31: Demo 12 — Results

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

## Slide 32: Demo 13 — Streaming (Concept)

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

## Slide 33: Demo 13 — Results

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

## Slide 34: Buyer vs Seller — Information Asymmetry

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

## Slide 35: Buyer & Seller — Results

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

## Slide 36: Negotiation Orchestrator — Composition

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

## Slide 37: Negotiation — Live Run Results

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

## Slide 38: A2A Orchestrated Negotiation

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

## Slide 39: Exercises

**Title:** Hands-On Exercises

**Body:**

| # | Exercise | Difficulty | What you build |
|---|----------|-----------|---------------|
| 1 | Tool Agent | Starter | Two cooperating tools (estimate + mortgage) |
| 2 | Stateful Offers | Core | Offer tracking with regression warnings |
| 3 | Research Pipeline | Core | SequentialAgent + optional ParallelAgent |
| 4 | Callback Guard | Core | Argument validation on buyer agent |
| 5 | Fetch Agent Card | Core | Programmatic A2A discovery |

Each exercise has: step-by-step instructions, verify checklist, reflection question, and a matching solution.

Exercise 3 is the most interesting — it combines d04 + d05 patterns. Exercise 5 bridges to the A2A section.
