# Module 3 — ADK Multi-Agents & A2A Protocol (`m3_adk_multiagents`)

**Requires:** `OPENAI_API_KEY` set as an environment variable

This module teaches Google's Agent Development Kit (ADK) from first principles, then shows how agents communicate over the A2A protocol.

---

## What this module teaches

| Concept | Where you learn it |
|---|---|
| `LlmAgent` — the core building block | Demo 01 (basic agent) |
| `MCPToolset` — auto-discover MCP tools | Demo 02, `negotiation_agents/buyer_agent`, `negotiation_agents/seller_agent` |
| Sessions & state — persistence across turns | Demo 03 |
| `SequentialAgent`, `ParallelAgent`, `LoopAgent` | Demos 04–06 |
| `AgentTool` — agent-as-a-callable-tool | Demo 07 |
| Callbacks — policy hooks (PII, allowlists) | Demo 08 |
| ADK event stream — tool calls, state deltas | Demo 09 |
| A2A wire format & task lifecycle | Demo 10 (terminal script) |
| A2A context threading | Demo 11 (terminal script) |
| A2A parts & artifacts | Demo 12 (terminal script) |
| A2A streaming (`message/stream`) | Demo 13 (terminal script) |
| A2A orchestrated negotiation | Demo 14 / `a2a_14_orchestrated_negotiation.py` |
| Full negotiation orchestration | `negotiation_agents/negotiation` |

---

## Directory structure

```
m3_adk_multiagents/
  negotiation_agents/              ← adk web negotiation_agents/  (3 agents in dropdown)
    buyer_agent/agent.py           LlmAgent + MCPToolset (pricing)
    seller_agent/agent.py          LlmAgent + MCPToolset (pricing + inventory)
    negotiation/agent.py           LoopAgent ↔ SequentialAgent + MCP tools + submit_decision
  adk_demos/                       ← adk web adk_demos/  (9 agents in dropdown)
    d01_basic_agent/agent.py       Bare LlmAgent + function tool
    d02_mcp_tools/agent.py         LlmAgent + MCPToolset (pricing server)
    d03_sessions_state/agent.py    ToolContext: read/write session state
    d04_sequential/agent.py        SequentialAgent pipeline
    d05_parallel/agent.py          ParallelAgent fan-out
    d06_loop/agent.py              LoopAgent with escalation callback
    d07_agent_as_tool/agent.py     AgentTool wrapper
    d08_callbacks/agent.py         before_model / before_tool / after_tool
    d09_event_stream/agent.py      ADK event stream: tool calls, state deltas, markers
    a2a_10_wire_lifecycle.py       Terminal script: raw JSON-RPC + task states
    a2a_11_context_threading.py    Terminal script: contextId across rounds
    a2a_12_parts_and_artifacts.py  Terminal script: multi-part messages + artifacts
    a2a_13_streaming.py            Terminal script: message/stream SSE events
  a2a_14_orchestrated_negotiation.py  Terminal script: full buyer↔seller negotiation over A2A
  exercises/
  solution/
  notes/
```

---

## The ADK Web UI

When you run `adk web`, a browser UI opens at `http://localhost:8000`. Here's what each element does:

### Top bar

| Element | What it does |
|---------|-------------|
| **Agent dropdown** (top-left) | Pick which agent to chat with. Each subfolder with `__init__.py` + `agent.py` appears here |
| **Session dropdown** | Shows current session ID. Each session has its own conversation history and state |
| **New Session** button | Start a fresh conversation (clears history and state) |
| **Streaming** toggle (top-right) | When on, responses stream token by token. When off, you get the full response at once |

### Tab bar (below top bar)

| Tab | What it shows |
|-----|---------------|
| **Events** | The conversation flow: user messages, agent responses, tool call badges (⚡ = called, ✓ = completed). This is the main view |
| **Traces** | OpenTelemetry-style trace spans for each turn — useful for debugging latency |
| **Info** | The agent's resolved config: model, system instruction, discovered tools with full JSON schemas |
| **State** | Current session state dict — shows all keys written by `output_key` or `ToolContext.state` |
| **Artifacts** | Any artifacts saved during the session (binary blobs, generated files) |
| **Evals** | Agent evaluation runs (not used in this workshop) |

### Left panel (event inspector)

