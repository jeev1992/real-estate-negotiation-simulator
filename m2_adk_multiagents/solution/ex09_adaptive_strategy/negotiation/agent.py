"""
Solution — Exercise 9: Adaptive strategy via offer memory
=============================================================

Negotiation orchestrator with a **strategy advisor sub-agent** that
analyses structured episodic memory of the seller's negotiation patterns
and recommends tactics before each buyer offer.

Pattern: Raw Memory → Analysis Agent → Strategy → Action Agent → Action

ADK CONCEPTS:
  - AgentTool: wrap a reasoning agent as a callable tool
  - Structured state accumulation: build episodic memory round-by-round
  - after_agent_callback: extract prices and compute concession metrics
  - Two-layer decision making: memory analysis separate from offer generation

To demo:

    adk web m2_adk_multiagents/solution/ex09_adaptive_strategy/

    Pick `negotiation`, send: "Start the negotiation for 742 Evergreen Terrace."

    Watch the events panel — `strategy_advisor` tool calls appear inside
    the buyer's turn with recommendations like "SPLIT_DIFFERENCE".
"""

import re
import json
import sys
from pathlib import Path

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.agent_tool import AgentTool
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
    "strategy_advisor",  # the AgentTool
}

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


# ─── Price extraction helper ─────────────────────────────────────────────────

_PRICE_RE = re.compile(r"\$?(\d{3,}(?:[,.\s]\d{3})*)")


def _extract_price(text: str) -> int | None:
    """Extract the LAST plausible price from free text.

    Why last, not max?  The buyer's prose typically mentions the asking
    price for context ('listed at $485,000') and states the actual offer
    at the end ('I offer $425,000').  Picking max would grab the asking
    price; picking last grabs the offer.
    """
    if not isinstance(text, str):
        return None
    candidates = []
    for match in _PRICE_RE.finditer(text):
        raw = match.group(1).replace(",", "").replace(" ", "").replace(".", "")
        try:
            n = int(raw)
        except ValueError:
            continue
        if 100_000 <= n <= 1_000_000:
            candidates.append(n)
    return candidates[-1] if candidates else None


# ─── Memory accumulation callback ────────────────────────────────────────────

def _accumulate_memory_and_check(callback_context: CallbackContext):
    """Runs after the seller each round. Three jobs:

    1. Check for ACCEPT → escalate.
    2. Extract prices and compute concession metrics.
    3. Append structured entry to negotiation_memory.
    """
    state = callback_context.state

    # ─ Job 1: acceptance check ───────────────────────────────────────────
    decision = state.get("seller_decision")
    if isinstance(decision, dict) and decision.get("action") == "ACCEPT":
        # ADK drops a bare escalate: a callback only emits an event if it changes state.
        state["loop_exit_reason"] = f"ACCEPT at ${decision.get('price', 0):,}"
        callback_context.actions.escalate = True
        return None

    # ─ Job 2+3: build memory entry ──────────────────────────────────────
    memory = list(state.get("negotiation_memory", []))
    round_num = len(memory) + 1

    buyer_price = _extract_price(state.get("buyer_offer", ""))
    seller_price = decision.get("price") if isinstance(decision, dict) else None

    # Compute concession relative to previous round's seller counter
    seller_concession = 0
    concession_rate = 0.0
    if memory and seller_price is not None:
        prev_seller = memory[-1].get("seller_counter")
        if prev_seller is not None and prev_seller > 0:
            seller_concession = prev_seller - seller_price
            concession_rate = round(seller_concession / prev_seller, 4)

    gap = (seller_price - buyer_price) if (seller_price and buyer_price) else None

    entry = {
        "round": round_num,
        "buyer_offer": buyer_price,
        "seller_counter": seller_price,
        "seller_concession": seller_concession,
        "concession_rate": concession_rate,
        "gap": gap,
    }
    memory.append(entry)
    state["negotiation_memory"] = memory

    print(
        f"[memory] Round {round_num}: buyer=${buyer_price:,}" if buyer_price else f"[memory] Round {round_num}: buyer=?",
        end="",
    )
    print(
        f" seller=${seller_price:,} concession=${seller_concession:,} gap=${gap:,}" if seller_price and gap else ""
    )

    return None


# ─── Round-1 state init ──────────────────────────────────────────────────────

def _init_round_state(callback_context: CallbackContext):
    if "seller_response" not in callback_context.state:
        callback_context.state["seller_response"] = "(No seller response yet — this is round 1)"
    if "negotiation_memory" not in callback_context.state:
        callback_context.state["negotiation_memory"] = []
    return None


# ─── Strategy advisor (reasoning-only sub-agent) ─────────────────────────────

