"""
LangGraph Negotiation Orchestration
=====================================
Orchestrates the real estate negotiation between buyer and seller agents
using a stateful LangGraph workflow.

LANGGRAPH CONCEPTS DEMONSTRATED:
  1. StateGraph — the main graph with shared typed state
  2. TypedDict state — the single source of truth all nodes share
  3. Annotated reducers — append to history without overwriting
  4. Async nodes — nodes that call async agent functions
  5. Conditional edges — route based on negotiation outcome
  6. Cycles — the negotiation loop (buyer → seller → check → buyer)
  7. Termination guards — max_rounds prevents infinite loops

WORKFLOW TOPOLOGY:
  START
    │
    ▼
  BUYER NODE (makes offer, calls MCP, calls GPT-4o)
    │
    ├── buyer_walked → END
    ├── accepted → END
    │
    ▼
  SELLER NODE (reads offer, calls MCP ×2, calls GPT-4o)
    │
    ├── accepted → END
    ├── rejected → END
    ├── deadlocked → END
    │
    └── continue → BUYER NODE (loop back)

USAGE:
  from m3_langgraph_multiagents.langgraph_flow import create_negotiation_graph, initial_state

  graph = create_negotiation_graph()
  result = await graph.ainvoke(initial_state())
  print(result["status"], result.get("agreed_price"))
"""

import asyncio
import operator
from typing import Annotated, Literal, Optional, TypedDict

from langgraph.graph import StateGraph, END

from m3_langgraph_multiagents.buyer_simple import BuyerAgent
from m3_langgraph_multiagents.seller_simple import SellerAgent
from m3_langgraph_multiagents.negotiation_types import NegotiationStatus


# ─── Shared State ─────────────────────────────────────────────────────────────

class NegotiationState(TypedDict):
    """
    The shared state for the entire LangGraph negotiation workflow.

    LangGraph concept:
    All nodes read from this state and return PARTIAL updates.
    LangGraph merges the updates automatically.

    The `Annotated[list, operator.add]` pattern means:
    - When a node returns {"history": [new_item]}, LangGraph APPENDS
      the new_item to the existing list
    - Without this, the new list would REPLACE the existing one
    - This is critical for accumulating round-by-round history

    DESIGN PRINCIPLES USED HERE:
    1. Immutable inputs (listing_price, buyer_budget, etc.) — set once
    2. Mutable position tracking (current_offer, current_counter)
    3. Status field for routing (determines which edge to take)
    4. Accumulated history (append-only via reducer)
    5. Per-agent LLM context (kept in state for memory across rounds)
    """

    # ── Property context (immutable) ─────────────────────────────────────────
    session_id: str
    property_address: str
    listing_price: float

    # ── Agent constraints (immutable) ─────────────────────────────────────────
    buyer_budget: float
    seller_minimum: float
    max_rounds: int

    # ── Current negotiation positions ─────────────────────────────────────────
    buyer_current_offer: float
    seller_current_counter: float

    # ── Round tracking ────────────────────────────────────────────────────────
    round_number: int

    # ── Negotiation outcome ───────────────────────────────────────────────────
    status: NegotiationStatus
    agreed_price: Optional[float]

    # ── Last negotiation message (for routing) ───────────────────────────────
    # These hold the most recent message from each agent
    # Used to pass information between nodes
    last_buyer_message: Optional[dict]
    last_seller_message: Optional[dict]

    # ── Accumulated history (APPEND-ONLY via reducer) ─────────────────────────
    # Each node returns {"history": [new_entry]} and LangGraph appends it
    # This gives us a complete audit trail of the negotiation
    history: Annotated[list[dict], operator.add]

    # ── Agent-level state ─────────────────────────────────────────────────────
    # These hold references to agent objects across node invocations
    # NOTE: In production, agents would be initialized separately.
    # For this workshop, we store them in state for simplicity.
    # (In a real system, use dependency injection or context variables)
    _buyer_agent_ref: Optional[object]
    _seller_agent_ref: Optional[object]


def initial_state(
    session_id: str = "neg_001",
    property_address: str = "742 Evergreen Terrace, Austin, TX 78701",
    listing_price: float = 485_000,
    buyer_budget: float = 460_000,
    seller_minimum: float = 445_000,
    max_rounds: int = 5,
) -> dict:
    """
    Create the initial state for a new negotiation.

    LangGraph concept:
    The initial state passed to graph.ainvoke() must include ALL
    required fields, even if they start as empty/None.
    Missing fields cause KeyError in nodes.
    """
    return {
        "session_id": session_id,
        "property_address": property_address,
        "listing_price": listing_price,
        "buyer_budget": buyer_budget,
        "seller_minimum": seller_minimum,
        "max_rounds": max_rounds,
        "buyer_current_offer": 0.0,
        "seller_current_counter": listing_price,
        "round_number": 0,
        "status": "negotiating",
        "agreed_price": None,
        "last_buyer_message": None,
        "last_seller_message": None,
        "history": [],  # Will be appended to by nodes
        "_buyer_agent_ref": None,
        "_seller_agent_ref": None,
    }


