# Real Estate Negotiation Workshop
## Learn MCP · A2A · LangGraph · Google ADK

A **4-hour hands-on workshop** teaching modern AI agent frameworks through a concrete, runnable project: an autonomous real estate negotiation between a Buyer Agent and a Seller Agent.

---

## What You'll Learn

| Concept | What It Is | How We Use It |
|---|---|---|
| **MCP** | Standard protocol for agents to access external tools | Agents query pricing/inventory servers via MCP |
| **A2A** | Agent-to-Agent communication patterns | Module 4 uses true networked A2A protocol transport (`a2a-sdk`) |
| **LangGraph** | Stateful multi-agent workflow orchestration | Module 3 is pure LangGraph state-driven multi-agent workflow |
| **Google ADK** | Production-grade agent framework | Alternative implementation using OpenAI-backed agents |

---

## The Scenario

**Property**: 742 Evergreen Terrace, Austin, TX 78701
*(4 BR / 3 BA / 2,400 sqft / Single Family / Built 2005)*

| Party | Goal | Starting Position | Walk-Away |
|---|---|---|---|
| **Buyer Agent** (GPT-4o) | Buy at lowest price | Offer $425,000 | Over $460,000 |
| **Seller Agent** (GPT-4o) | Sell at highest price | Counter $477,000 | Below $445,000 |

The negotiation runs for a maximum of **5 rounds**. Agents use real market data (via MCP) to justify every offer.

---

## Project Structure

Folders are numbered in teaching order. Each module introduces one new concept.

```
real-estate-negotiation-simulator/
│
├── m1_baseline/                       # MODULE 1 — Start here. Watch it break.
│   ├── README.md                      # Module guide for learners
│   ├── naive_negotiation.py           # Intentionally broken (10 failure modes)
│   ├── state_machine.py               # FSM that fixes termination
│   ├── exercises/                      # Hands-on coding exercises for Module 1
│   ├── solution/                       # Worked solutions for Module 1 exercises
│   └── notes/
│       └── agents_fundamentals.md     # Reference: agent fundamentals
│
├── m2_mcp/                            # MODULE 2 — External data via MCP
│   ├── README.md                      # Module guide for learners
│   ├── github_demo_client.py          # Connect to GitHub's real MCP server
│   ├── pricing_server.py              # Custom MCP: market pricing tools
│   ├── inventory_server.py            # Custom MCP: inventory + seller constraints
│   ├── exercises/                      # Hands-on coding exercises for Module 2
│   ├── solution/                       # Worked solutions for Module 2 exercises
│   └── notes/
│       └── mcp_deep_dive.md           # Reference: MCP protocol deep dive
│
├── m3_langgraph_multiagents/          # MODULE 3 — Pure LangGraph multi-agent workflow
│   ├── README.md                      # Module guide for learners
│   ├── negotiation_types.py           # Internal state/message types for LangGraph
│   ├── buyer_simple.py                # Buyer agent (OpenAI GPT-4o)
│   ├── seller_simple.py               # Seller agent (OpenAI GPT-4o)
│   ├── langgraph_flow.py              # LangGraph negotiation workflow
│   ├── exercises/                      # Hands-on coding exercises for Module 3
│   ├── solution/                       # Worked solutions for Module 3 exercises
│   └── notes/
│       └── langgraph_explained.md     # Reference: LangGraph deep dive
│
├── m4_adk_multiagents/                # MODULE 4 — Google ADK + true A2A protocol
│   ├── README.md                      # Module guide for learners
│   ├── buyer_adk.py                   # Buyer agent (OpenAI model via ADK)
│   ├── seller_adk.py                  # Seller agent (OpenAI model via ADK)
│   ├── a2a_protocol_seller_server.py  # True networked A2A protocol server (A2A SDK)
│   ├── a2a_protocol_http_orchestrator.py # Multi-round HTTP A2A orchestrator (ADK-native state)
│   ├── a2a_protocol_buyer_client_demo.py # Single-turn A2A protocol client demo
│   ├── exercises/                      # Hands-on coding exercises for Module 4
│   ├── solution/                       # Worked solutions for Module 4 exercises
│   └── notes/
│       ├── a2a_protocols.md           # Reference: A2A protocol deep dive
│       ├── google_adk_overview.md     # Reference: Google ADK overview
│       └── langgraph_adk_a2a_comparison.md  # Reference: cross-module comparison
│
├── m3_langgraph_multiagents/main_langgraph_multiagent.py             # Entry point — Module 3 (OpenAI + LangGraph)
├── m4_adk_multiagents/a2a_protocol_seller_server.py                  # Entry point — Module 4 (A2A server)
├── m4_adk_multiagents/a2a_protocol_http_orchestrator.py              # Entry point — Module 4 (A2A orchestrator)
├── m4_adk_multiagents/a2a_protocol_buyer_client_demo.py              # Entry point — Module 4 (single-turn demo)
├── INSTRUCTOR_GUIDE.md                # 4-hour workshop script for instructors
├── .env.example                       # Copy to .env and add your API keys
└── requirements.txt
```

