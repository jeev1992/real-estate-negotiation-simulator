"""
Solution — Exercise 1: Budget-cap callback
============================================

A buyer agent whose `before_tool_callback` enforces TWO rules:

  1. Tool allowlist — only specific tools may be called.
  2. Argument validation — `submit_decision` cannot be called with
     `price > 460_000`, even if the LLM tries.

The instruction is intentionally aggressive ("anchor high, retreat slowly")
to make GPT-4o occasionally generate over-budget offers — so you can
SEE the callback fire during the demo.

To demo:

    adk web m3_adk_multiagents/solution/ex01_budget_cap_callback/

    Pick `buyer_agent`, then send messages like:
      "The seller countered at $477,000. Make your next offer."
      "Counter at $475,000."   (forcing the LLM toward over-budget)

    Watch the TERMINAL for the callback's print() output — that's the
    audit trail. The chat panel shows the agent recovering from blocked
    calls.
"""

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

# DELIBERATELY AGGRESSIVE instruction — designed to make the LLM occasionally
# attempt over-budget offers, so the demo SHOWS the callback firing.
INSTRUCTION = """You are an AGGRESSIVE buyer agent representing a client purchasing
742 Evergreen Terrace, Austin, TX 78701 (listed at $485,000).

YOUR CLIENT'S CONSTRAINTS:
- Maximum budget: $460,000 (HARD CAP — never exceed)

STRATEGY:
- Anchor HIGH. Open near the seller's expectations to project strength.
- When the seller counters above your budget, push back hard with a
  high but in-budget offer. Aim near $458,000-$460,000 — the very edge.
- Use your MCP pricing tools to justify offers with comps.
- ALWAYS submit your decision via `submit_decision(action="OFFER", price=X)`.

When ready to commit, call `submit_decision`. Don't just write your offer
in prose — call the tool."""


root_agent = LlmAgent(
    name="buyer_agent",
    model="openai/gpt-4o",
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