# ─── Nodes ────────────────────────────────────────────────────────────────────

async def initialize_agents_node(state: dict) -> dict:
    """
    Initialize buyer and seller agents before the negotiation starts.

    LangGraph concept:
    Nodes can do any work — including creating objects, making API calls,
    reading files. This node creates the agent objects once and stores
    references in state so subsequent nodes can reuse them.

    WHY A SEPARATE INIT NODE?
    We could initialize agents in the first buyer/seller node, but that
    would reinitialize them every iteration of the loop. Better to have
    a dedicated initialization node that runs exactly once.
    """
    session_id = state["session_id"]
    print("\n[LangGraph] Initializing agents...")

    buyer_agent = BuyerAgent(session_id=session_id)
    seller_agent = SellerAgent(session_id=session_id)

    print("[LangGraph] Agents initialized. Starting negotiation.")
    print(f"[LangGraph] Property: {state['property_address']}")
    print(f"[LangGraph] Listed at: ${state['listing_price']:,.0f}")
    print(f"[LangGraph] Buyer budget: ${state['buyer_budget']:,.0f}")
    print(f"[LangGraph] Seller minimum: ${state['seller_minimum']:,.0f}")
    print(f"[LangGraph] Max rounds: {state['max_rounds']}")

    return {
        "_buyer_agent_ref": buyer_agent,
        "_seller_agent_ref": seller_agent,
    }


async def buyer_node(state: dict) -> dict:
    """
    Buyer agent node — makes or updates an offer.

    LangGraph concept:
    This node reads from state, calls the async buyer agent, and returns
    a PARTIAL state update. LangGraph merges this with the existing state.

    Key state updates this node makes:
    - buyer_current_offer: the new offer price
    - round_number: increments
    - status: may change to "buyer_walked"
    - last_buyer_message: the latest buyer message for seller to read
    - history: appends this round's data (via reducer)

    ASYNC NODE:
    LangGraph supports async nodes natively. Since our agents make
    async MCP calls and async LLM calls, we need async nodes.
    """
    buyer_agent: BuyerAgent = state["_buyer_agent_ref"]
    round_number = state["round_number"]
    last_seller_msg_dict = state.get("last_seller_message")

    print(f"\n[LangGraph] -> BUYER NODE (Round {round_number + 1})")

    try:
        if last_seller_msg_dict is None:
            # First round — make initial offer
            buyer_message = await buyer_agent.make_initial_offer()
        else:
            # Subsequent rounds — respond to seller's counter
            buyer_message = await buyer_agent.respond_to_counter(last_seller_msg_dict)

    except Exception as e:
        print(f"[LangGraph] ERROR in buyer agent: {e}")
        return {
            "status": "error",
            "history": [{"round": round_number + 1, "agent": "buyer", "error": str(e)}],
        }

    # Determine status from the message type
    new_status = state["status"]
    if buyer_message["message_type"] == "WITHDRAW":
        new_status = "buyer_walked"
        print(f"[LangGraph] Buyer is walking away")
    elif buyer_message["message_type"] == "ACCEPT":
        new_status = "agreed"
        print(f"[LangGraph] Buyer accepts at ${buyer_message.get('price', 0):,.0f}")

    # History entry for this round
    history_entry = {
        "round": buyer_message["round"],
        "agent": "buyer",
        "message_type": buyer_message["message_type"],
        "price": buyer_message.get("price"),
        "message": buyer_message.get("message", "")[:200],
    }

    return {
        "buyer_current_offer": buyer_message.get("price") or state["buyer_current_offer"],
        "round_number": buyer_message["round"],
        "status": new_status,
        "agreed_price": buyer_message.get("price") if new_status == "agreed" else state.get("agreed_price"),
        "last_buyer_message": buyer_message,
        "history": [history_entry],  # Reducer appends this
    }


