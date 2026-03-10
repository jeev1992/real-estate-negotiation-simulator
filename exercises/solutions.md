# Solutions
## Real Estate Negotiation Workshop

Complete answers and code for all exercises.

---

## Exercise 1: MCP vs A2A vs Direct API

### Answers

**a) Which integrations use MCP?**
- **Yahoo Finance stock prices** → MCP
  - External data source → perfect MCP use case
  - Multiple agents might need price data
  - Would create a `stock-pricing` MCP server with tools like `get_current_price(ticker)`, `get_historical_prices(ticker, days)`

- **Internal portfolio database** → MCP or Direct API
  - If only one agent uses it → direct function call
  - If multiple agents need portfolio data → MCP server with `get_holdings()`, `update_position()`, `get_performance()` tools

**b) Which use A2A?**
- **Risk assessment agent** → A2A
  - Another autonomous agent with its own goals/logic
  - Needs to reason about the trade and respond with approval/rejection/conditions
  - Uses structured messages: `TradeProposal`, `RiskAssessment`, `Approval`

- **News analysis agent** → A2A
  - Another agent that autonomously processes news and forms sentiment opinions
  - Returns `SentimentReport` via A2A message

**c) Direct function call?**
- Simple utility functions with no AI reasoning (e.g., `calculate_tax()`, `format_currency()`)

**d) Architecture diagram**:
```
Trading Agent
    │
    ├── MCP → Yahoo Finance MCP Server → get_stock_price("AAPL")
    │
    ├── MCP → Portfolio DB MCP Server → get_holdings(), update_position()
    │
    ├── A2A → Risk Assessment Agent → TradeProposal → RiskReport
    │                (another LLM agent)
    │
    └── A2A → News Analysis Agent → SentimentRequest → SentimentReport
                  (another LLM agent)
```

---

## Exercise 2: LangGraph State Design

### Answers

**a) Why `Annotated[list, operator.add]`?**
```python
# Without Annotated (WRONG for accumulation):
class State(TypedDict):
    history: list[dict]

# If buyer_node returns: {"history": [{"round": 1, "offer": 425000}]}
# And seller_node returns: {"history": [{"round": 1, "counter": 477000}]}
# LangGraph applies updates sequentially: history = [{"round": 1, "counter": 477000}]
# ← buyer's entry is LOST! Last writer wins.

# With Annotated (CORRECT):
class State(TypedDict):
    history: Annotated[list[dict], operator.add]

# buyer_node returns: {"history": [{"round": 1, "offer": 425000}]}
# seller_node returns: {"history": [{"round": 1, "counter": 477000}]}
# LangGraph CONCATENATES: history = [
#     {"round": 1, "offer": 425000},    ← kept
#     {"round": 1, "counter": 477000}   ← appended
# ]
```

**b) Why separate price fields instead of just the last A2A message?**
- Direct field access is faster (no parsing required)
- Router functions need quick access: `state["buyer_current_offer"]` vs parsing JSON
- State should be normalized: prices are fundamentally floats, not embedded in message dicts
- The A2A message is stored too (in `last_buyer_message`) for full context when needed

**c) Advantages of `Literal` type for status:**
```python
# String (what we use for simplicity):
status: str  # Could accidentally be "AGREED" or "agreeed" (typo)

# Literal (better for production):
from typing import Literal
NegotiationStatus = Literal["negotiating", "agreed", "deadlocked", "buyer_walked", "seller_rejected", "error"]
status: NegotiationStatus

# Benefits:
# 1. Type checker catches invalid values at write time
# 2. IDE autocomplete shows valid values
# 3. Explicit enumeration of all possible states
# 4. Router functions can be exhaustively checked
```

**d) New fields for mediator agent:**
```python
class NegotiationState(TypedDict):
    # ... existing fields ...

    # Mediator tracking
    mediator_active: bool           # Is mediator currently intervening?
    mediator_proposal: Optional[float]  # Mediator's proposed price
    buyer_mediator_vote: Optional[str]  # "accept" | "reject" | None
    seller_mediator_vote: Optional[str] # "accept" | "reject" | None
    mediator_reasoning: Optional[str]   # Why mediator proposed this price
```

---

## Exercise 3: Information Asymmetry

### Answers

**a) Two technical approaches for access control:**

**Approach 1: API Key per Agent**
```python
# inventory_server.py
import os

SELLER_API_KEY = os.environ.get("SELLER_MCP_KEY", "secret-seller-key")

@mcp.tool()
def get_minimum_acceptable_price(property_id: str) -> dict:
    """Get seller's floor price. REQUIRES seller API key."""
    # In FastMCP, you'd check request headers or initialize params
    # This is a simplified illustration
    if not _check_caller_is_seller():
        raise McpError(ErrorCode.Unauthorized, "This tool requires seller credentials")
    ...

# Buyer connects without seller key → tool raises Unauthorized
# Seller connects with seller key → tool works
```

**Approach 2: Separate MCP Servers**
```python
# Public server (both agents)
# inventory_server_public.py — only exposes get_inventory_level()

# Private server (seller only)
# inventory_server_seller.py — exposes get_minimum_acceptable_price()
#                              only runs for seller agent

# Buyer agent connects to:
#   pricing_server.py + inventory_server_public.py

# Seller agent connects to:
#   pricing_server.py + inventory_server_seller.py (private)
```

