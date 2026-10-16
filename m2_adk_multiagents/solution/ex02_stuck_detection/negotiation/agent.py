"""
Solution — Exercise 2: Stuck-detection orchestrator
=====================================================

Negotiation orchestrator that exits early when the negotiation stalls.

Three exit conditions, in priority order:
  1. Seller submits action='ACCEPT'  →  deal reached, escalate
  2. Three consecutive rounds with <$1,000 price movement  →  stalled, escalate
  3. max_iterations=5 reached         →  hard cap

The stall check fires AFTER the seller responds, AFTER acceptance is checked.
So a healthy negotiation that closes at round 3 still exits via ACCEPT,
not via the stall check.

To demo:

    # 1. Healthy run (default — buyer max $460K, seller floor $445K, ZOPA exists):
    adk web m2_adk_multiagents/solution/ex02_stuck_detection/
    Pick `negotiation` and send: "Start the negotiation."
    Expect: ACCEPT around round 2-3.

    # 2. Stalled run — set STALL_DEMO=true to drop buyer budget to $440K:
    #    $env:STALL_DEMO = "true"
    #    adk web m2_adk_multiagents/solution/ex02_stuck_detection/
    #    Expect: stall detected at round 3-4, NOT round 5.
"""

import os
import json
import re
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

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PRICING_SERVER = str(_REPO_ROOT / "m1_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m1_mcp" / "inventory_server.py")

# Stall-detection parameters — see the reflection in walkthrough.md for
# how you would calibrate these in production.
STALL_WINDOW = 2        # number of consecutive rounds to inspect
STALL_THRESHOLD = 5_000 # dollars; if all prices move less than this each round, we call it stalled


# ─── Tool allowlists (unchanged from the canonical orchestrator) ──────────────

_BUYER_ALLOWED_TOOLS = {"get_market_price", "calculate_discount"}
_SELLER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_inventory_level",
    "get_minimum_acceptable_price",
    "submit_decision",
}


def _enforce_buyer_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the buyer"}
    return None


def _enforce_seller_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
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


# ─── Helpers for offer extraction ─────────────────────────────────────────────

_PRICE_RE = re.compile(r"\$?(\d{3,}(?:[,.\s]\d{3})*)")


def _extract_buyer_offer_price(buyer_text: str) -> int | None:
    """The buyer writes prose with a dollar amount. Extract the largest
    plausible price found in the text. Imperfect but good enough for a
    stall-detection signal — we are NOT using this to drive business logic,
    just to detect non-movement."""
    if not isinstance(buyer_text, str):
        return None
    candidates = []
    for match in _PRICE_RE.finditer(buyer_text):
        raw = match.group(1).replace(",", "").replace(" ", "").replace(".", "")
        try:
            n = int(raw)
        except ValueError:
            continue
        if 100_000 <= n <= 1_000_000:
            candidates.append(n)
    return max(candidates) if candidates else None


# ─── Stall-detection callback (the heart of this exercise) ────────────────────

def _track_and_check_stall(callback_context: CallbackContext):
    """Runs after the seller. Three jobs:

    1. If the seller accepted, escalate (deal done).
    2. Track this round's prices in offer_history.
    3. Check whether the last STALL_WINDOW rounds show movement < STALL_THRESHOLD.
       If so, escalate with a stall_reason in state.
    """
    state = callback_context.state

    # ─ Job 1: acceptance check (same as canonical orchestrator) ──────────
    decision = state.get("seller_decision")
    if isinstance(decision, dict) and decision.get("action") == "ACCEPT":
        # ADK drops a bare escalate: a callback only emits an event if it changes state.
        state["loop_exit_reason"] = f"ACCEPT at ${decision.get('price', 0):,}"
        callback_context.actions.escalate = True
        return None

    # ─ Job 2: track this round's offers ──────────────────────────────────
    buyer_price = _extract_buyer_offer_price(state.get("buyer_offer", ""))
    seller_price = decision.get("price") if isinstance(decision, dict) else None

    history = list(state.get("offer_history", []))
    history.append({"buyer": buyer_price, "seller": seller_price})
    state["offer_history"] = history

    print(
        f"[stall-check] round {len(history)}: buyer={buyer_price} "
        f"seller={seller_price}"
    )

    # ─ Job 3: stall check — last STALL_WINDOW rounds, all moved < THRESHOLD ─
    if len(history) >= STALL_WINDOW:
        window = history[-STALL_WINDOW:]
        # We need a buyer price AND a seller price for each round to compute movement.
        if all(r["buyer"] is not None and r["seller"] is not None for r in window):
            buyer_movements = [
                abs(window[i]["buyer"] - window[i - 1]["buyer"])
                for i in range(1, len(window))
            ]
            seller_movements = [
                abs(window[i]["seller"] - window[i - 1]["seller"])
                for i in range(1, len(window))
            ]
            max_move = max(buyer_movements + seller_movements)

            if max_move < STALL_THRESHOLD:
                state["stall_reason"] = (
                    f"No-progress detected: last {STALL_WINDOW} rounds had "
                    f"max movement of ${max_move:,} "
                    f"(threshold ${STALL_THRESHOLD:,})"
                )
                print(f"[stall-check] STALL DETECTED — {state['stall_reason']}")
                state["loop_exit_reason"] = "STALL"
                callback_context.actions.escalate = True

    return None


