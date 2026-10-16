"""
Demo 03 — Sessions and State
==============================
LlmAgent that uses ToolContext to read/write session state across turns.
State persists within a session, letting the agent remember offer history.

ADK CONCEPTS:
  - ToolContext: injected into tools automatically by ADK
  - State scoping: "user:" prefix persists across sessions for the same user
  - Session state: tools can read/write shared state that the agent sees

Run:
    adk web m2_adk_multiagents/adk_demos/d03_sessions_state/
"""

import os

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext


def record_offer(price: int, tool_context: ToolContext) -> dict:
    """Record the user's latest offer price in session state."""
    # Build a new list rather than mutating the one stored in state.
    history = [*tool_context.state.get("offer_history", []), price]
    tool_context.state["offer_history"] = history
    # user: state outlives the session, so increment it — len(history) would
    # only count this session and reset the lifetime total in a new session.
    total = tool_context.state.get("user:total_offers", 0) + 1
    tool_context.state["user:total_offers"] = total
    return {
        "recorded_price": price,
        "offers_this_session": len(history),
        "total_across_sessions": total,
        "all_offers": history,
    }


def get_offer_history(tool_context: ToolContext) -> dict:
    """Retrieve the full history of offers made in this session."""
    history = tool_context.state.get("offer_history", [])
    total = tool_context.state.get("user:total_offers", 0)
    return {"offers": history, "total_across_sessions": total}


MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

root_agent = LlmAgent(
    name="stateful_agent",
    model=MODEL,
    description="Real estate agent that remembers offer history across turns.",
    instruction=(
        "You help users negotiate on 742 Evergreen Terrace (listed $485,000).\n\n"
        "When the user proposes an offer:\n"
        "  1. Call record_offer with their price\n"
        "  2. Review the offer history\n"
        "  3. Advise whether to hold firm, go higher, or walk away\n\n"
        "When the user asks about past offers, call get_offer_history.\n"
        "Use the history to give strategic advice."
    ),
    tools=[record_offer, get_offer_history],
)
