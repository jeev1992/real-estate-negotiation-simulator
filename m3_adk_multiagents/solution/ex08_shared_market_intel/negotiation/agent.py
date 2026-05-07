"""
Solution — Exercise 8: Shared market intelligence via app state
=================================================================

Negotiation orchestrator that uses `app:`-scoped state as a shared memory
layer. Every pricing tool call gets cached in `app:price_cache`, building
a growing pool of market intelligence that ANY agent, session, or user
can reference.

Also seeds `app:recent_comps` with comparable sales that both buyer and
seller reference in their instructions — grounding both sides in the
same market data.

ADK CONCEPTS:
  - `app:` state prefix: global, shared across all users and sessions
  - `after_tool_callback`: intercepts tool results to cache them
  - `before_agent_callback`: seeds initial data on first run
  - Three-tier state: session (working) / user: (personal) / app: (shared)

To demo:

    adk web m3_adk_multiagents/solution/ex08_shared_market_intel/

    Pick `negotiation`, send: "Start the negotiation for 742 Evergreen Terrace."

    Watch the terminal for [cache] log lines.
    Check State tab: app:price_cache, app:recent_comps, app:total_price_lookups

    Click "New Session" and run again — app: state persists, counter keeps growing.
"""

import sys
from datetime import datetime, timezone
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

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m2_mcp" / "inventory_server.py")

# ─── Tool allowlists ─────────────────────────────────────────────────────────

_BUYER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_property_tax_estimate",
}

_SELLER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_inventory_level",
    "get_minimum_acceptable_price",
    "submit_decision",
}

_PRICING_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_property_tax_estimate",
}


def _enforce_buyer_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the buyer"}
    return None


def _enforce_seller_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
    if tool.name not in _SELLER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the seller"}
    return None


# ─── submit_decision (unchanged) ──────────────────────────────────────────────

def submit_decision(action: str, price: int, tool_context: ToolContext) -> dict:
    """Submit the seller's decision for this round.

    Args:
        action: Exactly "ACCEPT" or "COUNTER".
        price: The price in dollars.
    """
    action_upper = action.strip().upper()
    if action_upper not in ("ACCEPT", "COUNTER"):
        return {"error": f"action must be ACCEPT or COUNTER, got: {action}"}
    tool_context.state["seller_decision"] = {"action": action_upper, "price": price}
    return {"recorded": action_upper, "price": price}


# ─── App-state callbacks (the heart of this exercise) ─────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _cache_price_lookup(
    tool: BaseTool, args: dict, tool_context: ToolContext, tool_response
):
    """after_tool_callback: cache pricing tool results in app: state.

    Fires after ANY tool call. Only caches results from pricing tools.
    Builds a shared price cache that any agent/session/user can read.
    """
    if tool.name not in _PRICING_TOOLS:
        return None

    # Build cache key from the tool name + arguments
    cache_key = f"{tool.name}"
    if isinstance(args, dict):
        # Use property_id if available, else use all args
        prop_id = args.get("property_id", args.get("address", "unknown"))
        cache_key = f"{tool.name}:{prop_id}"

    # Read existing cache
    price_cache = dict(tool_context.state.get("app:price_cache", {}))

    # Update cache entry
    price_cache[cache_key] = {
        "result": tool_response if isinstance(tool_response, (dict, str, int, float)) else str(tool_response),
        "args": args,
        "last_lookup": _ts(),
        "lookup_count": price_cache.get(cache_key, {}).get("lookup_count", 0) + 1,
    }

    tool_context.state["app:price_cache"] = price_cache

    # Global counter
    total = tool_context.state.get("app:total_price_lookups", 0) + 1
    tool_context.state["app:total_price_lookups"] = total

    print(f"[cache] {_ts()} Cached {cache_key} (lookup #{total})")
    return None  # don't modify the result


