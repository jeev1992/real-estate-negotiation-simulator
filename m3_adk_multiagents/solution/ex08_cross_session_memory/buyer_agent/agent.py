"""
Solution — Exercise 8: Cross-session negotiation memory
=========================================================

A buyer agent that persists negotiation outcomes across sessions using
ADK's `user:`-scoped state. The deal journal survives "New Session" clicks,
letting the agent anchor future offers with historical data.

ADK CONCEPTS:
  - `user:` state prefix: persists for the same user_id across sessions
  - State as memory: tools read/write structured data to `user:deal_journal`
  - Placeholder injection: `{user:deal_journal}` in instruction → LLM sees past deals

To demo:

    adk web m3_adk_multiagents/solution/ex08_cross_session_memory/

    Session 1 — Pick `buyer_agent`, send:
      "I just closed on 742 Evergreen Terrace for $448,000 after 3 rounds. Record it."

    Click "New Session"

    Session 2 — Send:
      "I'm looking at 1234 Oak Street, listed at $510,000. What should I offer?"
      → Agent references the Evergreen deal as anchoring data.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from google.adk.tools.tool_context import ToolContext

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")

_BUYER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_property_tax_estimate",
    "record_deal",
    "recall_deals",
}


def _enforce_buyer_allowlist(
    tool: BaseTool, args: dict, tool_context: ToolContext
):
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the buyer"}
    return None


# ─── Memory tools ─────────────────────────────────────────────────────────────

def record_deal(
    property_name: str,
    final_price: int,
    rounds: int,
    outcome: str,
    tool_context: ToolContext,
) -> dict:
    """Save a completed negotiation outcome to persistent cross-session memory.

    Args:
        property_name: The property address (e.g. "742 Evergreen Terrace").
        final_price: The agreed price in dollars, or last offer if no deal.
        rounds: How many rounds the negotiation took.
        outcome: "ACCEPTED", "REJECTED", or "STALLED".
    """
    outcome_upper = outcome.strip().upper()
    if outcome_upper not in ("ACCEPTED", "REJECTED", "STALLED"):
        return {"error": f"outcome must be ACCEPTED, REJECTED, or STALLED, got: {outcome}"}

    journal = list(tool_context.state.get("user:deal_journal", []))
    entry = {
        "property": property_name,
        "final_price": final_price,
        "rounds": rounds,
        "outcome": outcome_upper,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    journal.append(entry)
    tool_context.state["user:deal_journal"] = journal
    tool_context.state["user:total_deals"] = len(journal)

    print(f"[memory] Recorded deal #{len(journal)}: {property_name} → ${final_price:,} ({outcome_upper})")

    return {
        "status": "recorded",
        "deal_number": len(journal),
        "entry": entry,
    }


def recall_deals(tool_context: ToolContext) -> dict:
    """Retrieve all past negotiation outcomes from persistent memory.

    Returns the full deal journal and summary statistics.
    """
    journal = list(tool_context.state.get("user:deal_journal", []))
    total = tool_context.state.get("user:total_deals", 0)

    if not journal:
        return {"deals": [], "total": 0, "message": "No past deals recorded yet."}

    # Compute summary stats
    accepted = [d for d in journal if d.get("outcome") == "ACCEPTED"]
    avg_price = (
        sum(d["final_price"] for d in accepted) // len(accepted)
        if accepted
        else None
    )

    return {
        "deals": journal,
        "total": total,
        "accepted_count": len(accepted),
        "average_accepted_price": avg_price,
    }


# ─── The agent ────────────────────────────────────────────────────────────────

def _init_memory(callback_context):
    """Ensure user: state keys exist before agent reads them."""
    if "user:deal_journal" not in callback_context.state:
        callback_context.state["user:deal_journal"] = []
    if "user:total_deals" not in callback_context.state:
        callback_context.state["user:total_deals"] = 0
    return None


root_agent = LlmAgent(
    name="buyer_agent",
    model="openai/gpt-4o",
    description="Buyer agent with persistent cross-session deal memory.",
    instruction=(
        "You are an expert real estate buyer agent with a MEMORY of past deals.\n\n"
        "PAST DEAL JOURNAL (persists across sessions):\n"
        "{user:deal_journal}\n\n"
        "YOUR CLIENT'S CONSTRAINTS:\n"
        "- Maximum budget: $460,000 for properties under $500K listing\n"
        "- Maximum budget: $510,000 for properties $500K+ listing\n"
        "- Pre-approved for financing, can close in 30–45 days\n\n"
        "STRATEGY:\n"
        "- ALWAYS review your past deal journal before making recommendations\n"
        "- Use past deals as anchoring data: 'Based on my experience closing "
        "  [property] at $X, I recommend...'\n"
        "- Call MCP pricing tools for current market data\n"
        "- Compare the current listing to similar past deals\n"
        "- When a negotiation concludes, call `record_deal` to save the outcome\n"
        "- When the user asks about past negotiations, call `recall_deals`\n\n"
        "If this is your first deal (no journal entries), mention that you're "
        "building your track record and rely more heavily on market data."
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
        record_deal,
        recall_deals,
    ],
    before_tool_callback=_enforce_buyer_allowlist,
    before_agent_callback=_init_memory,
)
