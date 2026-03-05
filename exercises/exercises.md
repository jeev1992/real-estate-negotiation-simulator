# Exercises
## Real Estate Negotiation Workshop

Complete these exercises to deepen your understanding of MCP, A2A, LangGraph, and Google ADK.

---

## How to Use These Exercises

- **Part A** (Exercises 1–3): Conceptual — answer in writing or discussion
- **Part B** (Exercises 4–7): Code modifications — change existing files
- **Part C** (Exercises 8–10): Extensions — add new features

See `solutions.md` for complete answers and code.

---

## Part A — Conceptual Understanding

### Exercise 1: MCP vs A2A vs Direct API

**Scenario**: You're building a stock trading agent that needs to:
1. Fetch current stock prices from Yahoo Finance
2. Check your internal portfolio database
3. Communicate trade decisions to a risk assessment agent
4. Ask a news analysis agent for market sentiment

**Questions**:
a) Which of the four integrations above would you implement with **MCP**? Explain why.
b) Which would you implement with **A2A**? Explain why.
c) Which would be better as a **direct Python function call**? Why?
d) Draw a simple architecture diagram showing all four integrations.

**Hint**: Remember — MCP is for agent-to-external-system; A2A is for agent-to-agent.

---

### Exercise 2: LangGraph State Design

Look at our `NegotiationState` in `m3_agents/langgraph_flow.py`.

**Questions**:
a) Why does `history` use `Annotated[list, operator.add]` instead of just `list`?
   What would happen if you removed the `Annotated` wrapper?

b) We store `buyer_current_offer` and `seller_current_counter` as separate fields.
   Why not just store the last A2A message and extract the price from it?

c) The `status` field is a string (`"negotiating"`, `"agreed"`, etc.).
   What are the advantages of using `Literal["negotiating", "agreed", ...]` instead?

d) **Design challenge**: If you added a **mediator agent** that could intervene
   when negotiations stall, what new fields would you add to `NegotiationState`?
   Sketch the new state schema.

---

### Exercise 3: Information Asymmetry and MCP Access Control

**Scenario**: In our simulator, the seller agent calls `get_minimum_acceptable_price()`
but the buyer agent does not. This is enforced by convention (we just don't give
the buyer that MCP connection).

**Questions**:
a) How would you enforce this access restriction in a **real production system**?
   Describe at least two different technical approaches.

b) What would happen to the negotiation dynamics if the buyer agent COULD access
   `get_minimum_acceptable_price()`? Would this be realistic? Would it be ethical?

c) In human real estate negotiations, a buyer's agent sometimes has information
   about the seller's motivation (e.g., "they're desperate to close fast").
   How could you model this information advantage in our MCP architecture?

d) MCP doesn't have a built-in access control standard yet. What would you add
   to the MCP protocol to handle this? (Think: headers, tokens, scopes, etc.)

---

## Part B — Code Modifications

### Exercise 4: Add a New MCP Tool

**Task**: Add a `get_property_inspection_report` tool to `m2_mcp/pricing_server.py`.

**Requirements**:
- Tool signature: `get_property_inspection_report(property_id: str, inspection_type: str = "standard") -> dict`
- Returns a simulated inspection report with:
  - `foundation_rating`: "excellent" | "good" | "fair" | "poor"
  - `roof_age_years`: integer
  - `hvac_age_years`: integer
  - `estimated_repair_costs`: dict with categories
  - `overall_recommendation`: "proceed" | "negotiate_repairs" | "walk_away"
- Add the tool to `pricing_server.py`
- Modify `buyer_simple.py` to call this tool before making offers

**Starting point**:
```python
@mcp.tool()
def get_property_inspection_report(property_id: str, inspection_type: str = "standard") -> dict:
    """
    Get a simulated property inspection report.

    Args:
        property_id: Property identifier
        inspection_type: "standard", "full", or "structural"

    Returns:
        Inspection report with condition ratings and repair estimates
    """
    # YOUR CODE HERE
    pass
```

**Verification**: Run `python main_simple.py` and observe the buyer referencing inspection data in its offers.

---

### Exercise 5: Modify the Negotiation Strategy

**Task**: Change the seller's strategy to use an **anchoring** technique.

**Background**: Anchoring in negotiation means stating a very high initial number
to make subsequent concessions seem more generous. Instead of starting at $477K,
have the seller start at $495K (above listing!) with a very strong justification.

**Requirements**:
- Modify `SELLER_SYSTEM_PROMPT` in `seller_simple.py`
- The seller should start at $495,000 with strong justification (renovations worth $75K)
- The seller should still never go below $445,000
- Run the simulation and observe: does the final agreed price change?