If module files feel overwhelming, start with the README inside each module folder.

### Notes live inside each module

Each module has a `notes/` subfolder with reference documentation for that module's concepts.

| Module | Notes |
|---|---|
| `m1_baseline/notes/` | `agents_fundamentals.md` — agent fundamentals and failure modes |
| `m2_mcp/notes/` | `mcp_deep_dive.md` — MCP protocol and tool integration |
| `m3_langgraph_multiagents/notes/` | `langgraph_explained.md` — LangGraph orchestration deep dive |
| `m4_adk_multiagents/notes/` | `a2a_protocols.md` — A2A protocol deep dive |
| | `google_adk_overview.md` — Google ADK overview |
| | `langgraph_adk_a2a_comparison.md` — cross-module comparison (M3 vs M4) |

Module 4 has three notes because it spans two distinct topics: the A2A protocol standard and the ADK runtime.

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Node.js 18+ (for GitHub MCP demo in Module 2 only)

**Verify installation:**
```bash
python --version  # should be 3.10+
node --version    # should be 18+
```

### 2. Clone or open this repo

```bash
# If you already have the repo, skip this step
git clone <your-repo-url>
cd real-estate-negotiation-simulator
```

### 3. Create a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
```

**macOS/Linux:**
```bash
python3 -m venv .venv
```

### 4. Activate the virtual environment

**Windows (PowerShell):**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\.venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```bat
.venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

> **Tip**: Your prompt will change to show `(.venv)` when the environment is active.
> To deactivate at any time, run `deactivate`.

### 5. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Configure API keys

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**
```bash
cp .env.example .env
```

Then edit `.env` and set:
```env
OPENAI_API_KEY=sk-your-key-here
GITHUB_TOKEN=ghp-your-token-here   # Optional — Module 2 GitHub demo only
```

### 8. Run a smoke test

```bash
python m1_baseline/naive_negotiation.py
```

If Module 1 runs, your environment is ready.

### 9. Run the Workshop Modules in Order

```bash
# MODULE 1: Watch the naive version fail (no API keys needed)
python m1_baseline/naive_negotiation.py   # 10 failure modes
python m1_baseline/state_machine.py       # FSM termination guarantee

# MODULE 2: MCP protocol
python m2_mcp/github_demo_client.py       # GitHub MCP demo (needs GITHUB_TOKEN)
python m2_mcp/pricing_server.py           # Run MCP server standalone (stdio)
python m2_mcp/pricing_server.py --sse --port 8001  # SSE transport mode

# MODULE 3: Full simple version (needs OPENAI_API_KEY)
python m3_langgraph_multiagents/main_langgraph_multiagent.py

# MODULE 4: True A2A protocol demo (needs OPENAI_API_KEY)
python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102
python m4_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 5
# Optional: single-turn request/response demo
python m4_adk_multiagents/a2a_protocol_buyer_client_demo.py --seller-url http://127.0.0.1:9102
```

### 10. Module Exercises

Each module contains hands-on exercises with difficulty labels (`[Starter]`, `[Core]`, `[Stretch]`) and worked solutions.

| Module | Exercise | Difficulty | Task |
|---|---|---|---|
| M1 | `ex01_identify_failure_modes.md` | `[Core]` | Add a TIMEOUT terminal state to the FSM |
| M1 | `ex02_fsm_termination_check.md` | `[Core]` | Compare naive vs FSM failure modes |
| M1 | `ex03_stretch_fsm_different_language.md` | `[Stretch]` | Reimplement the FSM in TypeScript |
| M2 | `ex01_find_mcp_tool.md` | `[Starter]` | Add a new MCP tool to the pricing server |
| M2 | `ex02_compare_two_servers.md` | `[Core]` | Wire the new tool into the buyer agent |
| M2 | `ex03_stretch_build_appraisal_server.md` | `[Stretch]` | Build an appraisal MCP server from scratch |
| M3 | `ex01_trace_graph_flow.md` | `[Core]` | Add a deadlock-breaker conditional edge |
| M3 | `ex02_run_two_rounds.md` | `[Core]` | Add automatic convergence accept |
| M3 | `ex03_stretch_state_persistence.md` | `[Stretch]` | Add SQLite state persistence |
| M3 | `ex04_capstone_inspector_agent.md` | `[Stretch]` | Capstone: add an inspector agent |
| M4 | `ex01_fetch_agent_card.md` | `[Core]` | Fetch and inspect the A2A Agent Card |
| M4 | `ex02_one_round_orchestrator.md` | `[Core]` | Add a negotiation history endpoint |
| M4 | `ex03_stretch_docker_deployment.md` | `[Stretch]` | Deploy seller to Docker |