**b) Effect if buyer could access floor price:**
- Negotiation would be very short: buyer would offer $445,001 immediately
- No longer realistic (real buyers don't know seller's bottom line)
- Not ethical in actual real estate (information fiduciary duty)
- However, it COULD model insider trading or collusion scenarios

**c) Modeling information advantages:**
```python
# Add a "motivation_signal" to inventory server that's partially accurate
@mcp.tool()
def get_seller_urgency_signal(property_id: str) -> dict:
    """
    Returns indirect signals about seller motivation.
    (Public information — what a buyer's agent could discover through research)

    NOT the actual floor price, but observable signals:
    - How many times has price been reduced?
    - How many days on market vs. neighborhood average?
    - Is property vacant? (suggests urgency)
    - Public records: seller bought new home? (suggests urgency)
    """
    return {
        "price_reductions": 0,
        "days_on_market_vs_avg": "+3 days",  # slightly above average
        "property_vacant": False,
        "seller_purchased_new_home": True,   # public record — suggests urgency!
        "signal_strength": "moderate",
        "interpretation": "Seller may be moderately motivated due to having purchased new home"
    }
```

---

## Exercise 4: New MCP Tool — Solution

### `m2_mcp/pricing_server.py` addition:

```python
@mcp.tool()
def get_property_inspection_report(
    property_id: str,
    inspection_type: str = "standard"
) -> dict:
    """
    Get a simulated property inspection report.

    In production: would call a home inspection API or database.
    MCP abstracts this — agents don't know the data source.

    Args:
        property_id: Property identifier (e.g., "742-evergreen-austin-78701")
        inspection_type: "standard", "full", or "structural"

    Returns:
        Inspection report with condition ratings and repair estimates.
    """
    # Known property report
    if property_id == "742-evergreen-austin-78701":
        return {
            "property_id": property_id,
            "inspection_type": inspection_type,
            "inspection_date": "2025-01-10",
            "inspector": "Austin Home Inspections LLC",
            "foundation_rating": "excellent",
            "roof_condition": {
                "rating": "excellent",
                "age_years": 3,     # New roof 2022
                "remaining_life_years": 27,
                "notes": "Architectural shingles replaced 2022. Excellent condition."
            },
            "hvac_condition": {
                "rating": "excellent",
                "age_years": 4,     # Replaced 2021
                "remaining_life_years": 11,
                "notes": "Carrier 16 SEER. All filters clean. Serviced 2024."
            },
            "plumbing": "good",
            "electrical": "good",
            "kitchen": {
                "rating": "excellent",
                "notes": "Fully renovated 2023. All new appliances."
            },
            "estimated_repair_costs": {
                "immediate": 0,         # No urgent repairs
                "within_1_year": 500,   # Minor: caulk bathroom
                "within_5_years": 2000, # Paint exterior
                "total_estimated": 2500
            },
            "overall_recommendation": "proceed",
            "summary": (
                "Property is in excellent condition. Recent major renovations "
                "(kitchen, roof, HVAC) reduce near-term repair risk significantly. "
                "Recommended to proceed with purchase."
            ),
            "data_source": "MCP Pricing Server (simulated inspection data)"
        }

    # Default for unknown properties
    import random
    ratings = ["excellent", "good", "fair", "poor"]
    roof_age = random.randint(2, 25)
    hvac_age = random.randint(1, 20)
    repair_cost = max(0, (roof_age - 10) * 500 + (hvac_age - 10) * 300)

    recommendation = "proceed" if repair_cost < 5000 else (
        "negotiate_repairs" if repair_cost < 20000 else "walk_away"
    )

    return {
        "property_id": property_id,
        "inspection_type": inspection_type,
        "foundation_rating": random.choice(ratings[:2]),
        "roof_condition": {"rating": ratings[min(roof_age // 8, 3)], "age_years": roof_age},
        "hvac_condition": {"rating": ratings[min(hvac_age // 7, 3)], "age_years": hvac_age},
        "estimated_repair_costs": {"total_estimated": repair_cost},
        "overall_recommendation": recommendation,
        "data_source": "MCP Pricing Server (simulated)"
    }
```

### Update to `buyer_simple.py` to call this tool:

```python
async def _get_inspection_report(self) -> dict:
    """Get inspection report — new tool added in Exercise 4."""
    if not hasattr(self, '_inspection_data') or self._inspection_data is None:
        print("   [Buyer] Calling MCP: get_property_inspection_report...")
        self._inspection_data = await call_pricing_mcp(
            "get_property_inspection_report",
            {
                "property_id": "742-evergreen-austin-78701",
                "inspection_type": "standard"
            }
        )
    return self._inspection_data

# Then in make_initial_offer(), add:
inspection = await self._get_inspection_report()
# Add to user_message:
f"""
INSPECTION REPORT:
  Overall recommendation: {inspection.get('overall_recommendation')}
  Estimated repairs: ${inspection.get('estimated_repair_costs', {}).get('total_estimated', 0):,}
  Notes: {inspection.get('summary', '')}
"""
```

---

## Exercise 5: Anchoring Strategy — Solution