**Bonus**: Also try changing the buyer to be more aggressive (start at $400K).
What happens to the negotiation dynamics?

**Questions to answer after running**:
- Did anchoring change the final outcome?
- How many rounds did it take to reach agreement?
- Was any round of the negotiation "deadlocked" by this strategy?

---

### Exercise 6: Add a Deadlock Detection Tool

**Task**: Add a `check_negotiation_deadlock` tool to the pricing server,
and have the buyer use it to decide when to walk away vs. keep negotiating.

**Requirements**:
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
    Analyze whether a negotiation is heading toward deadlock.

    Returns:
        {
            "deadlock_risk": "low" | "medium" | "high" | "certain",
            "gap_amount": float,
            "gap_percent": float,
            "rounds_remaining": int,
            "recommendation": str,
            "suggested_action": "continue" | "make_concession" | "walk_away"
        }
    """
    # YOUR CODE HERE
    pass
```

**Then**: Modify `buyer_simple.py` to call this tool and use the result in its decision-making.

---

### Exercise 7: Implement an SSE Client

**Task**: Modify the buyer agent to connect to the pricing server via **SSE** instead of stdio.

**Steps**:
1. Start the pricing server in SSE mode:
   ```bash
   python m2_mcp/pricing_server.py --sse --port 8001
   ```

2. Modify `call_pricing_mcp()` in `buyer_simple.py` to use SSE:
   ```python
   from mcp.client.sse import sse_client

   async def call_pricing_mcp_sse(tool_name: str, arguments: dict) -> dict:
       async with sse_client("http://localhost:8001/sse") as (read, write):
           # YOUR CODE HERE — same pattern as stdio version
           pass
   ```

3. Make the transport configurable via an environment variable:
   ```bash
   export MCP_TRANSPORT=sse  # or "stdio" (default)
   ```

**Questions**:
- What are the differences in the connection lifecycle between stdio and SSE?
- When would you prefer SSE over stdio in a production system?

---

## Part C — Extension Challenges

### Exercise 8: Add a Mediator Agent

**Task**: Add a third agent — a `MediatorAgent` — that intervenes when the
negotiation reaches round 4 without agreement and proposes a compromise.

**Requirements**:
- Create `m3_agents/mediator_simple.py`
- The mediator has access to BOTH buyer and seller's last offers
- Uses GPT-4o to propose a fair compromise price
- Modify `m3_agents/langgraph_flow.py` to:
  - Add a `mediator` node
  - Route to mediator when `round_number == 4` and status is still `"negotiating"`
  - Both agents can ACCEPT or REJECT the mediator's proposal

**LangGraph node to add**:
```python
async def mediator_node(state: dict) -> dict:
    """
    Mediator agent node — proposes compromise when negotiation stalls.
    Activated in round 4 if no agreement reached.
    """
    buyer_offer = state["buyer_current_offer"]
    seller_counter = state["seller_current_counter"]
    # YOUR CODE HERE
    pass
```

**New graph topology**:
```
buyer → seller → (rounds 1-3: continue to buyer)
               → (round 4, no deal: mediator)
                                        │
                               both agents vote
                                   ↓         ↓
                                ACCEPT    REJECT
                                  ↓         ↓
                                 END      END (deadlock)
```

---

### Exercise 9: Add Conversation Memory Across Sessions

**Task**: Implement persistent negotiation memory so that if a buyer and seller
negotiate and FAIL to reach a deal, their next negotiation session "remembers"
the previous failed attempt.

**Background**: In real estate, buyers and sellers sometimes negotiate multiple
times (e.g., offer falls through due to inspection, they try again).

**Requirements**:
- Create a simple `negotiation_memory.json` file to store past sessions
- Buyer agent reads past sessions: "In a previous negotiation in October, seller wouldn't go below $452K"
- Seller agent reads past sessions: "This buyer previously walked at $458K"
- Use this information to adjust starting positions

**Data structure**:
```json
{
  "sessions": [
    {
      "session_id": "neg_abc123",
      "date": "2025-01-15",
      "property": "742 Evergreen Terrace...",
      "outcome": "deadlocked",
      "buyer_final_offer": 448000,
      "seller_final_counter": 458000,
      "rounds": 5
    }
  ]
}
```

---

### Exercise 10: Build a Negotiation Analytics Dashboard

**Task**: After each negotiation run, generate an analytics report showing:

1. **Convergence graph**: Round-by-round buyer offers and seller counters
   (text-based ASCII chart — no external libraries required)

2. **Strategy analysis**: Did either agent deviate from expected strategy?
   (e.g., buyer increased offer by too much in one round)

3. **MCP usage stats**: How many MCP calls were made per agent?
   Which tools were called most?

4. **Outcome prediction**: Before the final round, could you have predicted
   the outcome? What signals indicated agreement/deadlock?

**Example output**:
```
NEGOTIATION ANALYTICS — Session neg_001
════════════════════════════════════════

CONVERGENCE CHART:
$490K |                                              ← Listing
      |  Seller: 477K────465K────456K────449K
$470K |
      |
$450K |                              ─────[449K] ← AGREED
      |           Buyer: 438K──445K─/
$430K |  Buyer: 425K─/
      |
$410K |
      Round:    1      2      3      4

MCP TOOL USAGE:
  Buyer: get_market_price ×5, calculate_discount ×5
  Seller: get_market_price ×4, get_inventory_level ×4, get_minimum_acceptable_price ×1

OUTCOME PREDICTION (Round 3):
  Gap at start of round 3: $18,000 (buyer 438K, seller 456K)
  Average round-by-round convergence: ~$12K
  Predicted rounds to agreement: 1.5 → Agreement likely in round 4-5
  Actual: Agreement reached in round 4 ✓
```

---

## Part D — New System: Customer Support Triage

Build a completely different multi-agent system from scratch to prove you have
internalized the framework patterns — not just memorized the real estate code.

**Domain**: A company's incoming support tickets must be classified and routed
to the right specialist, who then drafts a professional response.

```
Incoming Ticket
       |
  [Triage Agent] -- classifies: billing / technical / general
       |                       + urgency: low / medium / high
    (route)
   /    |    \
[Billing] [Technical] [General]
   \    |    /
  [Format Response]
       |
   Final Reply
```

**Exercise 11** implements this in **LangGraph** (OpenAI GPT-4o).
**Exercise 12** implements the same system in **Google ADK** (Gemini 2.0 Flash).

Completing both lets you compare the two frameworks side-by-side on identical
requirements.

---

### Exercise 11: Customer Support Triage — LangGraph

**File to create**: `bonus/support_triage_langgraph.py`

**State schema** (given — do not change):
```python
from typing import Annotated
import operator
from typing_extensions import TypedDict

class SupportState(TypedDict):
    ticket: str                               # Raw ticket text
    classification: str                       # "billing" | "technical" | "general"
    urgency: str                              # "low" | "medium" | "high"
    assigned_to: str                          # Which specialist handled it
    specialist_response: str                  # Specialist's draft response
    final_response: str                       # Formatted output
    history: Annotated[list[dict], operator.add]
```

**Implement these five nodes**:

1. **`triage_node`** — calls GPT-4o to classify the ticket.
   Use `response_format={"type": "json_object"}` and prompt for:
   ```json
   { "classification": "billing|technical|general", "urgency": "low|medium|high", "reasoning": "..." }
   ```

2. **`billing_node`** — billing specialist writes a 2-3 paragraph empathetic response

3. **`technical_node`** — technical specialist writes numbered troubleshooting steps

4. **`general_node`** — general support agent writes a friendly, concise response

5. **`format_response_node`** — assembles the final output:
   ```
   SUPPORT TICKET RESPONSE
   ========================================
   Classified: BILLING
   Urgency:    [!] HIGH
   Handled by: Billing Team
   ----------------------------------------
   [specialist_response here]
   ```
   (urgency tags: `[!]` = high, `[~]` = medium, `[ ]` = low)

**Implement this router**:
```python
def route_after_triage(state: SupportState) -> str:
    """Return "billing", "technical", or "general"."""
    # YOUR CODE HERE
    pass
```

**Build this graph topology**:
```
START -> triage
triage --[conditional]--> billing | technical | general
billing  ->  format_response
technical -> format_response
general  ->  format_response
format_response -> END
```

**Test with these tickets** (all three should route to different specialists):
```python
TICKETS = [
    "I was charged twice for my subscription this month. Please refund the extra charge.",
    "The app crashes every time I try to upload a file. Error: 'Internal Server Error'.",
    "How do I update the email address on my account?",
]
```

**Discussion questions**:

a) The `history` field uses `Annotated[list[dict], operator.add]`. This graph has
   no cycles — each run is `triage -> specialist -> format -> END`. Would the reducer
   matter if there were no branching at all? When is it ESSENTIAL vs. optional?

b) What happens if GPT-4o returns `"payment"` instead of `"billing"` as the classification?
   Write a defensive version of `route_after_triage` that handles unexpected values.

c) The negotiation graph (m3_agents) is **cyclic** (buyer -> seller -> buyer...).
   This support graph is a **DAG** (no cycles). How does this difference affect:
   - Risk of infinite loops?
   - Need for a termination condition like `max_rounds`?
   - Complexity of the routing function?

---

### Exercise 12: Customer Support Triage — Google ADK

**File to create**: `bonus/support_triage_adk.py`

**Architecture** (ADK pattern — fundamentally different from LangGraph):

In ADK, you don't write a Python router. Instead, you register specialist agents
as `sub_agents` of an orchestrator. The orchestrator LLM decides which sub-agent
to transfer to, based on its instruction prompt.

```python
orchestrator = LlmAgent(
    name="support_orchestrator",
    model="gemini-2.0-flash",
    instruction="...",   # Tell it to classify + use agent_transfer to delegate
    sub_agents=[billing_agent, technical_agent, general_agent],
)
```

**Starting skeleton**:
```python
import asyncio
import os
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

# 1. Define three specialist agents (implement their instructions)
billing_agent = LlmAgent(
    name="billing_agent",
    model="gemini-2.0-flash",
    instruction="...",  # YOUR CODE HERE
)

technical_agent = LlmAgent(
    name="technical_agent",
    model="gemini-2.0-flash",
    instruction="...",  # YOUR CODE HERE
)

general_agent = LlmAgent(
    name="general_agent",
    model="gemini-2.0-flash",
    instruction="...",  # YOUR CODE HERE
)

# 2. Define orchestrator with sub-agents
orchestrator = LlmAgent(
    name="support_orchestrator",
    model="gemini-2.0-flash",
    instruction="...",  # YOUR CODE HERE -- classify and delegate
    sub_agents=[billing_agent, technical_agent, general_agent],
)

# 3. Implement the handler
async def handle_ticket(ticket: str, session_id: str = "support_001") -> str:
    session_service = InMemorySessionService()
    # YOUR CODE HERE
    pass

# 4. Test it
if __name__ == "__main__":
    asyncio.run(handle_ticket(
        "I was charged twice this month.",
        session_id="test_001"
    ))
```

**Requirements**:
- **Orchestrator instruction**: tell Gemini to classify the ticket and use
  `agent_transfer` to hand off to the right sub-agent. It should NOT write
  a response itself — the specialist does that.
- **Specialist instructions**: each specialist must know their domain and
  respond directly to the customer.
- **`handle_ticket`**:
  1. Create `InMemorySessionService` and call `create_session`
  2. Create a `Runner` with the orchestrator
  3. Build a `Content(parts=[Part(text=...)])` message
  4. Iterate `runner.run_async(...)` and capture the final response

**Hint — collecting ADK output**:
```python
async for event in runner.run_async(
    user_id="customer", session_id=session_id, new_message=message
):
    if event.is_final_response() and event.content and event.content.parts:
        final_response = event.content.parts[0].text
```

**Discussion questions**:

a) **Explicit vs. implicit routing**:
   - LangGraph (Ex. 11): `route_after_triage()` is a deterministic Python function
   - ADK (Ex. 12): the orchestrator LLM decides which sub-agent to invoke
   When would you trust implicit LLM routing? When is explicit routing safer?

b) **Intermediate state**: In LangGraph, every node can read `state["classification"]`
   set by `triage_node`. In ADK, how does the orchestrator "remember" its
   classification decision before handing off to the sub-agent?

c) **Adding a 4th specialist**: Suppose you need a `returns_node` (handles
   product returns separately from general billing).
   - In LangGraph (Ex. 11): list every change required
   - In ADK (Ex. 12): list every change required
   Which framework made this extension easier?

d) **Production readiness**: List three specific things you would change
   to make the ADK version production-ready (persistent sessions, logging,
   error handling, etc.).

**Framework comparison** (fill in after completing both exercises):

| Aspect | LangGraph (Ex. 11) | ADK (Ex. 12) |
|--------|--------------------|--------------|
| Routing mechanism | Python router function | LLM decision (agent_transfer) |
| State visibility | Explicit TypedDict fields | ADK session service |
| Adding a new specialist | New node + new edge + new router case | New LlmAgent + add to sub_agents list |
| Inspecting intermediate steps | State dict at each node | ADK event stream |
| Lines of code (approximate) | ~130 lines | ~80 lines |

---

## Bonus: Research Exercises

### Bonus A: MCP Ecosystem Research
Find 3 publicly available MCP servers (besides GitHub's) and for each:
1. What tool does it connect to?
2. What tools does it expose?
3. Which agent use case would benefit from it?

Resources: https://github.com/modelcontextprotocol/servers

### Bonus B: LangGraph Persistence
Implement PostgreSQL checkpointing for the LangGraph workflow.
Reference: LangGraph docs on `PostgresSaver`

### Bonus C: ADK + Vertex AI
Modify the ADK version to run on Google Cloud Vertex AI instead of
the AI Studio free tier. What changes are needed?

---

*See `solutions.md` for complete answers and code for all exercises.*
