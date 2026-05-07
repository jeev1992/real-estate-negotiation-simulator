"""
Solution — Exercise 6: Human-in-the-Loop Checkpoint
======================================================

Negotiation orchestrator with a three-tier governance model:

  Tier 1 — Auto-approve:    Deal at or below $455,000 → escalate immediately
  Tier 2 — Human checkpoint: Deal above $455,000 → pause, ask user in chat
  Tier 3 — Hard block:       (From Exercise 1) Price above $460,000 → callback blocks

The human checkpoint works through the **web UI chat**: the negotiation
loop exits with a pending approval, and the parent LlmAgent asks the
user to approve or reject in the conversation.

To demo:

    adk web m3_adk_multiagents/solution/ex06_human_in_the_loop/

    Pick `negotiation`, send: "Start the negotiation."

    If the deal closes above $455K, the agent will ask you:
      "The seller wants to accept at $457,000. Approve or reject?"

    Reply "approve" or "reject" in the chat.
"""

import re
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
    """After each round, implement three-tier governance.

    Tier 1: price <= AUTO_APPROVE_CEILING → auto-approve, escalate
    Tier 2: price >  AUTO_APPROVE_CEILING → set pending_approval, escalate
            (parent LlmAgent will ask user in chat)
    Tier 3: (handled by buyer's budget callback, not here)
    """
    if callback_context.state.get("deal_finalized"):
        callback_context.actions.escalate = True
        return None

    decision = callback_context.state.get("seller_decision")
    if not isinstance(decision, dict) or decision.get("action") != "ACCEPT":
        return None

    price = decision.get("price", 0)

    # ── Tier 1: Auto-approve ──────────────────────────────────────────────
    if price <= AUTO_APPROVE_CEILING:
        print(f"[AUTO-APPROVED] Deal at ${price:,} — within threshold")
        callback_context.state["deal_finalized"] = True
        callback_context.state["deal_outcome"] = (
            f"Deal auto-approved at ${price:,} (within ${AUTO_APPROVE_CEILING:,} threshold)."
        )
        callback_context.actions.escalate = True
        return None

    # ── Tier 2: Pending human approval ────────────────────────────────────
    print(f"[PENDING APPROVAL] Deal at ${price:,} — above threshold, asking user")
    callback_context.state["pending_approval"] = {
        "price": price,
        "threshold": AUTO_APPROVE_CEILING,
    }
    callback_context.state["deal_outcome"] = (
        f"Negotiation paused — seller wants to accept at ${price:,}, "
        f"which exceeds the auto-approval threshold of ${AUTO_APPROVE_CEILING:,}."
    )
    callback_context.actions.escalate = True
    return None


def _init_round_state(callback_context: CallbackContext):
    """Ensure state variables exist before round 1."""
    if "seller_response" not in callback_context.state:
        callback_context.state["seller_response"] = (
            "(No seller response yet — this is round 1)"
        )
    if "deal_outcome" not in callback_context.state:
        callback_context.state["deal_outcome"] = "(negotiation not started yet)"
    if "pending_approval" not in callback_context.state:
        callback_context.state["pending_approval"] = ""
    return None


# ─── Agents ───────────────────────────────────────────────────────────────────

buyer = LlmAgent(
    name="buyer",
    model=MODEL,
    instruction=(
        "You are a buyer agent for 742 Evergreen Terrace, Austin TX 78701 "
        "(listed at $485,000).\n\n"
        "BUDGET: $460,000 maximum.\n"
        "TARGET: $455,000 - $460,000.\n\n"
        "STRATEGY:\n"
        "- Call your MCP pricing tools BEFORE every offer\n"
        "- Round 1: offer ~$450,000\n"
        "- Each subsequent round: increase by 1-2%\n"
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
)

negotiation_round = SequentialAgent(
    name="round",
    sub_agents=[buyer, seller],
    after_agent_callback=_check_agreement_with_approval,
)

negotiation_loop = LoopAgent(
    name="negotiation_loop",
    description=(
        "Runs multi-round buyer ↔ seller negotiation. Returns the deal outcome. "
        "If deal is at or below $455,000 it is auto-approved. "
        "If above $455,000, it needs human approval — the outcome will say 'paused'."
    ),
    sub_agents=[negotiation_round],
    max_iterations=5,
)

# ─── Root agent: orchestrates negotiation + handles approval in chat ──────────

root_agent = LlmAgent(
    name="negotiation",
    model=MODEL,
    description=(
        "Multi-round buyer ↔ seller negotiation with human-in-the-loop "
        "approval for deals above $455,000."
    ),
    instruction=(
        "You orchestrate real estate negotiations with human oversight.\n\n"
        "WORKFLOW:\n"
        "1. When the user asks to negotiate, call the `negotiation_loop` tool.\n"
        "2. After it completes, read the session state to check what happened:\n"
        "   - If the deal was auto-approved (at or below $455,000), report "
        "     the final price to the user.\n"
        "   - If there is a pending approval (deal above $455,000), tell the "
        "     user the price and ask: 'The seller wants to accept at $X. "
        "This exceeds the $455,000 auto-approval threshold. "
        "Do you APPROVE or REJECT this deal?'\n"
        "3. If the user says APPROVE: confirm the deal is closed at that price.\n"
        "4. If the user says REJECT: tell the user the deal was rejected.\n\n"
        "Always wait for the user's response before finalizing."
    ),
    tools=[AgentTool(agent=negotiation_loop)],
)