Click any event number in the conversation to see its raw details:
- **Event N of M** — navigate through all internal events (includes MCP handshake, tool calls, LLM requests, state deltas)
- Shows the full event payload: `author`, `content.parts`, `actions.stateDelta`
- The high event count (100+) is normal — it includes MCP protocol frames, not just conversation turns

### Right panel (conversation)

The chat view showing:
- **User messages** (right, blue) — what you typed
- **Agent responses** (left, dark) — the LLM's final text
- **Tool call badges** — ⚡ `tool_name` (request) → ✓ `tool_name` (result) — shows which tools the LLM called and in what order

### Teaching tip

> Tell students to focus on the **right panel** for understanding agent behavior, and use the **Info tab** to see what tools the agent has access to. The left panel event inspector is for deep debugging (demo d09 teaches this explicitly).

### Runtime files (`.adk/`)

When `adk web` runs, it creates a `.adk/` directory inside the agents folder containing `session.db` (a SQLite database for session persistence). This is a **runtime artifact** — not source code. It's in `.gitignore` and gets recreated automatically on each run. You can delete it safely, or click "New Session" in the UI to start fresh.

---

## How to run

### ADK demos (01–08) — interactive web UI

```bash
# Run ALL demos (9 agents appear in the dropdown)
adk web m3_adk_multiagents/adk_demos/

# Open http://localhost:8000, pick a demo from the dropdown, chat with it
```

### Agents (buyer, seller, negotiation) — interactive web UI

```bash
# Run all 3 agents
adk web m3_adk_multiagents/negotiation_agents/

# With A2A endpoints enabled (serves Agent Cards automatically)
adk web --a2a m3_adk_multiagents/negotiation_agents/
```

With `--a2a`, each agent gets an Agent Card at:
- `http://localhost:8000/a2a/buyer_agent/.well-known/agent-card.json`
- `http://localhost:8000/a2a/seller_agent/.well-known/agent-card.json`
- `http://localhost:8000/a2a/negotiation/.well-known/agent-card.json`

### A2A protocol demos (09–12) — terminal scripts

```bash
# Terminal 1 — start agents with A2A endpoints
adk web --a2a m3_adk_multiagents/negotiation_agents/

# Terminal 2 — run the A2A demos
python m3_adk_multiagents/adk_demos/a2a_10_wire_lifecycle.py --seller-url http://127.0.0.1:8000/a2a/seller_agent
python m3_adk_multiagents/adk_demos/a2a_11_context_threading.py --seller-url http://127.0.0.1:8000/a2a/seller_agent
python m3_adk_multiagents/adk_demos/a2a_12_parts_and_artifacts.py --seller-url http://127.0.0.1:8000/a2a/seller_agent
python m3_adk_multiagents/adk_demos/a2a_13_streaming.py --seller-url http://127.0.0.1:8000/a2a/seller_agent

# A2A orchestrated negotiation (buyer ↔ seller via Agent Cards)
python m3_adk_multiagents/a2a_14_orchestrated_negotiation.py
```

---

## Agent details

### `negotiation_agents/buyer_agent/` — Buyer (MCPToolset + allowlist)

Declarative `LlmAgent` with `MCPToolset` connecting to the pricing MCP server. A `before_tool_callback` enforces the buyer's tool allowlist — the buyer can never call `get_minimum_acceptable_price`.

### `negotiation_agents/seller_agent/` — Seller (dual MCPToolsets + information asymmetry)

Same pattern, but connects to **two** MCP servers (pricing + inventory). The seller has access to `get_minimum_acceptable_price` — the buyer does not. This is the same information asymmetry from Module 2, now declarative.

### `negotiation_agents/negotiation/` — Orchestrator (LoopAgent + SequentialAgent + MCP)

A `LoopAgent` wrapping a `SequentialAgent(buyer → seller)` where both agents have real MCP tools. The buyer calls `get_market_price` and `calculate_discount` before each offer. The seller calls `get_minimum_acceptable_price` and `get_inventory_level`, then calls a `submit_decision` tool to write `{"action": "ACCEPT", "price": 445000}` to state. The `after_agent_callback` reads this structured dict — not free text — to detect agreement.

---

## Demos walkthrough