async def seller_node(state: dict) -> dict:
    """
    Seller agent node — responds to buyer's offer.

    LangGraph concept:
    Notice how the seller node reads last_buyer_message from state
    (set by buyer_node) and writes last_seller_message for buyer_node
    to read in the next iteration.

    This is the fundamental data flow pattern in LangGraph:
    Nodes don't call each other directly — they communicate through state.
    """
    seller_agent: SellerAgent = state["_seller_agent_ref"]
    round_number = state["round_number"]
    last_buyer_msg_dict = state.get("last_buyer_message")

    print(f"\n[LangGraph] -> SELLER NODE (Round {round_number})")

    if last_buyer_msg_dict is None:
        # Shouldn't happen -- seller always responds to buyer
        print("[LangGraph] WARN: No buyer message to respond to")
        return {"status": "error"}

    try:
        seller_message = await seller_agent.respond_to_offer(last_buyer_msg_dict)

    except Exception as e:
        print(f"[LangGraph] ERROR in seller agent: {e}")
        return {
            "status": "error",
            "history": [{"round": round_number, "agent": "seller", "error": str(e)}],
        }

    # Determine terminal/continuing status from seller message type.
    new_status = state["status"]
    agreed_price = state.get("agreed_price")

    if seller_message["message_type"] == "ACCEPT":
        new_status = "agreed"
        agreed_price = last_buyer_msg_dict.get("price")  # Seller accepted buyer's price
        print(f"[LangGraph] Seller accepts at ${agreed_price:,.0f}")
    elif seller_message["message_type"] == "REJECT":
        new_status = "seller_rejected"
        print(f"[LangGraph] Seller rejects")

    # Deadlock guard: if still negotiating at round limit, force terminal state.
    if round_number >= state["max_rounds"] and new_status == "negotiating":
        new_status = "deadlocked"
        print(f"[LangGraph] Max rounds reached -- deadlock")

    history_entry = {
        "round": seller_message["round"],
        "agent": "seller",
        "message_type": seller_message["message_type"],
        "price": seller_message.get("price"),
        "message": seller_message.get("message", "")[:200],
    }

    # Return only changed fields; LangGraph merges these into the shared state.
    return {
        "seller_current_counter": seller_message.get("price") or state["seller_current_counter"],
        "status": new_status,
        "agreed_price": agreed_price,
        "last_seller_message": seller_message,
        "history": [history_entry],  # Reducer appends this
    }


# ─── Routing Functions ────────────────────────────────────────────────────────

def route_after_buyer(state: dict) -> Literal["to_seller", "end"]:
    """
    Determine next step after buyer node runs.

    LangGraph concept:
    Router functions ONLY read state and return a string key.
    They should be fast, pure functions with no side effects.
    The string they return maps to a node name in add_conditional_edges().

    Route to "end" if:
    - Buyer walked away
    - Buyer accepted seller's counter
    - An error occurred

    Otherwise route to "to_seller" to continue negotiation.
    """
    # Router decisions are driven only by state, never by side effects.
    status = state.get("status", "negotiating")

    if status in ("buyer_walked", "agreed", "error"):
        return "end"

    return "to_seller"


def route_after_seller(state: dict) -> Literal["continue", "end"]:
    """
    Determine next step after seller node runs.

    Route to "continue" (loops back to buyer) if negotiation is still active.
    Route to "end" for all terminal states.
    """
    # If seller emitted any terminal status, stop graph execution.
    status = state.get("status", "negotiating")

    if status != "negotiating":
        return "end"

    # Secondary termination guard in case status was not flipped by a node.
    round_number = state.get("round_number", 0)
    max_rounds = state.get("max_rounds", 5)

    if round_number >= max_rounds:
        return "end"

    return "continue"


# ─── Graph Assembly ───────────────────────────────────────────────────────────

def create_negotiation_graph() -> StateGraph:
    """
    Build and compile the LangGraph negotiation workflow.

    LangGraph concept — graph structure:
    We build the graph in 4 steps:
    1. Create StateGraph with state schema
    2. Add nodes (the processing functions)
    3. Add edges (the connections between nodes)
    4. Compile the graph (validates and optimizes it)

    The resulting graph looks like:
      START → init → buyer → seller → (check) → buyer (loop)
                                             ↓
                                            END
    """
    # Use the declared state schema so LangGraph merges partial node updates
    # instead of replacing the entire state with each node return value.
    workflow = StateGraph(NegotiationState)

    # ── Add nodes ─────────────────────────────────────────────────────────────
    workflow.add_node("init", initialize_agents_node)
    workflow.add_node("buyer", buyer_node)
    workflow.add_node("seller", seller_node)

    # ── Set entry point ────────────────────────────────────────────────────────
    workflow.set_entry_point("init")

    # ── Add edges ──────────────────────────────────────────────────────────────

    # init always goes to buyer (unconditional edge)
    workflow.add_edge("init", "buyer")

    # buyer → seller OR end (conditional based on buyer's decision)
    workflow.add_conditional_edges(
        "buyer",           # Source node
        route_after_buyer, # Router function
        {
            "to_seller": "seller",  # "to_seller" → go to seller node
            "end": END,             # "end" → terminate graph
        }
    )

    # seller → buyer (loop) OR end (conditional based on seller's decision)
    workflow.add_conditional_edges(
        "seller",
        route_after_seller,
        {
            "continue": "buyer",  # "continue" → loop back to buyer
            "end": END,           # "end" → terminate graph
        }
    )

    # ── Compile ────────────────────────────────────────────────────────────────
    # Compilation validates the graph structure and prepares it for execution
    graph = workflow.compile()

    return graph