### Modified `SELLER_SYSTEM_PROMPT` in `seller_simple.py`:

```python
SELLER_SYSTEM_PROMPT = f"""You are an expert real estate listing agent with deep knowledge
of negotiation psychology, specifically the ANCHORING technique.

Property: {PROPERTY_ADDRESS}
Listed at: ${LISTING_PRICE:,}

ANCHORING STRATEGY:
The anchoring effect in negotiation: by starting with a very high number,
you make subsequent concessions feel more generous, and you shift the
buyer's reference point upward.

YOUR ANCHORING APPROACH:
  Round 1: Counter at $495,000 (ABOVE listing — justified by $75K in upgrades)
           Frame this confidently: "The improvements alone add $75K in value"
  Round 2: "Come down" to $482,000 — looks like big concession from $495K
  Round 3: $470,000 — still looks reasonable from the $495K anchor
  Round 4: $458,000 — now buyer feels they've negotiated hard
  Round 5 (if needed): $449,000 — your "absolute final"

PSYCHOLOGICAL JUSTIFICATION FOR OPENING AT $495K:
  • Kitchen renovation (2023): $45,000 — comparable homes without this sell for less
  • New roof (2022): $18,000 — buyers save on this for 25+ years
  • HVAC (2021): $12,000
  • Total upgrades: $75,000+
  • Market momentum: Austin market appreciating 4% annually
  Therefore: $485,000 list + $10,000 premium for quality = $495,000

ABSOLUTE FLOOR: ${MINIMUM_PRICE:,} (mortgage payoff — cannot go lower)
...
"""
```

**Expected outcome analysis:**
- Anchoring at $495K typically shifts the midpoint upward by $3-7K
- If buyer was going to settle at $449K without anchoring → may settle at $452-456K with anchoring
- Depends heavily on buyer agent's LLM and how strongly it "holds" to market data as counter-anchor

---

## Exercise 6: Deadlock Detection Tool — Solution

```python
@mcp.tool()
def check_negotiation_deadlock(
    buyer_offer: float,
    seller_counter: float,
    rounds_elapsed: int,
    max_rounds: int,
    buyer_budget: float
) -> dict:
    """
    Analyze negotiation trajectory and detect deadlock risk.

    Uses gap analysis and round consumption rate to predict outcomes.

    Args:
        buyer_offer: Current buyer offer in dollars
        seller_counter: Current seller counter in dollars
        rounds_elapsed: How many rounds have occurred
        max_rounds: Maximum allowed rounds
        buyer_budget: Buyer's ceiling price

    Returns:
        Deadlock risk assessment with recommended action.
    """
    gap = seller_counter - buyer_offer
    rounds_remaining = max_rounds - rounds_elapsed
    gap_percent = gap / seller_counter * 100

    # Calculate convergence rate from history context
    # If we had history, we'd compute actual rate
    # Here we estimate from gap and rounds
    if rounds_elapsed == 0:
        convergence_needed_per_round = gap  # full gap in 0 rounds — bad
    else:
        # Rough estimate: assume linear convergence
        convergence_needed_per_round = gap / max(rounds_remaining, 1)

    # Risk assessment
    if gap <= 0:
        risk = "none"
        recommendation = "Agreement zone reached — consider accepting"
        action = "accept"
    elif seller_counter > buyer_budget:
        # Seller hasn't come into buyer's range yet
        gap_to_budget = seller_counter - buyer_budget
        if gap_to_budget > 20_000 and rounds_remaining <= 1:
            risk = "certain"
            recommendation = "Seller is unlikely to reach your budget in remaining rounds"
            action = "walk_away"
        elif gap_to_budget > 10_000:
            risk = "high"
            recommendation = f"Need ${gap_to_budget:,.0f} more movement in {rounds_remaining} rounds"
            action = "make_concession" if rounds_remaining > 1 else "walk_away"
        else:
            risk = "medium"
            recommendation = "Close to budget range — one more round may resolve this"
            action = "continue"
    elif rounds_remaining <= 0:
        risk = "certain"
        recommendation = "No rounds remaining"
        action = "walk_away" if gap > 5000 else "accept"
    elif gap < 5_000:
        risk = "low"
        recommendation = "Gap is small — consider splitting the difference"
        action = "make_concession"
    elif gap < 15_000 and rounds_remaining >= 2:
        risk = "low"
        recommendation = "Normal negotiation gap — continue"
        action = "continue"
    else:
        risk = "medium"
        recommendation = f"${gap:,.0f} gap with {rounds_remaining} rounds left"
        action = "continue" if rounds_remaining > 1 else "make_concession"

    return {
        "analysis": {
            "current_gap": gap,
            "gap_percent": round(gap_percent, 1),
            "rounds_elapsed": rounds_elapsed,
            "rounds_remaining": rounds_remaining,
            "seller_above_budget_by": max(0, seller_counter - buyer_budget),
        },
        "deadlock_risk": risk,
        "recommendation": recommendation,
        "suggested_action": action,
        "if_splitting_difference": (buyer_offer + seller_counter) / 2,
        "data_source": "MCP Pricing Server (negotiation analytics)"
    }
```

