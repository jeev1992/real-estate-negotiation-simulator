"""
Negotiation Orchestrator — Idiomatic ADK
==========================================
LoopAgent wrapping a SequentialAgent (buyer → seller) to run multi-round
negotiation with real MCP tools. The buyer calls pricing tools before each
offer. The seller is told to call its tools (market price, inventory, the
secret floor price) every round; in practice it researches in round 1 and
reuses that from its context afterwards — submit_decision enforces the floor
every round regardless.

Demonstrates: LoopAgent, SequentialAgent, McpToolset, output_key state
passing, after_agent_callback with escalation, before_tool_callback
allowlists, information asymmetry (tool allowlists control what each agent
can CALL; include_contents="none" on the buyer controls what it can READ).

Run with:
    adk web m2_adk_multiagents/negotiation_agents/
"""

import json
import sys
from pathlib import Path

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from google.adk.tools.tool_context import ToolContext
from google.genai import types

import os

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRICING_SERVER = str(_REPO_ROOT / "m1_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m1_mcp" / "inventory_server.py")

# --- Tool allowlists (information asymmetry) ---

_BUYER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "submit_offer",  # structured offer signal
}

_SELLER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_inventory_level",
    "get_minimum_acceptable_price",  # seller-only
    "submit_decision",  # structured decision signal
}


def _enforce_buyer_allowlist(
    tool: BaseTool, args: dict, tool_context: ToolContext
):
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the buyer"}
    return None


def _enforce_seller_allowlist(
    tool: BaseTool, args: dict, tool_context: ToolContext
):
    if tool.name not in _SELLER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the seller"}
    return None


# --- Decision tools (structured signals, not text parsing) ---


_BUYER_MAX_BUDGET = 460000


def _append_history(
    tool_context: ToolContext, role: str, action: str, price: int | None
) -> None:
    """Append one entry to the shared offer_history list in state (UI-visible)."""
    entry = {"role": role, "action": action, "price": price}
    history = tool_context.state.get("offer_history", [])
    tool_context.state["offer_history"] = history + [entry]


def submit_offer(
    price: int, walk_away: bool, tool_context: ToolContext
) -> dict:
    """Record the buyer's offer for this round.

    Args:
        price: Offer price in dollars. Must be <= 460000. Ignored if walk_away is True.
        walk_away: True to end the negotiation because the seller won't meet the buyer's terms.
    """
    if walk_away:
        tool_context.state["buyer_walk_away"] = True
        _append_history(tool_context, "buyer", "WALK_AWAY", None)
        return {"recorded": "WALK_AWAY"}
    if price > _BUYER_MAX_BUDGET:
        # No number in the message: the seller reads the buyer's tool results
        # as context, so "$460000" here would hand it the buyer's budget.
        return {"error": f"offer {price} is over your client's maximum budget — offer less"}
    tool_context.state["buyer_offer_price"] = price
    _append_history(tool_context, "buyer", "OFFER", price)
    return {"recorded": price}


def submit_decision(
    action: str, price: int, tool_context: ToolContext
) -> dict:
    """Submit the seller's final decision for this round.

    The seller's minimum is enforced here, not left to the model: an offer at
    or above it is always recorded as ACCEPT, and nothing below it can be
    accepted or countered.

    Args:
        action: Exactly "ACCEPT" or "COUNTER" — no other values.
        price: The price in dollars (e.g. 445000 or 477000).
    """
    action_upper = action.strip().upper()
    if action_upper not in ("ACCEPT", "COUNTER"):
        return {"error": f"action must be ACCEPT or COUNTER, got: {action}"}
    buyer_offer = tool_context.state.get("buyer_offer_price")
    if action_upper == "ACCEPT" and buyer_offer is None:
        # Fail closed: without an offer recorded this round there's nothing to
        # accept — the model may have misread the buyer's message.
        return {"error": "The buyer hasn't recorded an offer this round, so there is nothing to ACCEPT. COUNTER instead."}
    decision = _apply_floor_policy(
        action_upper,
        price,
        buyer_offer=buyer_offer,
        floor=tool_context.state.get("seller_floor_price"),
    )
    if "error" in decision:
        return decision
    action_upper, price = decision["action"], decision["price"]
    tool_context.state["seller_decision"] = {
        "action": action_upper,
        "price": price,
    }
    _append_history(tool_context, "seller", action_upper, price)
    response = {"recorded": action_upper, "price": price}
    if decision["note"]:
        response["note"] = decision["note"]
    return response


# --- Seller floor policy (deterministic, like the buyer's budget check) ---


