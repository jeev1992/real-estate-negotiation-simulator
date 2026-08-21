"""
Negotiation Orchestrator — Idiomatic ADK
==========================================
LoopAgent wrapping a SequentialAgent (buyer → seller) to run multi-round
negotiation with real MCP tools. The buyer calls pricing tools before each
offer; the seller calls pricing + inventory tools (including the secret
floor price) before each counter.

Demonstrates: LoopAgent, SequentialAgent, MCPToolset, output_key state
passing, after_agent_callback with escalation, before_tool_callback
allowlists, information asymmetry.

Run with:
    adk web m2_adk_multiagents/negotiation_agents/
"""

import sys
from pathlib import Path

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
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
    "get_property_tax_estimate",
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
        return {
            "error": f"offer {price} exceeds the ${_BUYER_MAX_BUDGET} maximum budget"
        }
    tool_context.state["buyer_offer_price"] = price
    _append_history(tool_context, "buyer", "OFFER", price)
    return {"recorded": price}


def submit_decision(
    action: str, price: int, tool_context: ToolContext
) -> dict:
    """Submit the seller's final decision for this round.

    Args:
        action: Exactly "ACCEPT" or "COUNTER" — no other values.
        price: The price in dollars (e.g. 445000 or 477000).
    """
    action_upper = action.strip().upper()
    if action_upper not in ("ACCEPT", "COUNTER"):
        return {"error": f"action must be ACCEPT or COUNTER, got: {action}"}
    tool_context.state["seller_decision"] = {
        "action": action_upper,
        "price": price,
    }
    _append_history(tool_context, "seller", action_upper, price)
    return {"recorded": action_upper, "price": price}


# --- Callbacks ---


def _check_agreement(callback_context: CallbackContext):
    """After the seller responds, check the structured decision. Escalate on ACCEPT."""
    decision = callback_context.state.get("seller_decision")
    if isinstance(decision, dict) and decision.get("action") == "ACCEPT":
        callback_context.actions.escalate = True
    return None


def _check_walk_away(callback_context: CallbackContext):
    """After the buyer responds, end the negotiation if the buyer walked away."""
    if callback_context.state.get("buyer_walk_away"):
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
    """Ensure seller_response exists in state before round 1."""
    if "seller_response" not in callback_context.state:
        callback_context.state["seller_response"] = "(No seller response yet — this is round 1)"
    return None


buyer = LlmAgent(
    name="buyer",
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
    ),
    tools=[
        MCPToolset(
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
        "This is REQUIRED every single round — the negotiation cannot proceed without it.\n\n"
        "The buyer's current offer is ${buyer_offer_price?}.\n"
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
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                ),
                timeout=30.0,
            )
        ),
        MCPToolset(
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