**Usage in `buyer_simple.py`**:
```python
# In respond_to_counter(), call deadlock check:
deadlock_analysis = await call_pricing_mcp(
    "check_negotiation_deadlock",
    {
        "buyer_offer": state["buyer_current_offer"],
        "seller_counter": seller_price,
        "rounds_elapsed": self.round,
        "max_rounds": 5,
        "buyer_budget": float(BUYER_BUDGET)
    }
)

# Add to LLM context:
f"""
DEADLOCK ANALYSIS (from MCP):
  Risk: {deadlock_analysis.get('deadlock_risk')}
  Recommendation: {deadlock_analysis.get('recommendation')}
  Suggested action: {deadlock_analysis.get('suggested_action')}
  Split-the-difference price: ${deadlock_analysis.get('if_splitting_difference', 0):,.0f}
"""
```

---

## Exercise 7: SSE Client — Solution

```python
# In buyer_simple.py — SSE transport option

import os
from mcp.client.sse import sse_client  # SSE client

MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")
MCP_SSE_URL = os.environ.get("MCP_SSE_URL", "http://localhost:8001/sse")

async def call_pricing_mcp(tool_name: str, arguments: dict) -> dict:
    """
    Call pricing MCP server — supports both stdio and SSE transport.

    Set MCP_TRANSPORT=sse to use SSE mode.
    Start SSE server first: python m2_mcp/pricing_server.py --sse --port 8001
    """
    if MCP_TRANSPORT == "sse":
        return await _call_pricing_mcp_sse(tool_name, arguments)
    else:
        return await _call_pricing_mcp_stdio(tool_name, arguments)


async def _call_pricing_mcp_sse(tool_name: str, arguments: dict) -> dict:
    """SSE transport — connect to HTTP server."""
    async with sse_client(MCP_SSE_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if result.content:
                return json.loads(result.content[0].text)
    return {}


async def _call_pricing_mcp_stdio(tool_name: str, arguments: dict) -> dict:
    """stdio transport — spawn server as subprocess."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[PRICING_SERVER_PATH],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if result.content:
                return json.loads(result.content[0].text)
    return {}
```

**Key differences between stdio and SSE:**

| | stdio | SSE |
|---|---|---|
| Server lifetime | Lives for duration of client connection | Runs independently |
| Multiple clients | One server per client | Many clients, one server |
| Startup time | Spawns new process each connection | Server already running |
| Network | Local only (subprocess pipes) | Can be remote |
| Best for | Development, local tools | Production, shared tools |

---

## Exercise 8: Mediator Agent — Solution

### `m3_langgraph_multiagents/mediator_simple.py`:

```python
"""Mediator Agent — intervenes when negotiation stalls."""

import json
import os
from openai import AsyncOpenAI
from m3_langgraph_multiagents.negotiation_types import create_offer

MEDIATOR_SYSTEM_PROMPT = """You are a neutral real estate mediator.
Your job is to find a fair compromise when buyer and seller cannot agree.

You will be given the full negotiation history. Propose a fair settlement price.

Response format (JSON):
{
    "proposed_price": <integer>,
    "reasoning": "<why this is fair to both parties>",
    "message_to_both": "<neutral message explaining the proposal>"
}"""

class MediatorAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    async def propose_settlement(
        self,
        buyer_final_offer: float,
        seller_final_counter: float,
        history: list[dict],
        round_num: int
    ) -> dict:
        """Propose a compromise settlement."""
        midpoint = (buyer_final_offer + seller_final_counter) / 2

        user_message = f"""
Negotiation has stalled. Propose a fair settlement.

Buyer's position: ${buyer_final_offer:,.0f}
Seller's position: ${seller_final_counter:,.0f}
Gap: ${seller_final_counter - buyer_final_offer:,.0f}
Mathematical midpoint: ${midpoint:,.0f}

Full history:
{json.dumps(history, indent=2)}

Propose the fairest settlement price. Consider both parties' concession patterns.
"""
        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": MEDIATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"}
        )
        decision = json.loads(response.choices[0].message.content)
        proposed = float(decision.get("proposed_price", midpoint))

        return create_offer(
            session_id=self.session_id,
            round_num=round_num,
            price=proposed,
            message=f"[MEDIATOR PROPOSAL] {decision.get('message_to_both', '')}",
        )
```

### LangGraph changes in `m3_langgraph_multiagents/langgraph_flow.py`:

```python
# Add mediator node
async def mediator_node(state: dict) -> dict:
    """Mediator intervenes when round 4 hasn't produced agreement."""
    from m3_langgraph_multiagents.mediator_simple import MediatorAgent

    mediator = MediatorAgent(session_id=state["session_id"])
    proposal = await mediator.propose_settlement(
        buyer_final_offer=state["buyer_current_offer"],
        seller_final_counter=state["seller_current_counter"],
        history=state.get("history", []),
        round_num=state["round_number"] + 1
    )

    return {
        "last_buyer_message": proposal.dict(),
        "history": [{"round": proposal.round, "agent": "mediator",
                     "message_type": "MEDIATION", "price": proposal.payload.price}],
    }

# Add to graph
workflow.add_node("mediator", mediator_node)

# New routing in route_after_seller:
def route_after_seller(state: dict) -> str:
    if state.get("status") != "negotiating":
        return "end"
    if state.get("round_number") == 4:  # Intervene before final round
        return "mediator"
    if state.get("round_number") >= state.get("max_rounds", 5):
        return "end"
    return "continue"

# Updated edges
workflow.add_conditional_edges("seller", route_after_seller, {
    "continue": "buyer",
    "mediator": "mediator",
    "end": END,
})
workflow.add_edge("mediator", "seller")  # Seller evaluates mediator's proposal
```

