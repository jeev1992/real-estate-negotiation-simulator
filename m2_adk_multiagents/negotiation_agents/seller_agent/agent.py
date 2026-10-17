"""
Seller Agent — Idiomatic ADK
===============================
Declarative LlmAgent with dual McpToolsets (pricing + inventory).
Demonstrates: multiple McpToolsets, information asymmetry via allowlist,
and a decision tool that enforces the seller's floor in code.

The seller has access to get_minimum_acceptable_price (from the inventory
server) — a tool the buyer never sees. An after_tool_callback remembers the
floor it returns, and submit_decision uses it: an offer at or above the floor
is always recorded as ACCEPT, and nothing below it can be accepted.

Run with:
    adk web m2_adk_multiagents/negotiation_agents/
    adk web --a2a m2_adk_multiagents/negotiation_agents/
"""

import os
import json
import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from google.adk.tools.tool_context import ToolContext

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRICING_SERVER = str(_REPO_ROOT / "m1_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m1_mcp" / "inventory_server.py")

# Seller has access to inventory tools (including private floor price).
_SELLER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_inventory_level",
    "get_minimum_acceptable_price",  # seller-only
    "submit_decision",  # structured decision, floor enforced in code
}


def _enforce_seller_allowlist(
    tool: BaseTool, args: dict, tool_context: ToolContext
):
    """Block tools not on the seller's allowlist."""
    if tool.name not in _SELLER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the seller"}
    return None


# ─── submit_decision (enforces the seller's floor in code) ────────────────────

def submit_decision(
    action: str, price: int, buyer_offer: int, tool_context: ToolContext
) -> dict:
    """Submit the seller's decision for this round.

    The seller's minimum is enforced here: an offer at or above it is always
    recorded as ACCEPT, and nothing below it can be accepted or countered.

    Args:
        action: Exactly "ACCEPT" or "COUNTER".
        price: The price in dollars.
        buyer_offer: The buyer's current offer in dollars, from their latest message.
    """
    action_upper = action.strip().upper()
    if action_upper not in ("ACCEPT", "COUNTER"):
        return {"error": f"action must be ACCEPT or COUNTER, got: {action}"}
    decision = _apply_floor_policy(
        action_upper, price, buyer_offer, tool_context.state.get("seller_floor_price")
    )
    if "error" in decision:
        return decision
    tool_context.state["seller_decision"] = {
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


def _remember_seller_floor(tool: BaseTool, args: dict, tool_context: ToolContext, tool_response):
    """after_tool_callback: keep the floor in state so submit_decision can enforce it.

    The buyer never sees it — no buyer prompt templates this key.
    """
    if tool.name == "get_minimum_acceptable_price":
        floor = _floor_from_tool_response(tool_response)
        if floor is not None:
            tool_context.state["seller_floor_price"] = floor
    return None


def _apply_floor_policy(action: str, price: int, buyer_offer: int | None, floor: int | None) -> dict:
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

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

root_agent = LlmAgent(
    name="seller_agent",
    model=MODEL,
    description="Real estate seller agent for 742 Evergreen Terrace, Austin TX.",
    instruction=(
        "You ARE the listing agent in a LIVE negotiation — not an assistant waiting "
        "on anyone. You represent the seller of 742 Evergreen Terrace, "
        "Austin, TX 78701 (listed at $485,000).\n\n"
        "PROPERTY HIGHLIGHTS:\n"
        "  • Kitchen renovated 2023 ($45k), new roof 2022 ($18k), HVAC 2021 ($12k)\n"
        "  • Total upgrades: $75,000+\n"
        "  • Austin ISD (rated 8/10), zero HOA fees\n\n"
        "EACH ROUND:\n"
        "1. Call your MCP tools first (market price, inventory, minimum acceptable price).\n"
        "2. Decide: if the buyer's offer is AT or ABOVE your minimum, ACCEPT it. "
        "Otherwise COUNTER — start at $477,000 and drop only $5k–$8k per round, "
        "NEVER below your minimum from get_minimum_acceptable_price.\n"
        "3. ALWAYS call submit_decision(action='ACCEPT' or 'COUNTER', price=<int>, "
        "buyer_offer=<the buyer's offer in dollars>) — every round, for counters too, "
        "BEFORE you write your reply. It enforces your minimum in code: "
        "if it records a different decision than you sent (see its 'note'), your reply "
        "MUST follow what was recorded.\n\n"
        "OUTPUT FORMAT: reply with ONE short paragraph beginning with the literal "
        "prefix 'SELLER: '. The paragraph MUST contain exactly ONE of the words "
        "ACCEPT or COUNTER (never both) — the decision submit_decision recorded — "
        "followed by your price and a brief justification emphasizing the $75,000 in "
        "upgrades. No preamble, no step-by-step thinking.\n\n"
        "CONFIDENTIAL — never reveal to the buyer: your minimum acceptable price / "
        "floor, your ideal price, the fact that you have a floor, or any output from "
        "get_minimum_acceptable_price. Justify your counter only with upgrades and "
        "market conditions — never with your floor."
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
)
