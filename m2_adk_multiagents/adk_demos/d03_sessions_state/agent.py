"""
Demo 03 — Sessions and State (session, user, and app scope)
=============================================================
LlmAgent whose tools read/write state at all three persistent scopes, so you
can see exactly what each one is shared with:

  Prefix   Example key           Shared with                       Stored in (session.db)
  ──────   ───────────────────   ───────────────────────────────   ─────────────────────
  (none)   offer_history         this conversation only            sessions
  user:    user:total_offers     this user, across all sessions    user_states
  app:     app:total_offers      every user of this agent          app_states

(temp: keys also exist — visible only during the current invocation and
never saved — but this demo sticks to the three that persist.)

ADK CONCEPTS:
  - ToolContext: injected into tools automatically by ADK
  - tool_context.state: one dict-like view; the key prefix picks the scope
  - tool_context.user_id: who is calling — used here to track app-wide buyers

Run:
    adk web m2_adk_multiagents/adk_demos/
        The web UI always runs as user "user" and can't switch users.

    python m2_adk_multiagents/adk_demos/d03_sessions_state/run_multi_user.py
        Drives this agent as several users (alice, bob) and writes to the
        SAME .adk/session.db that adk web uses, then prints its tables.
"""

import os

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext


def record_offer(price: int, tool_context: ToolContext) -> dict:
    """Record a buyer's offer price for 742 Evergreen Terrace."""
    state = tool_context.state

    # Session scope: this conversation only. Build a new list rather than
    # mutating the one stored in state.
    history = [*state.get("offer_history", []), price]
    state["offer_history"] = history

    # User scope: this buyer across all their sessions. Increment it —
    # len(history) would only count this session and reset the total.
    user_total = state.get("user:total_offers", 0) + 1
    state["user:total_offers"] = user_total

    # App scope: every buyer using this agent.
    state["app:total_offers"] = state.get("app:total_offers", 0) + 1
    buyers = state.get("app:buyers", [])
    if tool_context.user_id not in buyers:
        state["app:buyers"] = [*buyers, tool_context.user_id]
    highest = state.get("app:highest_offer")
    if not highest or price > highest["price"]:
        state["app:highest_offer"] = {"price": price, "user_id": tool_context.user_id}

    return {
        "recorded_price": price,
        "offers_this_session": len(history),
        "your_total_offers": user_total,
        "all_buyers_total_offers": state["app:total_offers"],
    }


def get_offer_history(tool_context: ToolContext) -> dict:
    """Return offer activity at every scope: this session, this buyer, all buyers."""
    state = tool_context.state
    return {
        "this_session": {"offers": state.get("offer_history", [])},
        "this_buyer": {
            "user_id": tool_context.user_id,
            "total_offers": state.get("user:total_offers", 0),
        },
        "all_buyers": {
            "total_offers": state.get("app:total_offers", 0),
            "buyers": state.get("app:buyers", []),
            "highest_offer": state.get("app:highest_offer"),
        },
    }


MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

root_agent = LlmAgent(
    name="stateful_agent",
    model=MODEL,
    description="Real estate agent that tracks offers per conversation, per buyer, and across all buyers.",
    instruction=(
        "You help buyers negotiate on 742 Evergreen Terrace (listed $485,000).\n\n"
        "When the user proposes an offer:\n"
        "  1. Call record_offer with their price.\n"
        "  2. Advise whether to hold firm, go higher, or walk away.\n\n"
        "When the user asks about past offers or market activity, call "
        "get_offer_history and keep the three levels distinct: this "
        "conversation, this buyer across all their conversations, and all "
        "buyers using this agent."
    ),
    tools=[record_offer, get_offer_history],
)