---

## Exercise 9: Negotiation Memory — Solution

```python
# negotiation_memory.py
import json
import os
from datetime import datetime
from pathlib import Path

MEMORY_FILE = "negotiation_memory.json"

def save_session(session_id: str, outcome: str, buyer_final: float,
                 seller_final: float, agreed_price: float | None, rounds: int) -> None:
    """Save a completed negotiation session to memory."""
    memory = load_all_sessions()

    memory["sessions"].append({
        "session_id": session_id,
        "date": datetime.now().isoformat(),
        "property": "742 Evergreen Terrace, Austin, TX 78701",
        "outcome": outcome,
        "buyer_final_offer": buyer_final,
        "seller_final_counter": seller_final,
        "agreed_price": agreed_price,
        "rounds": rounds
    })

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def load_all_sessions() -> dict:
    """Load all past sessions."""
    if not Path(MEMORY_FILE).exists():
        return {"sessions": []}
    with open(MEMORY_FILE) as f:
        return json.load(f)

def get_buyer_memory_context() -> str:
    """Format past sessions as context for the buyer agent."""
    memory = load_all_sessions()
    sessions = memory.get("sessions", [])

    if not sessions:
        return "No previous negotiation history for this property."

    lines = ["NEGOTIATION HISTORY FOR THIS PROPERTY:"]
    for s in sessions[-3:]:  # Last 3 sessions
        lines.append(
            f"  {s['date'][:10]}: {s['outcome']} | "
            f"Buyer offered ${s['buyer_final_offer']:,.0f} | "
            f"Seller's final was ${s['seller_final_counter']:,.0f}"
        )

    if any(s["outcome"] == "deadlocked" for s in sessions):
        last_deadlock = next(s for s in reversed(sessions) if s["outcome"] == "deadlocked")
        lines.append(
            f"\n⚠️  In last deadlock, seller wouldn't go below "
            f"${last_deadlock['seller_final_counter']:,.0f}"
        )

    return "\n".join(lines)

def get_seller_memory_context() -> str:
    """Format past sessions as context for the seller agent."""
    memory = load_all_sessions()
    sessions = memory.get("sessions", [])

    if not sessions:
        return "No previous negotiation history."

    lines = ["PREVIOUS BUYER INTERACTIONS:"]
    for s in sessions[-3:]:
        lines.append(
            f"  {s['date'][:10]}: Buyer's highest offer was ${s['buyer_final_offer']:,.0f}"
        )

    return "\n".join(lines)
```

---

## Exercise 10: Analytics Dashboard — Solution

```python
# negotiation_analytics.py
def generate_analytics_report(history: list[dict], listing_price: float) -> None:
    """Generate ASCII analytics report."""
    buyer_offers = [(e["round"], e["price"]) for e in history if e["agent"] == "buyer" and e.get("price")]
    seller_counters = [(e["round"], e["price"]) for e in history if e["agent"] == "seller" and e.get("price")]

    all_prices = [p for _, p in buyer_offers + seller_counters]
    min_price = min(all_prices) if all_prices else listing_price * 0.85
    max_price = max(all_prices + [listing_price]) * 1.01

    print("\nCONVERGENCE CHART:")
    print(f"${max_price:,.0f} |{'─' * 45} ← Listing-adjacent")

    # Simple ASCII visualization (10 rows)
    rows = 8
    for row in range(rows):
        price_level = max_price - (row / rows) * (max_price - min_price)
        row_str = f"${price_level:,.0f} |"

        for round_num in range(1, max(h[0] for h in buyer_offers + seller_counters) + 1 if buyer_offers else 2):
            buyer_at_round = next((p for r, p in buyer_offers if r == round_num), None)
            seller_at_round = next((p for r, p in seller_counters if r == round_num), None)

            cell = "    "
            if buyer_at_round and abs(buyer_at_round - price_level) < (max_price - min_price) / rows:
                cell = "  B "
            if seller_at_round and abs(seller_at_round - price_level) < (max_price - min_price) / rows:
                cell = " S  " if cell == "    " else " BS "

            row_str += cell

        print(row_str)

    print(f"${min_price:,.0f} |{'─' * 45}")
    print(f"         Round: " + "".join(f"  {r}  " for r in range(1, len(buyer_offers) + 1)))
    print("  B=Buyer Offer, S=Seller Counter")

    print("\nMCP TOOL USAGE: (log during run for actual counts; counts vary by model decisions)")
    print("  Buyer: get_market_price, calculate_discount")
    print("  Seller: get_market_price, get_inventory_level, get_minimum_acceptable_price")

    print("\nOPTIONAL COMPARISON:")
    print("  Compare this run's MCP selection with Module 4 ADK autonomous tool-calling behavior.")
```

Suggested rubric-aligned answer checklist:

- Include concrete runtime evidence (tool-call logs or counted traces from the same session).
- State the architecture difference precisely:
    - Module 3: LangGraph orchestration + strict LLM-selected MCP execution in Python nodes
    - Module 4: ADK `LlmAgent` + `MCPToolset` autonomous tool loop under ADK runner
- Provide one clear similarity (both can do LLM-driven tool choice) and one clear difference (control surface/explicitness).
- End with a justified judgment on which was easier to reason about for that run.

---

## Research A: MCP Ecosystem Research — Answers

**Notable MCP servers (as of 2025)**:

1. **GitHub** (`@modelcontextprotocol/server-github`)
   - Tools: `search_repositories`, `get_file_contents`, `create_issue`, `list_pull_requests`
   - Use case: Code review agents, DevOps agents, documentation agents

2. **Filesystem** (`@modelcontextprotocol/server-filesystem`)
   - Tools: `read_file`, `write_file`, `list_directory`, `search_files`
   - Use case: Code generation agents, file organization agents

3. **Postgres** (`@modelcontextprotocol/server-postgres`)
   - Tools: `query`, `list_tables`, `describe_table`
   - Use case: Data analysis agents, SQL generation agents

4. **Slack** (`@modelcontextprotocol/server-slack`)
   - Tools: `post_message`, `list_channels`, `get_channel_history`
   - Use case: Customer service agents, notification agents

Full list: https://github.com/modelcontextprotocol/servers

---

## Exercise 11: Customer Support Triage — LangGraph Solution

### Complete implementation: `exercises/code_solutions/ex11_support_triage_langgraph_runner.py`

```python
"""
Customer Support Triage System — LangGraph version.
Run: python exercises/code_solutions/ex11_support_triage_langgraph_runner.py
Requires: OPENAI_API_KEY
"""
import asyncio
import json
import operator
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from openai import AsyncOpenAI

client = AsyncOpenAI()


# ── State Schema ──────────────────────────────────────────────────────────────

class SupportState(TypedDict):
    ticket: str
    classification: str         # "billing" | "technical" | "general"
    urgency: str                # "low" | "medium" | "high"
    assigned_to: str
    specialist_response: str
    final_response: str
    history: Annotated[list[dict], operator.add]


# ── Nodes ─────────────────────────────────────────────────────────────────────

async def triage_node(state: SupportState) -> dict:
    """Classify the ticket and assess urgency."""
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a customer support triage agent. "
                    "Classify the ticket and return JSON with keys: "
                    "classification, urgency, reasoning.\n\n"
                    "classification: billing | technical | general\n"
                    "urgency: low | medium | high\n\n"
                    "Billing: charges, refunds, invoices, subscriptions, payments\n"
                    "Technical: bugs, errors, crashes, system issues, features\n"
                    "General: account questions, how-tos, feedback, everything else"
                ),
            },
            {"role": "user", "content": f"Classify this ticket:\n\n{state['ticket']}"},
        ],
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    classification = result.get("classification", "general")
    urgency = result.get("urgency", "low")
    print(f"   [Triage] -> {classification.upper()} (urgency: {urgency})")
    return {
        "classification": classification,
        "urgency": urgency,
        "history": [{"step": "triage", "classification": classification, "urgency": urgency}],
    }


async def billing_node(state: SupportState) -> dict:
    """Billing specialist handles the ticket."""
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a billing support specialist at a SaaS company. "
                    "You handle charges, refunds, invoices, subscriptions, and payment issues. "
                    "Be empathetic, clear, and provide specific action steps. "
                    "Keep your response to 2-3 paragraphs."
                ),
            },
            {"role": "user", "content": f"Customer support ticket:\n\n{state['ticket']}"},
        ],
    )
    text = response.choices[0].message.content
    print(f"   [Billing] -> response drafted ({len(text)} chars)")
    return {
        "assigned_to": "billing",
        "specialist_response": text,
        "history": [{"step": "billing", "chars": len(text)}],
    }


async def technical_node(state: SupportState) -> dict:
    """Technical specialist handles the ticket."""
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a technical support specialist at a SaaS company. "
                    "You handle bugs, errors, crashes, feature questions, and system issues. "
                    "Provide numbered troubleshooting steps when relevant. "
                    "Be precise and actionable."
                ),
            },
            {"role": "user", "content": f"Customer support ticket:\n\n{state['ticket']}"},
        ],
    )
    text = response.choices[0].message.content
    print(f"   [Technical] -> response drafted ({len(text)} chars)")
    return {
        "assigned_to": "technical",
        "specialist_response": text,
        "history": [{"step": "technical", "chars": len(text)}],
    }


async def general_node(state: SupportState) -> dict:
    """General support agent handles the ticket."""
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a friendly customer support agent at a SaaS company. "
                    "You handle account questions, how-to guides, general feedback, "
                    "and anything that doesn't fit billing or technical categories. "
                    "Be warm, helpful, and concise."
                ),
            },
            {"role": "user", "content": f"Customer support ticket:\n\n{state['ticket']}"},
        ],
    )
    text = response.choices[0].message.content
    print(f"   [General] -> response drafted ({len(text)} chars)")
    return {
        "assigned_to": "general",
        "specialist_response": text,
        "history": [{"step": "general", "chars": len(text)}],
    }


async def format_response_node(state: SupportState) -> dict:
    """Format the final response with a metadata header."""
    urgency_tag = {"high": "[!]", "medium": "[~]", "low": "[ ]"}.get(
        state.get("urgency", "low"), "[ ]"
    )
    final = (
        f"SUPPORT TICKET RESPONSE\n"
        f"{'=' * 40}\n"
        f"Classified: {state.get('classification', 'general').upper()}\n"
        f"Urgency:    {urgency_tag} {state.get('urgency', 'low').upper()}\n"
        f"Handled by: {state.get('assigned_to', 'support').title()} Team\n"
        f"{'─' * 40}\n\n"
        f"{state.get('specialist_response', '')}"
    )
    return {
        "final_response": final,
        "history": [{"step": "format", "done": True}],
    }


# ── Router ────────────────────────────────────────────────────────────────────

def route_after_triage(state: SupportState) -> str:
    """Route to appropriate specialist. Falls back to 'general' for unknowns."""
    classification = state.get("classification", "general")
    return classification if classification in ("billing", "technical", "general") else "general"


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_support_graph():
    workflow = StateGraph(SupportState)
    workflow.add_node("triage", triage_node)
    workflow.add_node("billing", billing_node)
    workflow.add_node("technical", technical_node)
    workflow.add_node("general", general_node)
    workflow.add_node("format_response", format_response_node)

    workflow.set_entry_point("triage")
    workflow.add_conditional_edges(
        "triage",
        route_after_triage,
        {"billing": "billing", "technical": "technical", "general": "general"},
    )
    workflow.add_edge("billing", "format_response")
    workflow.add_edge("technical", "format_response")
    workflow.add_edge("general", "format_response")
    workflow.add_edge("format_response", END)
    return workflow.compile()


async def handle_ticket(ticket: str) -> str:
    app = build_support_graph()
    result = await app.ainvoke({"ticket": ticket, "history": []})
    return result["final_response"]


if __name__ == "__main__":
    TICKETS = [
        "I was charged twice for my subscription this month. Please refund the extra charge.",
        "The app crashes every time I try to upload a file larger than 10MB. Error: 'Internal Server Error'.",
        "How do I update the email address associated with my account?",
    ]

    async def run():
        for i, ticket in enumerate(TICKETS, 1):
            print(f"\n{'=' * 55}")
            print(f"Ticket {i}: {ticket[:65]}...")
            print("─" * 55)
            print(await handle_ticket(ticket))

    asyncio.run(run())
```

