# Real Estate Negotiation Workshop
## Learn MCP · A2A · LangGraph · Google ADK

A **4-hour hands-on workshop** teaching modern AI agent frameworks through a concrete, runnable project: an autonomous real estate negotiation between a Buyer Agent and a Seller Agent.

---

## What You'll Learn

| Concept | What It Is | How We Use It |
|---|---|---|
| **MCP** | Standard protocol for agents to access external tools | Agents query pricing/inventory servers via MCP |
| **A2A** | Agent-to-Agent communication patterns | Buyer and seller exchange structured negotiation messages |
| **LangGraph** | Stateful multi-agent workflow orchestration | Manages the 5-round negotiation loop |
| **Google ADK** | Production-grade agent framework | Alternative implementation using Gemini |

---

## The Scenario

**Property**: 742 Evergreen Terrace, Austin, TX 78701
*(4 BR / 3 BA / 2,400 sqft / Single Family / Built 2005)*

| Party | Goal | Starting Position | Walk-Away |
|---|---|---|---|
| **Buyer Agent** (GPT-4o / Gemini) | Buy at lowest price | Offer $425,000 | Over $460,000 |
| **Seller Agent** (GPT-4o / Gemini) | Sell at highest price | Counter $477,000 | Below $445,000 |

The negotiation runs for a maximum of **5 rounds**. Agents use real market data (via MCP) to justify every offer.

---

## Project Structure

Folders are numbered in teaching order. Each module introduces one new concept.

```
negotiation_workshop/
│
├── m1_baseline/                       # MODULE 1 — Start here. Watch it break.
│   ├── naive_negotiation.py           # Intentionally broken (10 failure modes)
│   └── state_machine.py               # FSM that fixes termination (Layer 7)
│
├── m2_mcp/                            # MODULE 2 — External data via MCP
│   ├── github_demo_client.py          # Connect to GitHub's real MCP server
│   ├── pricing_server.py              # Custom MCP: market pricing tools
│   └── inventory_server.py            # Custom MCP: inventory + seller constraints
│
├── m3_agents/                         # MODULE 3 — A2A messaging + LangGraph
│   ├── a2a_simple.py                  # A2A message schema + message bus
│   ├── buyer_simple.py                # Buyer agent (OpenAI GPT-4o)
│   ├── seller_simple.py               # Seller agent (OpenAI GPT-4o)
│   └── langgraph_flow.py              # LangGraph negotiation workflow
│
├── m4_adk/                            # MODULE 4 — Google ADK + Gemini
│   ├── messaging_adk.py               # ADK response parsing + session tracking
│   ├── buyer_adk.py                   # Buyer agent (Gemini 2.0 Flash via ADK)
│   └── seller_adk.py                  # Seller agent (Gemini 2.0 Flash via ADK)
│
├── tests/                             # Test suite (no API keys needed)
│   ├── test_fsm.py                    # FSM termination guarantee tests
│   └── test_a2a.py                    # A2A schema + state machine tests
│
├── notes/                             # Reference documentation
│   ├── 01_agents_fundamentals.md
│   ├── 02_mcp_deep_dive.md
│   ├── 03_a2a_protocols.md
│   ├── 04_langgraph_explained.md
│   └── 05_google_adk_overview.md
│
├── exercises/
│   ├── exercises.md                   # 10 exercises (conceptual + coding)
│   └── solutions.md                   # Complete solutions with code
│
├── main_simple.py                     # Entry point — Module 3 (OpenAI + LangGraph)
├── main_adk.py                        # Entry point — Module 4 (Gemini + ADK)
├── INSTRUCTOR_GUIDE.md                # 4-hour workshop script for instructors
├── .env.example                       # Copy to .env and add your API keys
└── requirements.txt
```

---

## Quick Start

### 1. Prerequisites

```bash
# Python 3.10+
python --version  # should be 3.10+

# Node.js 18+ (for GitHub MCP demo only)
node --version    # should be 18+
```

### 2. Create and Activate a Virtual Environment

```bash
cd negotiation_workshop

# Create the virtual environment
python -m venv .venv

# Activate — macOS / Linux
source .venv/bin/activate

# Activate — Windows (Command Prompt)
.venv\Scripts\activate.bat

# Activate — Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Confirm the venv is active (should show the .venv path)
which python        # macOS/Linux
where python        # Windows
```

> **Tip**: Your prompt will change to show `(.venv)` when the environment is active.
> To deactivate at any time, run `deactivate`.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set API Keys

Copy the template and fill in your keys:
```bash
cp .env.example .env
# Edit .env with your keys, then:
source .env
```

**Or export directly:**
```bash
export OPENAI_API_KEY=sk-...       # Module 3 (simple version)
export GOOGLE_API_KEY=AIza...      # Module 4 (ADK version, FREE)
export GITHUB_TOKEN=ghp_...        # Module 2 GitHub demo (optional)
```

### 5. Run the Tests (no API keys needed)

```bash
pytest tests/ -v
```

All tests verify pure logic (FSM termination guarantee, A2A schema validation)
with no LLM calls. A clean test run confirms your setup is correct.

### 6. Run the Workshop Modules in Order

