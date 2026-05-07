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
    adk web m3_adk_multiagents/negotiation_agents/
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

import os

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m2_mcp" / "inventory_server.py")

# --- Tool allowlists (information asymmetry) ---

_BUYER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_property_tax_estimate",
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


# --- Decision tool (structured signal, not text parsing) ---


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
    return {"recorded": action_upper, "price": price}


# --- Callbacks ---


def _check_agreement(callback_context: CallbackContext):
    """After the seller responds, check the structured decision. Escalate on ACCEPT."""
    decision = callback_context.state.get("seller_decision")
    if isinstance(decision, dict) and decision.get("action") == "ACCEPT":
        callback_context.actions.escalate = True
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
        "You are an expert real estate buyer agent representing a client "
        "purchasing 742 Evergreen Terrace, Austin, TX 78701 (listed at $485,000).\n\n"
        "YOUR CLIENT'S CONSTRAINTS:\n"
        "- Maximum budget: $460,000 (NEVER offer above this)\n"
        "- Target acquisition price: $445,000–$455,000\n"
        "- Pre-approved for financing, can close in 30–45 days\n\n"
        "STRATEGY:\n"
        "- Call your MCP pricing tools BEFORE every offer to get market data\n"
        "- Round 1: offer ~12%% below asking (~$425,000)\n"
        "- Each subsequent round: increase by 2–4%%\n"
        "- If the seller has responded, read {seller_response} and adjust.\n"
        "- Walk away if seller won't go below $460,000\n\n"
        "Always justify your offers with data from your tools.\n"
        "Write your offer as a dollar amount with brief justification."
    ),
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                )
            )
        )
    ],
    before_tool_callback=_enforce_buyer_allowlist,
    output_key="buyer_offer",
    before_agent_callback=_init_round_state,
)

seller = LlmAgent(
    name="seller",
    model=MODEL,
    instruction=(
        "You are an expert listing agent for 742 Evergreen Terrace, "
        "Austin, TX 78701 (listed at $485,000).\n\n"
        "PROPERTY HIGHLIGHTS:\n"
        "  • Kitchen renovated 2023 ($45k), new roof 2022 ($18k), HVAC 2021 ($12k)\n"
        "  • Total upgrades: $75,000+\n"
        "  • Austin ISD (rated 8/10), zero HOA fees\n\n"
        "STRATEGY:\n"
        "- Call your MCP tools BEFORE every response (market price, inventory, floor price)\n"
        "- Start counter at $477,000, drop $5k–$8k per round only\n"
        "- NEVER go below your minimum (from get_minimum_acceptable_price tool)\n"
        "- If buyer offers at or above your minimum, accept immediately\n"
        "- Emphasize $75,000 in upgrades to justify premium pricing\n\n"
        "Read {buyer_offer}.\n"
        "IMPORTANT: After writing your response, you MUST call the submit_decision "
        "tool with action='ACCEPT' or action='COUNTER' and the price. "
        "This is required — the negotiation cannot proceed without it."
    ),
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                )
            )
        ),
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_INVENTORY_SERVER],
                )
            )
        ),
        submit_decision,
    ],
    before_tool_callback=_enforce_seller_allowlist,
    output_key="seller_response",
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