# ─── Results Display ──────────────────────────────────────────────────────────

def print_negotiation_results(final_state: dict) -> None:
    """Display the final negotiation results and history."""

    print("\n" + "=" * 65)
    print("NEGOTIATION COMPLETE -- LangGraph Orchestrated")
    print("=" * 65)

    status = final_state.get("status", "unknown")
    agreed_price = final_state.get("agreed_price")
    listing_price = final_state.get("listing_price", 485_000)

    # Outcome
    outcome_icons = {
        "agreed": "[OK] DEAL REACHED",
        "buyer_walked": "BUYER WALKED AWAY",
        "deadlocked": "DEADLOCK -- MAX ROUNDS REACHED",
        "seller_rejected": "SELLER REJECTED",
        "error": "ERROR",
    }
    print(f"\nOutcome: {outcome_icons.get(status, status.upper())}")

    if agreed_price:
        savings = listing_price - agreed_price
        savings_pct = savings / listing_price * 100
        print(f"Agreed Price:  ${agreed_price:,.0f}")
        print(f"Listed Price:  ${listing_price:,.0f}")
        print(f"Buyer Saved:   ${savings:,.0f} ({savings_pct:.1f}% below listing)")

    # Round summary
    history = final_state.get("history", [])
    rounds_used = final_state.get("round_number", 0)
    print(f"\nRounds Used: {rounds_used} of {final_state.get('max_rounds', 5)}")
    print(f"Messages: {len(history)}")

    # History table
    if history:
        print("\nNEGOTIATION HISTORY:")
        print(f"  {'Rnd':>3} {'Agent':>8} {'Type':>16} {'Price':>12}")
        print("  " + "-" * 45)
        for entry in history:
            price_str = f"${entry.get('price', 0):,.0f}" if entry.get("price") else "—"
            print(
                f"  {entry.get('round', 0):>3} "
                f"{entry.get('agent', ''):>8} "
                f"{entry.get('message_type', ''):>16} "
                f"{price_str:>12}"
            )

    print("\n" + "=" * 65)


# ─── Standalone Runner ────────────────────────────────────────────────────────

async def run_negotiation(
    session_id: str = "neg_001",
    property_address: str = "742 Evergreen Terrace, Austin, TX 78701",
    listing_price: float = 485_000,
    buyer_budget: float = 460_000,
    seller_minimum: float = 445_000,
    max_rounds: int = 5,
) -> dict:
    """
    Run a complete negotiation using the LangGraph workflow.

    This function:
    1. Creates the graph
    2. Creates the initial state
    3. Invokes the graph asynchronously
    4. Displays and returns the final state

    LangGraph concept — ainvoke:
    graph.ainvoke() runs the entire graph from START to END,
    following all conditional edges until a terminal state is reached.
    The returned dict is the FINAL state after all nodes have run.
    """
    print("\n" + "=" * 65)
    print("REAL ESTATE NEGOTIATION -- LangGraph Version")
    print("=" * 65)

    # Build the graph
    graph = create_negotiation_graph()

    # Create initial state
    state = initial_state(
        session_id=session_id,
        property_address=property_address,
        listing_price=listing_price,
        buyer_budget=buyer_budget,
        seller_minimum=seller_minimum,
        max_rounds=max_rounds,
    )

    print(f"\nStarting negotiation for: {property_address}")
    print(f"Listing: ${listing_price:,.0f} | Buyer budget: ${buyer_budget:,.0f} | Max rounds: {max_rounds}")

    # Run the graph
    # ainvoke() runs the full graph asynchronously
    # It handles the buyer→seller→buyer loop automatically
    # It stops when route_after_seller returns "end"
    final_state = await graph.ainvoke(state)

    # Display results
    print_negotiation_results(final_state)

    return final_state


if __name__ == "__main__":
    # Can be run directly for testing
    asyncio.run(run_negotiation())