```bash
# MODULE 1: Watch the naive version fail (no API keys)
python m1_baseline/naive_negotiation.py   # 10 failure modes
python m1_baseline/state_machine.py       # FSM termination guarantee

# MODULE 2: MCP protocol
python m2_mcp/github_demo_client.py       # GitHub MCP demo (needs GITHUB_TOKEN)
python m2_mcp/pricing_server.py           # Run MCP server standalone (stdio)
python m2_mcp/pricing_server.py --sse --port 8001  # SSE transport mode

# MODULE 3: Full simple version (needs OPENAI_API_KEY)
python main_simple.py

# MODULE 4: ADK version (needs GOOGLE_API_KEY, free)
python main_adk.py
```

---

## Architecture Deep Dive

### Simple Version Flow

```
python main_simple.py
    │
    └── m3_agents/langgraph_flow.py
          │
          ├── LangGraph Graph: START → init → [buyer ↔ seller] → END
          │
          ├── buyer_node (async)
          │     ├── BuyerAgent.make_initial_offer()
          │     │     ├── MCP call → m2_mcp/pricing_server.py → get_market_price()
          │     │     ├── MCP call → m2_mcp/pricing_server.py → calculate_discount()
          │     │     └── OpenAI GPT-4o → decide offer price
          │     └── Returns A2AMessage (OFFER) → stored in LangGraph state
          │
          └── seller_node (async)
                ├── SellerAgent.respond_to_offer()
                │     ├── MCP call → m2_mcp/pricing_server.py → get_market_price()
                │     ├── MCP call → m2_mcp/inventory_server.py → get_inventory_level()
                │     ├── MCP call → m2_mcp/inventory_server.py → get_minimum_acceptable_price()
                │     └── OpenAI GPT-4o → decide counter-offer
                └── Returns A2AMessage (COUNTER_OFFER) → stored in LangGraph state
```

### ADK Version Flow

```
python main_adk.py
    │
    └── run_adk_negotiation() [manual orchestrator loop]
          │
          ├── BuyerAgentADK (async context manager)
          │     ├── MCPToolset → m2_mcp/pricing_server.py (discovers tools)
          │     ├── LlmAgent(model="gemini-2.0-flash", tools=[...])
          │     └── Runner → executes agent turns
          │           Agent autonomously calls MCP tools → Gemini decides
          │
          └── SellerAgentADK (async context manager)
                ├── MCPToolset → m2_mcp/pricing_server.py
                ├── MCPToolset → m2_mcp/inventory_server.py (seller ONLY)
                ├── LlmAgent(model="gemini-2.0-flash", tools=[...merged...])
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
| 0:15–1:05 | M1 | Why naive agents break + FSM fix | `m1_baseline/` |
| 1:05–1:30 | M2 | MCP with GitHub | `m2_mcp/github_demo_client.py` |
| 1:30–2:15 | M2 | Custom MCP servers | `m2_mcp/pricing_server.py` |
| 2:15–3:15 | M3 | A2A + LangGraph + full simple run | `m3_agents/`, `main_simple.py` |
| 3:15–3:40 | M4 | Google ADK + Gemini | `m4_adk/`, `main_adk.py` |
| 3:40–4:00 | Wrap | Exercises + Q&A | `exercises/exercises.md` |

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

In `m3_agents/buyer_simple.py`, modify `BUYER_SYSTEM_PROMPT`:

```python
# Change from "start 12% below asking" to "start 8% below"
# Or add: "Always ask for seller to cover closing costs"
```

### Add a Mediator Agent

See `exercises/solutions.md` for the complete mediator implementation.

---

## Key Files Reference

| File | Key Class/Function | What It Does |
|---|---|---|
| `a2a_simple.py` | `A2AMessage`, `A2AMessageBus` | A2A message schema and routing |
| `buyer_simple.py` | `BuyerAgent` | GPT-4o buyer with MCP tool calls |
| `seller_simple.py` | `SellerAgent` | GPT-4o seller with dual MCP servers |
| `pricing_server.py` | `get_market_price`, `calculate_discount` | MCP pricing tools |
| `inventory_server.py` | `get_inventory_level`, `get_minimum_acceptable_price` | MCP inventory tools |
| `langgraph_flow.py` | `create_negotiation_graph`, `run_negotiation` | LangGraph workflow |
| `buyer_adk.py` | `BuyerAgentADK` | ADK buyer with MCPToolset |
| `seller_adk.py` | `SellerAgentADK` | ADK seller with dual MCPToolsets |
| `messaging_adk.py` | `NegotiationSession`, `parse_*` | ADK A2A utilities |

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

**`google.api_core.exceptions.PermissionDenied` from Gemini**
```bash
export GOOGLE_API_KEY=AIza-your-actual-key
# Get free key at: https://aistudio.google.com
```

**`FileNotFoundError` running MCP servers**
```bash
# Run from the negotiation_workshop/ directory
cd negotiation_workshop
python main_simple.py  # Not: python negotiation_workshop/main_simple.py
```

**GitHub MCP demo fails with `command not found: npx`**
```bash
# Install Node.js from: https://nodejs.org
node --version && npx --version
```

---

*Built for the AI Agent Systems Workshop — teaching MCP, A2A, LangGraph, and Google ADK through a real estate negotiation simulator.*
