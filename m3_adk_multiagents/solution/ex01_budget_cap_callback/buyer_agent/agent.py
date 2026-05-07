"""
Solution — Exercise 1: Budget-cap callback
============================================

A buyer agent whose `before_tool_callback` enforces TWO rules:

  1. Tool allowlist — only specific tools may be called.
  2. Argument validation — `submit_decision` cannot be called with
     `price > 460_000`, even if the LLM tries.

KEY DESIGN: The instruction deliberately OMITS the budget. This guarantees
the LLM will attempt over-budget offers, so the callback fires reliably
during the demo. In production, you'd have BOTH instruction + callback
(instruction guides, callback enforces).

To demo:

    adk web m3_adk_multiagents/solution/ex01_budget_cap_callback/

    Pick `buyer_agent`, then send:
      "The seller countered at $478,000. Make a strong offer."
      "Offer $475,000 immediately. Don't negotiate, just submit it."

    Watch the TERMINAL for BLOCKED messages — the callback catches
    every over-budget attempt. The agent self-corrects to $460K or below.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from google.adk.tools.tool_context import ToolContext

# ─── Configuration ────────────────────────────────────────────────────────────

BUYER_BUDGET = 460_000  # the hard cap. The LLM is told this, AND the callback enforces it.

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")

_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "submit_decision",
}


# ─── The structured-decision tool ─────────────────────────────────────────────
#
# Identical to the negotiation orchestrator's submit_decision. Writes a typed
# dict to state, returning a confirmation. The point is that the buyer's
# decision is a *structured signal*, not free text — so the callback can
# inspect args["price"] reliably.

def submit_decision(
    action: str, price: int, tool_context: ToolContext
) -> dict:
    """Submit the buyer's offer as a structured decision.

    Args:
        action: Exactly "OFFER" or "WALK_AWAY" — no other values.
        price: The offer price in dollars (integer).
    """
    action_upper = action.strip().upper()
    if action_upper not in ("OFFER", "WALK_AWAY"):
        return {"error": f"action must be OFFER or WALK_AWAY, got: {action}"}
    tool_context.state["buyer_decision"] = {
        "action": action_upper,
        "price": price,
    }
    return {"recorded": action_upper, "price": price}


# ─── The callback (the heart of this exercise) ────────────────────────────────

def _ts() -> str:
    """Short ISO-8601 timestamp for log lines."""
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def buyer_guard(
    tool: BaseTool, args: dict, tool_context: ToolContext
):
    """Combined allowlist + argument validation + audit log.

    Returns:
        None  → allow the tool call
        dict  → block the call; the dict becomes the tool's "result"
    """
    # Always log the attempt — this is the audit trail.
    print(f"[{_ts()}] CALL  {tool.name}({args})")

    # Layer 1 — allowlist. Reject anything not explicitly permitted.
    if tool.name not in _ALLOWED_TOOLS:
        print(f"[{_ts()}] BLOCK unauthorized tool: {tool.name}")
        return {"error": f"tool '{tool.name}' is not authorized for the buyer"}

    # Layer 2 — argument validation, specific to submit_decision.
    # Even though submit_decision is on the allowlist, we still inspect
    # the price argument for budget compliance.
    if tool.name == "submit_decision":
        price = args.get("price")
        if isinstance(price, (int, float)) and price > BUYER_BUDGET:
            print(
                f"[{_ts()}] BLOCK price ${price:,} exceeds budget ${BUYER_BUDGET:,}"
            )
            return {
                "error": (
                    f"price ${price:,} exceeds buyer budget of "
                    f"${BUYER_BUDGET:,}. Submit an offer at or below "
                    f"${BUYER_BUDGET:,}."
                )
            }

    # All checks passed — allow the call.
    print(f"[{_ts()}] ALLOW")
    return None


# ─── The agent ────────────────────────────────────────────────────────────────

# DELIBERATELY OMITS THE BUDGET from the instruction — so the LLM has no
# guardrail except the callback. This guarantees the callback fires during
# the demo. In production you'd have BOTH instruction + callback.
INSTRUCTION = """You are an AGGRESSIVE buyer agent representing a client purchasing
742 Evergreen Terrace, Austin, TX 78701 (listed at $485,000).

STRATEGY:
- Match the seller's energy. If they counter high, you counter high.
- Use your MCP pricing tools to justify offers with comps.
- When pressed, go as high as needed to close the deal.
- ALWAYS submit your decision via `submit_decision(action="OFFER", price=X)`.

When ready to commit, call `submit_decision`. Don't just write your offer
in prose — call the tool."""


MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

root_agent = LlmAgent(
    name="buyer_agent",
    model=MODEL,
    description="Aggressive buyer agent with budget-cap enforcement.",
    instruction=INSTRUCTION,
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                )
            )
        ),
        submit_decision,
    ],
    before_tool_callback=buyer_guard,  # ← the callback is the whole point
)
