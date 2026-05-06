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

    adk web m3_adk_multiagents/solution/ex07_parallel_negotiation/

    Send: "Find me the best deal."

    Watch the events panel — tool calls from both negotiations interleave.
    The deal_picker runs last and synthesizes a recommendation.
"""

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

MODEL = "openai/gpt-4o"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m2_mcp" / "inventory_server.py")


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

def submit_decision_a(action: str, price: int, tool_context: ToolContext) -> dict:
    """Submit the seller's decision for negotiation A (742 Evergreen).

    Args:
        action: Exactly "ACCEPT" or "COUNTER".
        price: The price in dollars.
    """
    action_upper = action.strip().upper()
    if action_upper not in ("ACCEPT", "COUNTER"):
        return {"error": f"action must be ACCEPT or COUNTER, got: {action}"}
    tool_context.state["seller_decision_a"] = {"action": action_upper, "price": price}
    return {"recorded": action_upper, "price": price}


def submit_decision_b(action: str, price: int, tool_context: ToolContext) -> dict:
    """Submit the seller's decision for negotiation B (1234 Oak St).

    Args:
        action: Exactly "ACCEPT" or "COUNTER".
        price: The price in dollars.
    """
    action_upper = action.strip().upper()
    if action_upper not in ("ACCEPT", "COUNTER"):
        return {"error": f"action must be ACCEPT or COUNTER, got: {action}"}
    tool_context.state["seller_decision_b"] = {"action": action_upper, "price": price}
    return {"recorded": action_upper, "price": price}


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
        "You are a buyer agent for 742 Evergreen Terrace, Austin TX 78701 "
        "(listed at $485,000).\n\n"
        "BUDGET: $460,000 maximum.\n"
        "TARGET: $445,000 - $455,000.\n\n"
        "STRATEGY:\n"
        "- Call MCP pricing tools BEFORE every offer\n"
        "- Round 1: offer ~$425,000\n"
        "- Each subsequent round: increase by 2-4%\n"
        "- Read {seller_response_a} and adjust\n\n"
        "Write your offer as a dollar amount with brief justification."
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
        "You are the seller agent for 742 Evergreen Terrace, Austin TX 78701.\n\n"
        "STRATEGY:\n"
        "- Call your MCP tools BEFORE every response\n"
        "- Start counter at $477,000, drop $5k-$8k per round\n"
        "- NEVER go below your minimum (from get_minimum_acceptable_price)\n"
        "- If buyer offers at or above your minimum, ACCEPT immediately\n\n"
        "Read {buyer_offer_a}.\n"
        "IMPORTANT: Call submit_decision_a with action='ACCEPT' or 'COUNTER' and price."
    ),
    tools=[_mcp(_PRICING_SERVER), _mcp(_INVENTORY_SERVER), submit_decision_a],
    before_tool_callback=_enforce_seller_allowlist,
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
        "You are a buyer agent for 1234 Oak Street, Austin TX 78702 "
        "(listed at $510,000). This is a HOT market area (East Austin).\n\n"
        "BUDGET: $495,000 maximum.\n"
        "TARGET: $480,000 - $490,000.\n\n"
        "STRATEGY:\n"
        "- Call MCP pricing tools BEFORE every offer for market context\n"
        "- Round 1: offer ~$465,000\n"
        "- Each subsequent round: increase by 2-3% (hot market, less room)\n"
        "- Read {seller_response_b} and adjust\n\n"
        "Write your offer as a dollar amount with brief justification."
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
        "You are the seller agent for 1234 Oak Street, Austin TX 78702.\n"
        "This is a HOT market — multiple offers are common.\n\n"
        "YOUR MINIMUM: $480,000 (absolute floor — you need this to cover "
        "your mortgage payoff plus agent commission).\n\n"
        "STRATEGY:\n"
        "- Call MCP pricing tools for market context if needed\n"
        "- Start counter at $505,000, drop $3k-$5k per round (hot market)\n"
        "- NEVER go below $480,000\n"
        "- If buyer offers at or above $480,000, ACCEPT immediately\n\n"
        "Read {buyer_offer_b}.\n"
        "IMPORTANT: Call submit_decision_b with action='ACCEPT' or 'COUNTER' and price."
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