def _init_round_state(callback_context: CallbackContext):
    """Initialize seller_response on round 1 so the buyer's {seller_response}
    placeholder doesn't crash (same fix as the canonical orchestrator)."""
    if "seller_response" not in callback_context.state:
        callback_context.state["seller_response"] = "(No seller response yet — round 1)"
    return None


# ─── The agents ───────────────────────────────────────────────────────────────

# When STALL_DEMO=true, buyer budget drops to $440K (below seller's $445K floor)
# to guarantee a no-ZOPA stall. Default is $460K (healthy ZOPA).
_STALL_DEMO = os.environ.get("STALL_DEMO", "").lower() == "true"
_BUYER_BUDGET = 440_000 if _STALL_DEMO else 460_000
_BUYER_TARGET_LO = _BUYER_BUDGET - 10_000
_BUYER_TARGET_HI = _BUYER_BUDGET

buyer = LlmAgent(
    name="buyer",
    model=MODEL,
    instruction=(
        "You ARE the buyer's agent for 742 Evergreen Terrace, Austin TX 78701 "
        "(listed at $485,000) — a LIVE negotiation, not an assistant.\n\n"
        f"BUDGET: ${_BUYER_BUDGET:,} maximum — NEVER offer above this.\n"
        f"TARGET: ${_BUYER_TARGET_LO:,} - ${_BUYER_TARGET_HI:,}.\n\n"
        "EACH ROUND:\n"
        "1. Read {seller_response} and call your MCP pricing tools for market data.\n"
        "2. Make exactly ONE offer as a specific dollar amount, justified with data.\n"
        f"   If you have already reached your max (${_BUYER_BUDGET:,}) and the seller is "
        "still above it, hold firm and repeat the same number.\n\n"
        "OUTPUT: ONE short paragraph beginning with the literal prefix 'BUYER: ' "
        "stating your offer amount. No preamble, no step-by-step thinking, no "
        "'we will wait' meta commentary.\n\n"
        "CONFIDENTIAL — never reveal to the seller: your maximum budget, your target "
        "range, or that you are at your ceiling (avoid phrases like 'my maximum', "
        "'the most I can pay', 'my final offer'). Never reference or guess the seller's "
        "minimum or 'minimum acceptable price' — you do NOT have that information."
    ),
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable, args=[_PRICING_SERVER],
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
        "You ARE the seller's agent for 742 Evergreen Terrace — a LIVE negotiation, "
        "not an assistant.\n\n"
        "EACH ROUND:\n"
        "1. Read {buyer_offer} and look up your floor with `get_minimum_acceptable_price` "
        "for property_id='742-evergreen-austin-78701'.\n"
        "2. If buyer offer >= floor → submit_decision(action='ACCEPT', price=buyer_price, "
        "buyer_offer=buyer_price). Else → counter at a price between buyer_price and your "
        "previous counter, and submit_decision(action='COUNTER', price=your_counter, "
        "buyer_offer=buyer_price).\n"
        "3. ALWAYS call submit_decision. Do not just write your decision in prose. "
        "It enforces your minimum in code: if it records a different decision than you "
        "sent (see its 'note'), your reply MUST match what was recorded.\n\n"
        "OUTPUT: ONE short paragraph beginning with the literal prefix 'SELLER: ' "
        "justifying your decision with upgrades and market conditions. No preamble, "
        "no step-by-step thinking.\n\n"
        "CONFIDENTIAL — never reveal to the buyer: your minimum acceptable price / "
        "floor, your ideal price, the fact that you have a floor, or any output from "
        "get_minimum_acceptable_price. Justify counters only with upgrades and market "
        "conditions — never with your floor."
    ),
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable, args=[_PRICING_SERVER],
                )
            )
        ),
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable, args=[_INVENTORY_SERVER],
                )
            )
        ),
        submit_decision,
    ],
    before_tool_callback=_enforce_seller_allowlist,
    after_tool_callback=_remember_seller_floor,
    output_key="seller_response",
    after_agent_callback=_track_and_check_stall,  # ← the stall detector
)


negotiation_round = SequentialAgent(name="round", sub_agents=[buyer, seller])

root_agent = LoopAgent(
    name="negotiation",
    description="Multi-round buyer ↔ seller negotiation with stall detection.",
    sub_agents=[negotiation_round],
    max_iterations=5,
)
