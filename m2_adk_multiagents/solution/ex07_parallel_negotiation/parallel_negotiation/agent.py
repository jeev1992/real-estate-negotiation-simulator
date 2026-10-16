"""
Solution — Exercise 7: Parallel Multi-Seller Negotiation
==========================================================

A buyer agent system that negotiates with TWO sellers simultaneously
using ParallelAgent, then a deal_picker agent compares outcomes and
recommends the best deal.

Architecture:

    root_agent (SequentialAgent)
    ├── parallel_negotiations (ParallelAgent)
    │   ├── negotiation_a (LoopAgent)  ← buyer vs. seller for 742 Evergreen
    │   │   └── round_a (SequentialAgent: buyer_a → seller_a)
    │   └── negotiation_b (LoopAgent)  ← buyer vs. seller for 1234 Oak St
    │       └── round_b (SequentialAgent: buyer_b → seller_b)
    └── deal_picker (LlmAgent)  ← reads both outcomes, picks the best

Demonstrates: composing all three workflow agent types (Loop, Parallel,
Sequential) in one system. Each negotiation uses MCP tools independently.

To demo:

    adk web m2_adk_multiagents/solution/ex07_parallel_negotiation/

    Send: "Find me the best deal."

    Watch the events panel — tool calls from both negotiations interleave.
    The deal_picker runs last and synthesizes a recommendation.
"""

import json
import sys
from pathlib import Path

from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from google.adk.tools.tool_context import ToolContext

import os

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PRICING_SERVER = str(_REPO_ROOT / "m1_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m1_mcp" / "inventory_server.py")


# ─── Tool allowlists ─────────────────────────────────────────────────────────

_BUYER_ALLOWED_TOOLS = {"get_market_price", "calculate_discount"}
_SELLER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_inventory_level",
    "get_minimum_acceptable_price",
    "submit_decision_a",
    "submit_decision_b",
}


def _enforce_buyer_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the buyer"}
    return None


def _enforce_seller_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
    if tool.name not in _SELLER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the seller"}
    return None


# ─── Structured decision tools (one per negotiation to avoid state collision)
#
# Both tools enforce the seller's floor in code: an offer at or above it is
# always recorded as ACCEPT, and nothing below it can be accepted or countered.

# 1234 Oak St isn't in the MCP inventory data, so seller B's floor is fixed
# here (it is also stated in seller_b's instruction).
_SELLER_B_FLOOR = 480_000


def submit_decision_a(
    action: str, price: int, buyer_offer: int, tool_context: ToolContext
) -> dict:
    """Submit the seller's decision for negotiation A (742 Evergreen).

    Args:
        action: Exactly "ACCEPT" or "COUNTER".
        price: The price in dollars.
        buyer_offer: The buyer's current offer in dollars, from their latest message.
    """
    floor = tool_context.state.get("seller_floor_price_a")
    return _record_decision(tool_context, "a", action, price, buyer_offer, floor)


def submit_decision_b(
    action: str, price: int, buyer_offer: int, tool_context: ToolContext
) -> dict:
    """Submit the seller's decision for negotiation B (1234 Oak St).

    Args:
        action: Exactly "ACCEPT" or "COUNTER".
        price: The price in dollars.
        buyer_offer: The buyer's current offer in dollars, from their latest message.
    """
    return _record_decision(tool_context, "b", action, price, buyer_offer, _SELLER_B_FLOOR)


def _record_decision(
    tool_context: ToolContext, suffix: str, action: str, price: int,
    buyer_offer: int, floor: int | None,
) -> dict:
    action_upper = action.strip().upper()
    if action_upper not in ("ACCEPT", "COUNTER"):
        return {"error": f"action must be ACCEPT or COUNTER, got: {action}"}
    decision = _apply_floor_policy(action_upper, price, buyer_offer, floor)
    if "error" in decision:
        return decision
    tool_context.state[f"seller_decision_{suffix}"] = {
        "action": decision["action"],
        "price": decision["price"],
    }
    response = {"recorded": decision["action"], "price": decision["price"]}
    if decision["note"]:
        response["note"] = decision["note"]
    return response