### Discussion Answers

**a) When is `Annotated[list[dict], operator.add]` essential vs. optional?**

In a DAG graph (no cycles, no fan-out), the reducer doesn't actively prevent data
loss because no two branches are updating the same field simultaneously.
However it DOES matter for accumulation: without `operator.add`, each node's
`{"history": [...]}` return overwrites the previous list instead of appending.
The reducer is ESSENTIAL whenever multiple nodes write to the same list field,
or when you need an accumulated log across the run. Without it, only the last
writer's entries survive.

**b) Defensive `route_after_triage` for unexpected values:**
```python
def route_after_triage(state: SupportState) -> str:
    raw = state.get("classification", "").strip().lower()
    # Normalize: payment -> billing, crash -> technical, etc.
    billing_aliases = {"billing", "payment", "invoice", "refund", "charge", "subscription"}
    technical_aliases = {"technical", "tech", "bug", "error", "crash", "system"}
    if raw in billing_aliases:
        return "billing"
    if raw in technical_aliases:
        return "technical"
    return "general"  # safe fallback
```

**c) Cyclic (negotiation) vs. DAG (support triage) implications:**

| | Negotiation (cyclic) | Support Triage (DAG) |
|--|--|--|
| Infinite loop risk | YES — must have max_rounds | No — graph terminates by structure |
| Termination condition | Required (FSM, round counter) | Built into graph (no back-edges to START) |
| Router complexity | Must check state + round number | Simple: read one field |
| State accumulation | Critical — history grows across loops | Optional — single pass |

---

## Exercise 12: Customer Support Triage — ADK Solution

### Complete implementation: `exercises/code_solutions/ex12_support_triage_adk_runner.py`