def _floor_from_tool_response(response) -> int | None:
    """Read minimum_acceptable_price from a get_minimum_acceptable_price MCP result."""
    if not isinstance(response, dict):
        return None
    candidates = [response, response.get("structuredContent")]
    for block in response.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            try:
                candidates.append(json.loads(block.get("text", "")))
            except ValueError:
                pass
    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("result"), dict):
            candidate = candidate["result"]
        constraints = candidate.get("pricing_constraints") if isinstance(candidate, dict) else None
        if isinstance(constraints, dict) and isinstance(constraints.get("minimum_acceptable_price"), int):
            return constraints["minimum_acceptable_price"]
    return None


def _remember_seller_floor(
    tool: BaseTool, args: dict, tool_context: ToolContext, tool_response
):
    """after_tool_callback: keep the floor in state so submit_decision can enforce it.

    The buyer never sees it — no buyer prompt templates this key.
    """
    if tool.name == "get_minimum_acceptable_price":
        floor = _floor_from_tool_response(tool_response)
        if floor is not None:
            tool_context.state["seller_floor_price"] = floor
    return None


def _apply_floor_policy(
    action: str, price: int, buyer_offer: int | None, floor: int | None
) -> dict:
    """Return {"action", "price", "note"} after enforcing the floor, or {"error"}.

    - An offer at or above the floor MUST be accepted, at the buyer's price.
    - Nothing may be accepted or countered below the floor.
    """
    if floor is None:
        return {"error": "Call get_minimum_acceptable_price before submit_decision."}
    if buyer_offer is not None and buyer_offer >= floor:
        note = None
        if action != "ACCEPT" or price != buyer_offer:
            note = (
                f"The buyer's offer of ${buyer_offer:,} meets your minimum, so it was "
                "recorded as ACCEPT at that price. Your reply MUST accept it, without "
                "mentioning your minimum or that you have one."
            )
        return {"action": "ACCEPT", "price": buyer_offer, "note": note}
    if action == "ACCEPT" and buyer_offer is not None:
        return {"error": "The buyer's offer is below your minimum, so you cannot ACCEPT it. COUNTER instead."}
    if price < floor:
        return {"error": f"{action} at ${price:,} is below your minimum. Use a price at or above it."}
    return {"action": action, "price": price, "note": None}


# --- Callbacks ---


def _check_agreement(callback_context: CallbackContext):
    """After the seller responds, check the structured decision. Escalate on ACCEPT."""
    decision = callback_context.state.get("seller_decision")
    if isinstance(decision, dict) and decision.get("action") == "ACCEPT":
        # ADK drops a bare escalate: a callback only emits an event if it changes state.
        callback_context.state["loop_exit_reason"] = f"ACCEPT at ${decision.get('price', 0):,}"
        callback_context.actions.escalate = True
    return None


def _check_walk_away(callback_context: CallbackContext):
    """After the buyer responds, end the negotiation if the buyer walked away."""
    if callback_context.state.get("buyer_walk_away"):
        callback_context.state["loop_exit_reason"] = "BUYER_WALK_AWAY"
        callback_context.actions.escalate = True
    return None


def _skip_if_walked_away(callback_context: CallbackContext):
    """Skip the seller's turn and end the loop if the buyer already walked away."""
    if callback_context.state.get("buyer_walk_away"):
        callback_context.actions.escalate = True
        return types.Content(
            role="model",
            parts=[types.Part(text="SELLER: The buyer walked away — negotiation ended.")],
        )
    return None


def _init_round_state(callback_context: CallbackContext):
    """Runs before the buyer each round.

    - Round 1: make sure seller_response exists for the {seller_response} placeholder.
    - Every round: clear last round's recorded offer, so a buyer that skips
      submit_offer can't leave a stale price for submit_decision to enforce.
    """
    if "seller_response" not in callback_context.state:
        callback_context.state["seller_response"] = "(No seller response yet — this is round 1)"
    if callback_context.state.get("buyer_offer_price") is not None:
        callback_context.state["buyer_offer_price"] = None
    return None