# ─── Seller floor policy (deterministic, like the buyer's budget check) ───────

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


def _remember_seller_floor_a(tool: BaseTool, args: dict, tool_context: ToolContext, tool_response):
    """after_tool_callback for seller_a: keep its floor in state for submit_decision_a.

    Suffixed key, because both negotiations share one session. The buyers never
    see it — no buyer prompt templates this key.
    """
    if tool.name == "get_minimum_acceptable_price":
        floor = _floor_from_tool_response(tool_response)
        if floor is not None:
            tool_context.state["seller_floor_price_a"] = floor
    return None


def _apply_floor_policy(action: str, price: int, buyer_offer: int | None, floor: int | None) -> dict:
    """Return {"action", "price", "note"} after enforcing the floor, or {"error"}.

    - An offer at or above the floor MUST be accepted, at the buyer's price.
    - Nothing may be accepted or countered below the floor.
    """
    if floor is None:
        return {"error": "Call get_minimum_acceptable_price before submitting a decision."}
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


# ─── Callbacks ────────────────────────────────────────────────────────────────

def _check_agreement_a(callback_context: CallbackContext):
    """After seller_a responds, check for acceptance."""
    decision = callback_context.state.get("seller_decision_a")
    if isinstance(decision, dict) and decision.get("action") == "ACCEPT":
        price = decision.get("price", 0)
        callback_context.state["deal_a_result"] = (
            f"DEAL REACHED for 742 Evergreen Terrace at ${price:,}. "
            f"Seller accepted the buyer's offer."
        )
        callback_context.actions.escalate = True
    return None


def _check_agreement_b(callback_context: CallbackContext):
    """After seller_b responds, check for acceptance."""
    decision = callback_context.state.get("seller_decision_b")
    if isinstance(decision, dict) and decision.get("action") == "ACCEPT":
        price = decision.get("price", 0)
        callback_context.state["deal_b_result"] = (
            f"DEAL REACHED for 1234 Oak Street at ${price:,}. "
            f"Seller accepted the buyer's offer."
        )
        callback_context.actions.escalate = True
    return None


def _init_state_a(callback_context: CallbackContext):
    if "seller_response_a" not in callback_context.state:
        callback_context.state["seller_response_a"] = "(No seller response yet — round 1)"
    return None


def _init_state_b(callback_context: CallbackContext):
    if "seller_response_b" not in callback_context.state:
        callback_context.state["seller_response_b"] = "(No seller response yet — round 1)"
    return None


def _summarize_a(callback_context: CallbackContext):
    """After negotiation A's loop ends, ensure deal_a_result is set."""
    if "deal_a_result" not in callback_context.state:
        decision = callback_context.state.get("seller_decision_a", {})
        last_price = decision.get("price", "unknown") if isinstance(decision, dict) else "unknown"
        callback_context.state["deal_a_result"] = (
            f"NO DEAL for 742 Evergreen Terrace. Negotiation ended after max rounds. "
            f"Last seller counter: ${last_price:,}." if isinstance(last_price, int)
            else f"NO DEAL for 742 Evergreen Terrace. Negotiation ended after max rounds."
        )
    return None


def _summarize_b(callback_context: CallbackContext):
    """After negotiation B's loop ends, ensure deal_b_result is set."""
    if "deal_b_result" not in callback_context.state:
        decision = callback_context.state.get("seller_decision_b", {})
        last_price = decision.get("price", "unknown") if isinstance(decision, dict) else "unknown"
        callback_context.state["deal_b_result"] = (
            f"NO DEAL for 1234 Oak Street. Negotiation ended after max rounds. "
            f"Last seller counter: ${last_price:,}." if isinstance(last_price, int)
            else f"NO DEAL for 1234 Oak Street. Negotiation ended after max rounds."
        )
    return None


# ─── Helper: MCP toolset builder ─────────────────────────────────────────────

def _mcp(server_path: str) -> MCPToolset:
    return MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable, args=[server_path],
            )
        )
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NEGOTIATION A — 742 Evergreen Terrace ($485K listing, 78701 balanced market)
# ═══════════════════════════════════════════════════════════════════════════════