| # | ADK concept | Key takeaway |
|---|---|---|
| 01 | `LlmAgent` + function tool | Simplest possible agent — declare and go |
| 02 | `MCPToolset` | ADK spawns MCP server, discovers tools automatically |
| 03 | `ToolContext` + state | Tools can read/write session state that persists across turns |
| 04 | `SequentialAgent` | Pipeline: each agent's `output_key` feeds the next via `{placeholder}` |
| 05 | `ParallelAgent` | Fan-out: concurrent agents write to different state keys |
| 06 | `LoopAgent` | Iterate until `callback_context.actions.escalate = True` |
| 07 | `AgentTool` | Wrap an agent as a callable tool — hierarchical delegation |
| 08 | Callbacks | `before_model` (PII redaction), `before_tool` (allowlist), `after_tool` (logging) |
| 09 | Event stream | See ADK events: tool calls, state deltas, final response markers |
| 10 | A2A wire format | Hand-craft JSON-RPC, see Agent Card discovery, task state transitions |
| 11 | A2A context threading | `contextId` ties multiple rounds into one conversation |
| 12 | A2A parts & artifacts | Multi-part Messages (TextPart + DataPart), inspect Artifacts |
| 13 | A2A streaming | `message/stream` SSE events — see status transitions in real time |
| 14 | A2A orchestration | Full buyer↔seller negotiation — Agent Card discovery + multi-round A2A messages |

---

## Exercises

Four core exercises plus one stretch — designed for the **2-hour follow-up review session** held a few days after the workshop. Try them as homework; the instructor will walk through and run each solution live in class.

Each exercise extends the real-estate codebase with a production-relevant pattern. Difficulty mix: 1 starter, 3 core, 1 stretch.

| Exercise | Difficulty | Reinforces | Task |
|---|---|---|---|
| [`ex01_budget_cap_callback.md`](exercises/ex01_budget_cap_callback.md) | `[Starter]` | Demo 08 (callbacks) | Write a `before_tool_callback` that blocks `submit_decision` calls with `price > $460,000`. Forces the buyer to obey budget *deterministically*, not just via instruction. |
| [`ex02_stuck_detection.md`](exercises/ex02_stuck_detection.md) | `[Core]` | Demos 03, 06 (state, LoopAgent escalation) | Modify the orchestrator to track offer history across rounds and escalate early when 3+ consecutive rounds show <$1K of movement. The production "stuck-agent detection" pattern. |
| [`ex03_a2a_multiround_client.md`](exercises/ex03_a2a_multiround_client.md) | `[Core]` | Demos 10, 11, 14 (A2A wire format, contextId threading) | Write a Python script that drives buyer ↔ seller via A2A `message/send`, threading by `contextId`. The matchmaker pattern, end to end. |
| [`ex04_mediator_agent.md`](exercises/ex04_mediator_agent.md) | `[Core]` | Demo 07 (`AgentTool`) | Build a mediator that wraps buyer + seller as `AgentTool`s and proposes a midpoint price. Demonstrates hierarchical delegation as the alternative to peer-to-peer A2A. |
| [`stretch_streaming_client.md`](exercises/stretch_streaming_client.md) | `[Stretch]` | Demo 13 (A2A streaming) | Convert the multi-round client to use `message/stream` instead of `message/send`. Render task lifecycle events to console as they arrive. |

Each solution lives in `solution/<exercise_name>/` as a self-contained, runnable package — most are launchable directly with `adk web solution/<exercise_name>/`. The instructor walks through each solution live during the review session.

---

## A2A in one diagram

```
adk web --a2a negotiation_agents/
  ├─ buyer_agent   → GET /.well-known/agent-card.json
  ├─ seller_agent  → GET /.well-known/agent-card.json
  └─ negotiation   → GET /.well-known/agent-card.json

Demo 09 (terminal):
  1. GET /seller_agent/.well-known/agent-card.json  → discover capabilities
  2. POST /seller_agent  (JSON-RPC message/send)    → send offer
  3. Response: Task { status: "completed", result: counter-offer }

Demo 10 (terminal):
  Round 1: POST → get contextId from response
  Round 2: POST + contextId → threaded conversation
  Round 3: POST + contextId → agreement or deadlock
```

Companion notes: [a2a_protocols.md](notes/a2a_protocols.md), [google_adk_overview.md](notes/google_adk_overview.md), [adk_quick_reference.md](notes/adk_quick_reference.md).