Solutions are in each module's `solution/` folder.

---

## Architecture Deep Dive

### Simple Version Flow

```
python m3_langgraph_multiagents/main_langgraph_multiagent.py
    │
    └── m3_langgraph_multiagents/langgraph_flow.py
          │
          ├── LangGraph Graph: START → init → [buyer ↔ seller] → END
          │
          ├── buyer_node (async)
          │     ├── BuyerAgent.make_initial_offer()
            │     │     ├── GPT-4o planner selects MCP tool(s) for this turn
            │     │     ├── MCP call(s) execute only for selected tool(s)
          │     │     └── OpenAI GPT-4o → decide offer price
          │     └── Returns A2AMessage (OFFER) → stored in LangGraph state
          │
          └── seller_node (async)
                ├── SellerAgent.respond_to_offer()
                │     ├── GPT-4o planner selects MCP tool(s) for this turn
                │     ├── MCP call(s) execute only for selected tool(s)
                │     └── OpenAI GPT-4o → decide counter-offer
                └── Returns A2AMessage (COUNTER_OFFER) → stored in LangGraph state
```

    Note: Module 3 currently runs in strict planner mode — MCP tools are invoked only when explicitly selected by the LLM planner for that round.

### ADK Version Flow

```
python m4_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 5
    │
    └── A2A HTTP orchestration loop
          │
          ├── BuyerAgentADK (async context manager)
          │     ├── MCPToolset → m2_mcp/pricing_server.py (discovers tools)
          │     ├── LlmAgent(model="gpt-4o", tools=[...])
          │     └── Runner → executes agent turns
          │           Agent autonomously calls MCP tools → model decides
          │
          └── SellerAgentADK (async context manager)
                ├── MCPToolset → m2_mcp/pricing_server.py
                ├── MCPToolset → m2_mcp/inventory_server.py (seller ONLY)
                ├── LlmAgent(model="gpt-4o", tools=[...merged...])
                └── Runner → executes agent turns
```

### MCP Data Flow

```
BUYER AGENT                     MCP Protocol                PRICING SERVER
──────────────────────          ─────────────────────       ──────────────────
"I need market data"
await call_tool(
  "get_market_price",    ──►   tools/call request    ──►   Executes Python fn
  {"address": "742..."}) ◄──   CallToolResult        ◄──   Returns dict
"Comps avg $462K,
 listing is 4.9% above
 market. I'll offer
 $425K."
```

### A2A Message Exchange

```
Round 1: BUYER  ──[OFFER: $425,000]──────────────────────────────► SELLER
Round 1: BUYER ◄──[COUNTER_OFFER: $477,000]───────────────────── SELLER
Round 2: BUYER  ──[OFFER: $438,000]──────────────────────────────► SELLER
Round 2: BUYER ◄──[COUNTER_OFFER: $465,000]───────────────────── SELLER
Round 3: BUYER  ──[OFFER: $449,000]──────────────────────────────► SELLER
Round 3: BUYER ◄──[ACCEPT: $449,000]──────────────────────────── SELLER
                   ✅ DEAL REACHED at $449,000
                   (Buyer saved $36,000 from listing price)
```

---

## Workshop Schedule (4 Hours)

See `INSTRUCTOR_GUIDE.md` for the full 4-hour script, talking points, and debrief questions.

| Time | Module | Topic | Key Files |
|---|---|---|---|
| 0:00–0:15 | Intro | What we're building | `README.md` |
| 0:15–0:45 | M1 | Why naive agents break + FSM fix | `m1_baseline/` |
| 0:45–1:30 | M2 | MCP with GitHub | `m2_mcp/github_demo_client.py` |
| 1:30–2:05 | M2 | Custom MCP servers (break at 1:30) | `m2_mcp/pricing_server.py` |
| 2:05–2:50 | M3 | Pure LangGraph multi-agent flow + full simple run | `m3_langgraph_multiagents/`, `m3_langgraph_multiagents/main_langgraph_multiagent.py` |
| 2:50–3:50 | M4 | True A2A protocol demos (ADK backing) | `m4_adk_multiagents/a2a_protocol_seller_server.py`, `m4_adk_multiagents/a2a_protocol_buyer_client_demo.py` |
| 3:50–4:00 | Wrap | Exercises + Q&A | `m1_baseline/exercises/`, `m2_mcp/exercises/`, `m3_langgraph_multiagents/exercises/`, `m4_adk_multiagents/exercises/` |