buyer_a = LlmAgent(
    name="buyer_a",
    model=MODEL,
    instruction=(
        "You ARE the buyer's agent for 742 Evergreen Terrace, Austin TX 78701 "
        "(listed at $485,000) — a LIVE negotiation, not an assistant.\n\n"
        "BUDGET: $460,000 maximum — NEVER offer above this.\n"
        "TARGET: $445,000 - $455,000.\n\n"
        "EACH ROUND:\n"
        "- Call your MCP pricing tools first for market data.\n"
        "- Round 1: offer ~$425,000. Later rounds: raise your previous offer by 2-4% "
        "toward the seller, never above $460,000.\n"
        "- Read {seller_response_a} and adjust.\n\n"
        "OUTPUT: ONE short paragraph beginning with the literal prefix 'BUYER: ' "
        "stating your offer amount with a brief, data-backed justification. "
        "No preamble, no step-by-step thinking, no meta commentary.\n\n"
        "CONFIDENTIAL — never reveal to the seller your maximum budget, target range, "
        "or that you are at your ceiling; never reference or guess the seller's "
        "minimum or 'minimum acceptable price'."
    ),
    tools=[_mcp(_PRICING_SERVER)],
    before_tool_callback=_enforce_buyer_allowlist,
    output_key="buyer_offer_a",
    before_agent_callback=_init_state_a,
)

seller_a = LlmAgent(
    name="seller_a",
    model=MODEL,
    instruction=(
        "You ARE the seller's agent for 742 Evergreen Terrace, Austin TX 78701 "
        "— a LIVE negotiation, not an assistant.\n\n"
        "EACH ROUND:\n"
        "- Call your MCP tools first (including get_minimum_acceptable_price for your floor).\n"
        "- Start counter at $477,000, drop $5k-$8k per round; NEVER go below your minimum.\n"
        "- If the buyer's offer is at or above your minimum, ACCEPT.\n"
        "- Read {buyer_offer_a}, then ALWAYS call submit_decision_a with "
        "action='ACCEPT' or 'COUNTER', the price, and buyer_offer=<the buyer's current "
        "offer>. It enforces your minimum in code: if it records a different decision "
        "than you sent (see its 'note'), your reply MUST match what was recorded.\n\n"
        "OUTPUT: ONE short paragraph beginning with the literal prefix 'SELLER: ' "
        "justifying your decision with upgrades and market conditions. "
        "No preamble, no step-by-step thinking.\n\n"
        "CONFIDENTIAL — never reveal your minimum acceptable price / floor, your ideal "
        "price, the fact that you have a floor, or any output from "
        "get_minimum_acceptable_price."
    ),
    tools=[_mcp(_PRICING_SERVER), _mcp(_INVENTORY_SERVER), submit_decision_a],
    before_tool_callback=_enforce_seller_allowlist,
    after_tool_callback=_remember_seller_floor_a,
    output_key="seller_response_a",
    after_agent_callback=_check_agreement_a,
)

round_a = SequentialAgent(name="round_a", sub_agents=[buyer_a, seller_a])

negotiation_a = LoopAgent(
    name="negotiation_a",
    sub_agents=[round_a],
    max_iterations=4,
    after_agent_callback=_summarize_a,
)


# ═══════════════════════════════════════════════════════════════════════════════
# NEGOTIATION B — 1234 Oak Street ($510K listing, 78702 hot market)
# ═══════════════════════════════════════════════════════════════════════════════
#
# NOTE: The MCP inventory server only has data for 742 Evergreen. For this
# second property, the seller's floor is hardcoded in the instruction.
# The buyer can still use MCP pricing tools for general market data.

