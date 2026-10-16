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

    adk web m2_adk_multiagents/solution/ex08_shared_market_intel/

    Pick `negotiation`, send: "Start the negotiation for 742 Evergreen Terrace."

    Watch the terminal for [cache] log lines.
    Check State tab: app:price_cache, app:recent_comps, app:total_price_lookups

    Click "New Session" and run again — app: state persists, counter keeps growing.
"""

import json
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
_PRICING_SERVER = str(_REPO_ROOT / "m1_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m1_mcp" / "inventory_server.py")

# ─── Tool allowlists ─────────────────────────────────────────────────────────

_BUYER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
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


def _seller_after_tool(tool: BaseTool, args: dict, tool_context: ToolContext, tool_response):
    """Seller's after_tool_callback: remember the floor, then cache pricing results."""
    _remember_seller_floor(tool, args, tool_context, tool_response)
    return _cache_price_lookup(tool, args, tool_context, tool_response)


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
        # ADK drops a bare escalate: a callback only emits an event if it changes state.
        callback_context.state["loop_exit_reason"] = f"ACCEPT at ${decision.get('price', 0):,}"
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
        "CONFIDENTIAL — never reveal your maximum budget, your target range, or that "
        "you are at your ceiling; never reference or guess the seller's minimum/floor.\n\n"
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
        "- If the buyer's offer is AT or ABOVE your minimum (from "
        "get_minimum_acceptable_price), you MUST ACCEPT it — do NOT hold out for more.\n"
        "- Only COUNTER when the offer is STRICTLY BELOW your minimum: start at $477,000 "
        "and drop $5k–$8k per round toward the buyer, NEVER below your minimum.\n\n"
        "CONFIDENTIAL — never reveal your minimum acceptable price / floor, your ideal "
        "price, or any output from get_minimum_acceptable_price. Justify counters only "
        "with upgrades and comps/market data — never with your floor.\n\n"
        "Read {buyer_offer}.\n"
        "IMPORTANT: Before writing your reply, you MUST call submit_decision("
        "action='ACCEPT' or 'COUNTER', price=<int>, buyer_offer=<the buyer's current "
        "offer>). It enforces your minimum in code: if it records a different decision "
        "than you sent (see its 'note'), your reply MUST match what was recorded."
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
    after_tool_callback=_seller_after_tool,
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