```python
"""
Customer Support Triage System — Google ADK version.
Run: python exercises/code_solutions/ex12_support_triage_adk_runner.py
Requires: OPENAI_API_KEY
"""
import asyncio
import os
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part


# ── Specialist Agents ─────────────────────────────────────────────────────────

billing_agent = LlmAgent(
    name="billing_agent",
    model="gpt-4o",
    instruction=(
        "You are a billing support specialist at a SaaS company. "
        "You handle questions about charges, refunds, invoices, subscriptions, "
        "and payment methods. "
        "When delegated a customer ticket, respond directly and empathetically "
        "with clear action steps in 2-3 paragraphs. "
        "Do not ask clarifying questions — work with the information given."
    ),
)

technical_agent = LlmAgent(
    name="technical_agent",
    model="gpt-4o",
    instruction=(
        "You are a technical support specialist at a SaaS company. "
        "You handle bugs, errors, crashes, feature questions, and system issues. "
        "When delegated a customer ticket, respond with numbered troubleshooting "
        "steps and be precise. "
        "Do not ask clarifying questions — work with the information given."
    ),
)

general_agent = LlmAgent(
    name="general_agent",
    model="gpt-4o",
    instruction=(
        "You are a friendly general support agent at a SaaS company. "
        "You handle account questions, how-to guides, and general inquiries. "
        "When delegated a customer ticket, respond warmly and concisely. "
        "Do not ask clarifying questions — work with the information given."
    ),
)


# ── Orchestrator ──────────────────────────────────────────────────────────────

orchestrator = LlmAgent(
    name="support_orchestrator",
    model="gemini-2.0-flash",
    instruction=(
        "You are a customer support orchestrator. Your job is to:\n\n"
        "1. Read the incoming support ticket carefully\n"
        "2. Classify it into one category:\n"
        "   - billing: charges, refunds, invoices, subscriptions, payment methods\n"
        "   - technical: bugs, errors, crashes, system issues, feature questions\n"
        "   - general: account questions, how-tos, feedback, anything else\n"
        "3. Immediately transfer to the right specialist:\n"
        "   - billing   -> transfer to billing_agent\n"
        "   - technical -> transfer to technical_agent\n"
        "   - general   -> transfer to general_agent\n\n"
        "Do NOT write a response yourself. "
        "Transfer immediately after classifying — let the specialist respond."
    ),
    sub_agents=[billing_agent, technical_agent, general_agent],
)


# ── Handler ───────────────────────────────────────────────────────────────────

async def handle_ticket(ticket: str, session_id: str = "support_001") -> str:
    """Process a support ticket using the ADK orchestrator."""
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="support_triage",
        user_id="customer",
        session_id=session_id,
    )

    runner = Runner(
        agent=orchestrator,
        app_name="support_triage",
        session_service=session_service,
    )

    message = Content(parts=[Part(text=f"Support ticket:\n\n{ticket}")])
    final_response = ""
    agent_used = "unknown"

    async for event in runner.run_async(
        user_id="customer",
        session_id=session_id,
        new_message=message,
    ):
        if hasattr(event, "author") and event.author:
            agent_used = event.author
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    print(f"   [ADK] Final response from: {agent_used}")
    return final_response


if __name__ == "__main__":
    TICKETS = [
        ("I was charged twice for my subscription this month. Please refund the extra charge.", "support_001"),
        ("The app crashes every time I upload a file. Error: 'Internal Server Error'.", "support_002"),
        ("How do I update the email address on my account?", "support_003"),
    ]

    async def run():
        for ticket, session_id in TICKETS:
            print(f"\n{'=' * 55}")
            print(f"Ticket: {ticket[:65]}...")
            print("─" * 55)
            print(await handle_ticket(ticket, session_id=session_id))

    asyncio.run(run())
```

### Discussion Answers

**a) Explicit vs. implicit routing — when to use each:**

| | Explicit (LangGraph router function) | Implicit (ADK LLM routing) |
|--|--|--|
| Correctness guarantee | Deterministic — always routes correctly | LLM can make classification errors |
| Auditability | Route decision visible in code | Embedded in LLM reasoning |
| New categories | Add one branch to router + one node | Update prompt + add sub_agent |
| Cost | No extra LLM call for routing | Routing is part of orchestrator LLM call |
| Best for | Precise, rule-based routing | Natural language classification with fuzzy boundaries |

Choose explicit routing when correctness is critical and categories are well-defined.
Choose implicit routing when the categories are nuanced and benefit from LLM understanding.

**b) How the orchestrator "remembers" its classification in ADK:**

ADK maintains a **conversation thread** within the session. When the orchestrator
runs, its reasoning and classification appear in the session's event history.
When a sub-agent is invoked via `agent_transfer`, the context of the conversation
so far (including what the orchestrator decided) is passed along in the session
state. There is no explicit Python variable holding `classification` — it lives
in the session's conversation history as the orchestrator's internal reasoning.

**c) Adding a 4th specialist (returns_node):**

LangGraph changes:
1. Create `returns_node` async function
2. `workflow.add_node("returns", returns_node)`
3. `workflow.add_edge("returns", "format_response")`
4. Add `"returns": "returns"` to `add_conditional_edges` dict
5. Update `route_after_triage` to return `"returns"` for returns tickets
6. Update `triage_node` system prompt to include "returns" as a category

ADK changes:
1. Create `returns_agent = LlmAgent(...)`
2. Add to `sub_agents=[..., returns_agent]`
3. Update orchestrator instruction to mention returns_agent and when to use it

Verdict: ADK requires fewer structural code changes (2 changes vs. 6).
LangGraph gives you explicit control of exactly when `returns` is chosen.

**d) Making ADK version production-ready — three specific changes:**

1. **Persistent sessions**: Replace `InMemorySessionService` with a database-backed
   session service (e.g., `VertexAiSessionService` or a custom Redis/PostgreSQL
   implementation). This survives server restarts.

2. **Structured logging and tracing**: Capture all ADK events (not just final response)
   and log `event.author`, `event.content`, and timestamps to a centralized log store.
   Add correlation IDs linking each ticket to its full event trace.

3. **Error handling and fallback**: Wrap `runner.run_async()` in try/except.
   If the orchestrator fails to route (no `is_final_response` event within a timeout),
   fall back to a default general response rather than returning an empty string.

---

*End of solutions. See the notes directory for conceptual explanations.*