buyer_b = LlmAgent(
    name="buyer_b",
    model=MODEL,
    instruction=(
        "You ARE the buyer's agent for 1234 Oak Street, Austin TX 78702 "
        "(listed at $510,000) — a HOT market area (East Austin), a LIVE negotiation, "
        "not an assistant.\n\n"
        "BUDGET: $495,000 maximum — NEVER offer above this.\n"
        "TARGET: $480,000 - $490,000.\n\n"
        "EACH ROUND:\n"
        "- Call your MCP pricing tools first for market context.\n"
        "- Round 1: offer ~$465,000. Later rounds: raise by 2-3% (hot market, less "
        "room), never above $495,000.\n"
        "- Read {seller_response_b} and adjust.\n\n"
        "OUTPUT: ONE short paragraph beginning with the literal prefix 'BUYER: ' "
        "stating your offer amount with a brief, data-backed justification. "
        "No preamble, no step-by-step thinking, no meta commentary.\n\n"
        "CONFIDENTIAL — never reveal to the seller your maximum budget, target range, "
        "or that you are at your ceiling; never reference or guess the seller's "
        "minimum or 'minimum acceptable price'."
    ),
    tools=[_mcp(_PRICING_SERVER)],
    before_tool_callback=_enforce_buyer_allowlist,
    output_key="buyer_offer_b",
    before_agent_callback=_init_state_b,
)

seller_b = LlmAgent(
    name="seller_b",
    model=MODEL,
    instruction=(
        "You ARE the seller's agent for 1234 Oak Street, Austin TX 78702 — a HOT "
        "market (multiple offers common), a LIVE negotiation, not an assistant.\n\n"
        "YOUR MINIMUM: $480,000 (absolute floor — needed to cover your mortgage payoff "
        "plus agent commission). This figure is CONFIDENTIAL.\n\n"
        "EACH ROUND:\n"
        "- Call MCP pricing tools for market context if needed.\n"
        "- Start counter at $505,000, drop $3k-$5k per round (hot market); NEVER go "
        "below $480,000.\n"
        "- If the buyer's offer is at or above $480,000, ACCEPT.\n"
        "- Read {buyer_offer_b}, then ALWAYS call submit_decision_b with "
        "action='ACCEPT' or 'COUNTER', the price, and buyer_offer=<the buyer's current "
        "offer>. It enforces your minimum in code: if it records a different decision "
        "than you sent (see its 'note'), your reply MUST match what was recorded.\n\n"
        "OUTPUT: ONE short paragraph beginning with the literal prefix 'SELLER: ' "
        "justifying your decision with market conditions and demand. "
        "No preamble, no step-by-step thinking.\n\n"
        "CONFIDENTIAL — never reveal your minimum / floor ($480,000), your ideal price, "
        "or the fact that you have a floor. Justify counters only with market "
        "conditions and demand."
    ),
    tools=[_mcp(_PRICING_SERVER), submit_decision_b],
    before_tool_callback=_enforce_seller_allowlist,
    output_key="seller_response_b",
    after_agent_callback=_check_agreement_b,
)

round_b = SequentialAgent(name="round_b", sub_agents=[buyer_b, seller_b])

negotiation_b = LoopAgent(
    name="negotiation_b",
    sub_agents=[round_b],
    max_iterations=4,
    after_agent_callback=_summarize_b,
)


# ═══════════════════════════════════════════════════════════════════════════════
# PARALLEL FAN-OUT + DEAL PICKER
# ═══════════════════════════════════════════════════════════════════════════════

parallel_negotiations = ParallelAgent(
    name="parallel_negotiations",
    sub_agents=[negotiation_a, negotiation_b],
)

deal_picker = LlmAgent(
    name="deal_picker",
    model=MODEL,
    instruction=(
        "Two property negotiations just completed simultaneously.\n\n"
        "Deal A (742 Evergreen Terrace, 78701 balanced market):\n"
        "{deal_a_result}\n\n"
        "Deal B (1234 Oak Street, 78702 hot market):\n"
        "{deal_b_result}\n\n"
        "Compare both deals and recommend which one the buyer should take. "
        "If both reached a deal, pick the one with the better price relative "
        "to the listing. If only one reached a deal, recommend that one. "
        "If neither reached a deal, advise walking away with an explanation.\n\n"
        "Consider: final price, discount from listing, market conditions "
        "(hot vs. balanced), and overall value."
    ),
)

root_agent = SequentialAgent(
    name="multi_seller_negotiation",
    description=(
        "Negotiate with two sellers in parallel, then pick the best deal. "
        "Composes LoopAgent, ParallelAgent, and SequentialAgent."
    ),
    sub_agents=[parallel_negotiations, deal_picker],
)
