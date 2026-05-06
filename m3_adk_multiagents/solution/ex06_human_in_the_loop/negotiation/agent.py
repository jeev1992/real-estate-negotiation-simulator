"""
Solution — Exercise 6: Human-in-the-Loop Checkpoint
======================================================

Negotiation orchestrator with a three-tier governance model:

  Tier 1 — Auto-approve:    Deal at or below $455,000 → escalate immediately
  Tier 2 — Human checkpoint: Deal above $455,000 → pause, prompt human, wait
  Tier 3 — Hard block:       (From Exercise 1) Price above $460,000 → callback blocks

The human checkpoint uses Python's input() for simplicity. In production,
replace with Slack/email/dashboard approval workflows.

NOTE: This exercise must be tested via terminal (python -m or adk run),
not adk web — the web UI doesn't support interactive input().

To demo:

    # Use adk web for observation, but the input() prompt will appear
    # in the terminal where adk web is running:
    adk web m3_adk_multiagents/solution/ex06_human_in_the_loop/

    Pick `negotiation`, send: "Start the negotiation."

    If the deal closes above $455K, the terminal will pause with:
      ╔══════════════════════════════════════════════════════╗
      ║  HUMAN APPROVAL REQUIRED                            ║
      ╚══════════════════════════════════════════════════════╝
      Approve this deal? [y/n]:
"""

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

MODEL = "openai/gpt-4o"

_REPO_ROOT = Path(__file__).resolve().parents[5]
_PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m2_mcp" / "inventory_server.py")

# ─── Governance threshold ────────────────────────────────────────────────────
# Deals at or below this price are auto-approved.
# Deals above require human confirmation.
AUTO_APPROVE_CEILING = 455_000


# ─── Tool allowlists ─────────────────────────────────────────────────────────

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


# ─── submit_decision ─────────────────────────────────────────────────────────

def submit_decision(action: str, price: int, tool_context: ToolContext) -> dict:
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


# ─── Human-in-the-loop callback (the heart of this exercise) ─────────────────

def _check_agreement_with_approval(callback_context: CallbackContext):
    """After the seller responds, implement three-tier governance.

    Tier 1: price <= AUTO_APPROVE_CEILING → auto-approve, escalate
    Tier 2: price >  AUTO_APPROVE_CEILING → human checkpoint
    Tier 3: (handled by buyer's budget callback, not here)
    """
    decision = callback_context.state.get("seller_decision")
    if not isinstance(decision, dict) or decision.get("action") != "ACCEPT":
        # Not an acceptance — counter-offers proceed without checkpoint
        return None

    price = decision.get("price", 0)

    # ── Tier 1: Auto-approve ──────────────────────────────────────────────
    if price <= AUTO_APPROVE_CEILING:
        print(f"[AUTO-APPROVED] Deal at ${price:,} — within auto-approval "
              f"threshold (${AUTO_APPROVE_CEILING:,})")
        callback_context.actions.escalate = True
        return None

    # ── Tier 2: Human checkpoint ──────────────────────────────────────────
    print()
    print("╔" + "═" * 54 + "╗")
    print(f"║  {'HUMAN APPROVAL REQUIRED':<52}  ║")
    print(f"║  {'Seller wants to accept at $' + f'{price:,}':<52}  ║")
    print(f"║  {'Auto-approval threshold: $' + f'{AUTO_APPROVE_CEILING:,}':<52}  ║")
    print("╚" + "═" * 54 + "╝")

    try:
        answer = input("Approve this deal? [y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        # Non-interactive environment — default to reject (safer)
        answer = "n"
        print("\n[NO INPUT] Defaulting to reject (non-interactive environment)")

    if answer == "y":
        print(f"[APPROVED] Human approved deal at ${price:,}")
        callback_context.actions.escalate = True
    else:
        print(f"[REJECTED] Human rejected deal at ${price:,}. "
              "Continuing negotiation.")
        # Override the seller's decision to COUNTER so the loop continues
        callback_context.state["seller_decision"] = {
            "action": "COUNTER",
            "price": price,
        }

    return None


def _init_round_state(callback_context: CallbackContext):
    """Ensure seller_response exists in state before round 1."""
    if "seller_response" not in callback_context.state:
        callback_context.state["seller_response"] = (
            "(No seller response yet — this is round 1)"
        )
    return None


# ─── Agents ───────────────────────────────────────────────────────────────────

buyer = LlmAgent(
    name="buyer",
    model=MODEL,
    instruction=(
        "You are a buyer agent for 742 Evergreen Terrace, Austin TX 78701 "
        "(listed at $485,000).\n\n"
        "BUDGET: $460,000 maximum.\n"
        "TARGET: $445,000 - $455,000.\n\n"
        "STRATEGY:\n"
        "- Call your MCP pricing tools BEFORE every offer\n"
        "- Round 1: offer ~$425,000\n"
        "- Each subsequent round: increase by 2-4%\n"
        "- Read {seller_response} and adjust\n"
        "- Walk away if seller won't go below $460,000\n\n"
        "Write your offer as a dollar amount with brief justification."
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
        "You are the seller agent for 742 Evergreen Terrace.\n\n"
        "STRATEGY:\n"
        "- Call your MCP tools BEFORE every response\n"
        "- Start counter at $477,000, drop $5k-$8k per round\n"
        "- NEVER go below your minimum (from get_minimum_acceptable_price)\n"
        "- If buyer offers at or above your minimum, ACCEPT immediately\n\n"
        "Read {buyer_offer}.\n"
        "IMPORTANT: After writing your response, you MUST call submit_decision "
        "with action='ACCEPT' or action='COUNTER' and the price."
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
    output_key="seller_response",
    after_agent_callback=_check_agreement_with_approval,  # ← the checkpoint
)

negotiation_round = SequentialAgent(
    name="round",
    sub_agents=[buyer, seller],
)

root_agent = LoopAgent(
    name="negotiation",
    description=(
        "Multi-round buyer ↔ seller negotiation with human-in-the-loop "
        "approval for deals above $455,000."
    ),
    sub_agents=[negotiation_round],
    max_iterations=5,
)