def _seed_comps(callback_context: CallbackContext):
    """before_agent_callback on the LoopAgent: seed comparable sales if not
    already present. Since this uses app: state, it only seeds once —
    subsequent sessions and users all see the same comps."""
    state = callback_context.state

    if "app:recent_comps" not in state:
        state["app:recent_comps"] = [
            {"address": "800 Maple Dr, Austin TX", "sold_price": 452000, "date": "2024-11", "sqft": 2100},
            {"address": "315 Cedar Ln, Austin TX", "sold_price": 471000, "date": "2024-12", "sqft": 2350},
            {"address": "1020 Birch Ave, Austin TX", "sold_price": 438000, "date": "2025-01", "sqft": 1950},
        ]
        print(f"[cache] {_ts()} Seeded app:recent_comps with 3 comparable sales")

    if "app:price_cache" not in state:
        state["app:price_cache"] = {}
    if "app:total_price_lookups" not in state:
        state["app:total_price_lookups"] = 0

    return None


# ─── Acceptance check (unchanged from canonical) ──────────────────────────────

def _check_agreement(callback_context: CallbackContext):
    decision = callback_context.state.get("seller_decision")
    if isinstance(decision, dict) and decision.get("action") == "ACCEPT":
        callback_context.actions.escalate = True
    return None


def _init_round_state(callback_context: CallbackContext):
    if "seller_response" not in callback_context.state:
        callback_context.state["seller_response"] = "(No seller response yet — this is round 1)"
    # Ensure app: state exists before buyer instruction reads {app:price_cache}
    if "app:recent_comps" not in callback_context.state:
        callback_context.state["app:recent_comps"] = []
    if "app:price_cache" not in callback_context.state:
        callback_context.state["app:price_cache"] = {}
    if "app:total_price_lookups" not in callback_context.state:
        callback_context.state["app:total_price_lookups"] = 0
    return None


# ─── The agents ───────────────────────────────────────────────────────────────

buyer = LlmAgent(
    name="buyer",
    model=MODEL,
    instruction=(
        "You are an expert real estate buyer agent representing a client "
        "purchasing 742 Evergreen Terrace, Austin, TX 78701 (listed at $485,000).\n\n"
        "YOUR CLIENT'S CONSTRAINTS:\n"
        "- Maximum budget: $460,000 (NEVER offer above this)\n"
        "- Target acquisition price: $445,000–$455,000\n\n"
        "COMPARABLE SALES (shared market data — same data the seller sees):\n"
        "{app:recent_comps}\n\n"
        "CACHED MARKET DATA:\n"
        "{app:price_cache}\n\n"
        "STRATEGY:\n"
        "- Reference the comparable sales above to justify your offers\n"
        "- Call your MCP pricing tools for additional market data\n"
        "- Read {seller_response} and adjust your offer accordingly\n"
        "- Round 1: offer ~12% below asking (~$425,000)\n"
        "- Each subsequent round: increase by 2–4%\n\n"
        "Always justify your offers with comps AND tool data."
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
    ],
    before_tool_callback=_enforce_buyer_allowlist,
    after_tool_callback=_cache_price_lookup,
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
        "  • Total upgrades: $75,000+\n\n"
        "COMPARABLE SALES (shared market data — same data the buyer sees):\n"
        "{app:recent_comps}\n\n"
        "STRATEGY:\n"
        "- Call your MCP tools for market data, inventory, and your floor price\n"
        "- Use comps AND your upgrades to justify pricing above comparable sales\n"
        "- Your upgrades add $75K+ value above raw comps\n"
        "- Start counter at $477,000, drop $5k–$8k per round only\n"
        "- NEVER go below your minimum (from get_minimum_acceptable_price)\n"
        "- If buyer offers at or above your minimum, accept immediately\n\n"
        "Read {buyer_offer}.\n"
        "IMPORTANT: After writing your response, you MUST call submit_decision "
        "with action='ACCEPT' or action='COUNTER' and the price."
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
    after_tool_callback=_cache_price_lookup,
    output_key="seller_response",
    after_agent_callback=_check_agreement,
)

negotiation_round = SequentialAgent(name="round", sub_agents=[buyer, seller])

root_agent = LoopAgent(
    name="negotiation",
    description="Multi-round negotiation with shared market intelligence via app: state.",
    sub_agents=[negotiation_round],
    max_iterations=5,
    before_agent_callback=_seed_comps,
)