buyer = LlmAgent(
    name="buyer",
    # Don't give the buyer the shared session history: ADK shows every agent the
    # other agents' turns as context — including the seller's tool results (its
    # floor price). The buyer gets the seller's reply via {seller_response}.
    include_contents="none",
    model=MODEL,
    instruction=(
        "You ARE the buyer's agent in a LIVE negotiation — not an assistant "
        "waiting on anyone. You represent a client purchasing 742 Evergreen "
        "Terrace, Austin, TX 78701 (listed at $485,000).\n\n"
        "CLIENT CONSTRAINTS:\n"
        "- Maximum budget: $460,000 — the submit_offer tool REJECTS anything higher.\n"
        "- Target acquisition price: $445,000–$455,000.\n"
        "- Pre-approved for financing, can close in 30–45 days.\n\n"
        "EACH ROUND you MUST, in order:\n"
        "1. Call your MCP pricing tools to get fresh market data.\n"
        "2. Decide exactly ONE new offer for this round:\n"
        "   - Round 1 (seller has not responded yet): ~12% below asking (~$425,000).\n"
        "   - Later rounds: raise your PREVIOUS offer by 2–4% toward the seller, "
        "never above $460,000.\n"
        "3. Call submit_offer(price=<int>, walk_away=False) to record it. "
        "Use walk_away=True ONLY if the seller refuses to go below $460,000.\n\n"
        "The seller's last response was:\n{seller_response}\n\n"
        "Then reply with ONE short paragraph: your new offer amount plus a "
        "data-backed justification. Begin the paragraph with the literal prefix "
        "'BUYER: '. Output ONLY that single 'BUYER: ...' paragraph — no preamble, "
        "no step-by-step thinking, no 'submitting offer' narration.\n\n"
        "CONFIDENTIAL — the seller must NEVER learn these, so never state them in your "
        "reply: your maximum budget ($460,000), your target range, your walk-away "
        "threshold, or any private client constraints. Reveal only the single offer number.\n"
        "- Never signal you are at or near your ceiling. Do NOT say things like 'the "
        "maximum I can accommodate', 'my highest/best/final offer', or 'the most I can pay'. "
        "Present each offer as a considered, market-based figure.\n"
        "- Never reference or guess the seller's minimum, floor, or 'minimum acceptable "
        "price' — you do NOT have that information.\n\n"
        "Do NOT write meta commentary such as "
        "'we will wait for the seller' or reminders/checklists — you ARE negotiating now."
        "\n\nYour previous offer (empty in round 1):\n{buyer_offer?}"
    ),
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                ),
                timeout=30.0,
            )
        ),
        submit_offer,
    ],
    before_tool_callback=_enforce_buyer_allowlist,
    output_key="buyer_offer",
    before_agent_callback=_init_round_state,
    after_agent_callback=_check_walk_away,
)

seller = LlmAgent(
    name="seller",
    model=MODEL,
    instruction=(
        "You ARE the listing agent in a LIVE negotiation — not an assistant "
        "waiting on anyone. You represent the seller of 742 Evergreen Terrace, "
        "Austin, TX 78701 (listed at $485,000).\n\n"
        "PROPERTY HIGHLIGHTS:\n"
        "  • Kitchen renovated 2023 ($45k), new roof 2022 ($18k), HVAC 2021 ($12k)\n"
        "  • Total upgrades: $75,000+\n"
        "  • Austin ISD (rated 8/10), zero HOA fees\n\n"
        "EACH ROUND you MUST, in order:\n"
        "1. Call your MCP tools (market price, inventory, minimum acceptable price).\n"
        "2. Decide FIRST: if the buyer's offer is AT or ABOVE your minimum acceptable "
        "price, you MUST ACCEPT it this round — do NOT keep countering to squeeze out "
        "more. Only COUNTER when the offer is STRICTLY BELOW your minimum, starting at "
        "$477,000 and dropping $5k–$8k per round toward (but never below) your minimum "
        "from get_minimum_acceptable_price.\n"
        "3. Call submit_decision(action='ACCEPT' or 'COUNTER', price=<int>). "
        "This is REQUIRED every single round — the negotiation cannot proceed without it. "
        "submit_decision enforces your minimum in code: if it records a different "
        "decision than you sent (see its 'note'), your reply MUST match what was "
        "recorded.\n\n"
        "The buyer's recorded offer this round (blank if it didn't record one): "
        "{buyer_offer_price?}\n"
        "Full buyer message:\n{buyer_offer}\n\n"
        "Then reply with ONE short paragraph justifying your decision, emphasizing "
        "the $75,000 in upgrades. Begin the paragraph with the literal prefix "
        "'SELLER: '. Output ONLY that single 'SELLER: ...' paragraph — no preamble, "
        "no step-by-step thinking, no 'submitting decision' narration.\n\n"
        "CONFIDENTIAL — the buyer must NEVER learn these, so never state them in your "
        "reply: your minimum acceptable price / floor, your ideal price, the fact that "
        "you have a floor, or any output from get_minimum_acceptable_price. Justify your "
        "counter only with upgrades and market conditions — never with your floor.\n\n"
        "Do NOT write meta commentary such as "
        "'we will wait for the buyer' or reminders/checklists — you ARE negotiating now."
    ),
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                ),
                timeout=30.0,
            )
        ),
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_INVENTORY_SERVER],
                ),
                timeout=30.0,
            )
        ),
        submit_decision,
    ],
    before_tool_callback=_enforce_seller_allowlist,
    after_tool_callback=_remember_seller_floor,
    output_key="seller_response",
    before_agent_callback=_skip_if_walked_away,
    after_agent_callback=_check_agreement,
)

negotiation_round = SequentialAgent(
    name="round",
    sub_agents=[buyer, seller],
)

root_agent = LoopAgent(
    name="negotiation",
    description="Multi-round buyer ↔ seller negotiation for 742 Evergreen Terrace.",
    sub_agents=[negotiation_round],
    max_iterations=5,
)