---

## Running the MCP Servers Manually

### Inspect Available Tools

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def inspect_server(script: str):
    params = StdioServerParameters(command="python", args=[script])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools = await session.list_tools()
            for t in tools.tools:
                print(f"  • {t.name}: {t.description[:60]}")

asyncio.run(inspect_server("m2_mcp/pricing_server.py"))
asyncio.run(inspect_server("m2_mcp/inventory_server.py"))
```

### SSE Mode (Multiple Clients)

```bash
# Terminal 1 — start servers
python m2_mcp/pricing_server.py --sse --port 8001
python m2_mcp/inventory_server.py --sse --port 8002

# Terminal 2 — connect to SSE server
python -c "
import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession
async def test():
    async with sse_client('http://localhost:8001/sse') as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            result = await s.call_tool('get_market_price', {'address': '742 Evergreen Terrace, Austin, TX 78701'})
            print(result.content[0].text[:200])
asyncio.run(test())
"
```

---

## Customization Guide

### Change the Property

Edit these values in `buyer_simple.py`, `seller_simple.py`, `buyer_adk.py`, `seller_adk.py`:

```python
PROPERTY_ADDRESS = "1234 Oak Street, Dallas, TX 75201"
LISTING_PRICE = 520_000
BUYER_BUDGET = 495_000
MINIMUM_PRICE = 475_000
```

Add the property to `m2_mcp/pricing_server.py`'s `PROPERTY_DATABASE`.

### Add a New MCP Tool

In `m2_mcp/pricing_server.py`:

```python
@mcp.tool()
def get_neighborhood_score(zip_code: str) -> dict:
    """Get neighborhood safety and amenity score."""
    return {
        "zip_code": zip_code,
        "safety_score": 8.2,
        "walkability": 7.5,
        "school_rating": 8.0,
    }
```

### Change Negotiation Strategy

In `m3_langgraph_multiagents/buyer_simple.py`, modify `BUYER_SYSTEM_PROMPT`:

```python
# Change from "start 12% below asking" to "start 8% below"
# Or add: "Always ask for seller to cover closing costs"
```

### Add a Mediator Agent

Start from `m3_langgraph_multiagents/langgraph_flow.py` and add a mediator node plus conditional routing between buyer and seller.

---

## Key Files Reference

| File | Key Class/Function | What It Does |
|---|---|---|
| `negotiation_types.py` | `create_offer`, `create_counter_offer`, `create_acceptance` | Module 3 typed negotiation message builders |
| `buyer_simple.py` | `BuyerAgent` | GPT-4o buyer with MCP tool calls |
| `seller_simple.py` | `SellerAgent` | GPT-4o seller with dual MCP servers |
| `pricing_server.py` | `get_market_price`, `calculate_discount` | MCP pricing tools |
| `inventory_server.py` | `get_inventory_level`, `get_minimum_acceptable_price` | MCP inventory tools |
| `langgraph_flow.py` | `create_negotiation_graph`, `run_negotiation` | LangGraph workflow |
| `buyer_adk.py` | `BuyerAgentADK` | ADK buyer with MCPToolset |
| `seller_adk.py` | `SellerAgentADK` | ADK seller with dual MCPToolsets |
| `a2a_protocol_http_orchestrator.py` | `ADKOrchestrationState`, round loop | HTTP A2A orchestration + ADK session state |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'mcp'`**
```bash
pip install mcp
```

**`AuthenticationError` from OpenAI**
```bash
export OPENAI_API_KEY=sk-your-actual-key
```

**`AuthenticationError` / provider auth failure in ADK runs**
```bash
export OPENAI_API_KEY=sk-your-actual-key
```

**`FileNotFoundError` running MCP servers**
```bash
# Run from the real-estate-negotiation-simulator/ directory
cd real-estate-negotiation-simulator
python m3_langgraph_multiagents/main_langgraph_multiagent.py  # Not: python real-estate-negotiation-simulator/m3_langgraph_multiagents/main_langgraph_multiagent.py
```

**GitHub MCP demo fails with `command not found: npx`**
```bash
# Install Node.js from: https://nodejs.org
node --version && npx --version
```

**PowerShell `UnauthorizedAccess` error activating venv**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\.venv\Scripts\Activate.ps1
```

**Unicode / encoding errors on Windows (`UnicodeEncodeError`, garbled output)**
```powershell
# Set UTF-8 mode before running any script
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
python m3_langgraph_multiagents/main_langgraph_multiagent.py
```
Or add `PYTHONUTF8=1` to your `.env` file to make it permanent.

---

*Built for the AI Agent Systems Workshop — teaching MCP, A2A, LangGraph, and Google ADK through a real estate negotiation simulator.*