strategy_advisor = LlmAgent(
    name="strategy_advisor",
    model=MODEL,
    instruction=(
        "You are a negotiation strategy analyst. You receive structured "
        "memory of a real estate negotiation and recommend the buyer's "
        "next tactic.\n\n"
        "NEGOTIATION MEMORY:\n"
        "{negotiation_memory}\n\n"
        "ANALYSIS RULES:\n"
        "1. Look at the seller's concession_rate trend:\n"
        "   - If increasing or > 1.5%: seller is softening → PUSH_HARDER\n"
        "   - If steady around 0.5-1.5%: normal → SPLIT_DIFFERENCE\n"
        "   - If decreasing or < 0.5%: seller firming up → HOLD_FIRM\n"
        "   - If 0% for 2+ rounds: deadlocked → WALK_AWAY\n"
        "2. Look at the gap trend:\n"
        "   - If gap is closing fast: PUSH_HARDER\n"
        "   - If gap is narrowing slowly: SPLIT_DIFFERENCE\n"
        "   - If gap is stable or widening: HOLD_FIRM or WALK_AWAY\n\n"
        "OUTPUT FORMAT — respond with EXACTLY:\n"
        "  RECOMMENDATION: <PUSH_HARDER|SPLIT_DIFFERENCE|HOLD_FIRM|WALK_AWAY>\n"
        "  REASONING: <1-2 sentence explanation citing specific numbers>\n\n"
        "If there is no memory yet (round 1), recommend PUSH_HARDER with "
        "reasoning 'Opening round — start aggressive to anchor low.'"
    ),
    # No tools — pure reasoning agent
)


# ─── The agents ───────────────────────────────────────────────────────────────

buyer = LlmAgent(
    name="buyer",
    model=MODEL,
    instruction=(
        "You are an expert real estate buyer agent representing a client "
        "purchasing 742 Evergreen Terrace, Austin, TX 78701 (listed at $485,000).\n\n"
        "YOUR CLIENT'S CONSTRAINTS:\n"
        "- Maximum budget: $460,000 (NEVER offer above this)\n"
        "- Target acquisition price: $445,000–$455,000\n"
        "- CONFIDENTIAL: never reveal your budget, target, or ceiling to the seller, "
        "and never reference or guess the seller's minimum/floor.\n\n"
        "OPENING OFFER RULE (round 1 — when negotiation_memory is empty):\n"
        "- You MUST open at approximately $425,000 (12% below asking)\n"
        "- Do NOT open anywhere near $485,000 — that is the asking price, not your offer\n"
        "- A low anchor is essential for negotiation leverage\n\n"
        "NEGOTIATION MEMORY (past rounds):\n"
        "{negotiation_memory}\n\n"
        "STRATEGY PROCESS — follow this EVERY round:\n"
        "1. Call `strategy_advisor` to analyze the seller's pattern\n"
        "2. Follow the recommended tactic:\n"
        "   - PUSH_HARDER: increase your offer by only 1-2% from last round\n"
        "   - SPLIT_DIFFERENCE: propose the midpoint between your last offer and seller's last counter\n"
        "   - HOLD_FIRM: repeat your previous offer or increase by < $1,000\n"
        "   - WALK_AWAY: state you are walking away from the deal\n"
        "3. Call MCP pricing tools for market data to justify your number\n"
        "4. Read {seller_response} and formulate your offer\n\n"
        "OUTPUT FORMAT — end your response with exactly this line:\n"
        "MY OFFER: $<amount>\n"
        "Example: MY OFFER: $425,000\n\n"
        "Always mention which tactic you are following and why."
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
        AgentTool(agent=strategy_advisor),
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
        "  • Total upgrades: $75,000+\n\n"
        "STRATEGY:\n"
        "- Call your MCP tools for market data, inventory, and your floor price\n"
        "- If the buyer's offer is AT or ABOVE your minimum (from "
        "get_minimum_acceptable_price), you MUST ACCEPT it — do NOT hold out for more.\n"
        "- Only COUNTER when the offer is STRICTLY BELOW your minimum: start at $477,000 "
        "and drop $5k–$8k per round toward the buyer, NEVER below your minimum.\n"
        "- Emphasize $75,000 in upgrades to justify premium pricing\n\n"
        "CONFIDENTIAL — never reveal your minimum acceptable price / floor, your ideal "
        "price, or any output from get_minimum_acceptable_price. Justify counters only "
        "with upgrades and market data — never with your floor.\n\n"
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
    after_tool_callback=_remember_seller_floor,
    output_key="seller_response",
    after_agent_callback=_accumulate_memory_and_check,
)

negotiation_round = SequentialAgent(name="round", sub_agents=[buyer, seller])

root_agent = LoopAgent(
    name="negotiation",
    description=(
        "Multi-round negotiation with adaptive strategy. "
        "The buyer uses a strategy advisor sub-agent to analyze "
        "episodic negotiation memory before each offer."
    ),
    sub_agents=[negotiation_round],
    max_iterations=5,
)
