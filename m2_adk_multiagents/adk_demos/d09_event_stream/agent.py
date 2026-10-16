"""
Demo 09 — ADK Event Stream
============================
An agent with two state-writing tools that demonstrates the ADK event
stream — the sequence of Events emitted by Runner.run_async(). Every user
message, model tool-call request, tool result, and final answer is an
Event carrying content, actions, and metadata.

ADK CONCEPTS:
  - Event: the unit of output from Runner.run_async()
  - event.author: who produced this event ("user" or the agent's name)
  - event.content.parts: text, function_call, or function_response
  - event.actions: state_delta, escalate, transfer_to_agent
  - event.is_final_response(): marks the last text output of a turn
  - ToolContext state writes appear as state deltas on tool-result events

Two ways to run it:

  1. Web UI — click events in the left-panel inspector, watch the State tab:
       adk web m2_adk_multiagents/adk_demos/

  2. Terminal — drive this same root_agent with Runner.run_async() and
     print every Event as it is yielded:
       python m2_adk_multiagents/adk_demos/d09_event_stream/run_event_stream.py
"""

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext

import os

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")


def lookup_comps(address: str, tool_context: ToolContext) -> dict:
    """Look up comparable sales near an address."""
    # Write to session state so it shows up in event state_delta
    tool_context.state["last_comp_lookup"] = address
    return {
        "address": address,
        "comps": [
            {"address": "740 Evergreen Terrace", "sold_price": 458_000},
            {"address": "744 Evergreen Terrace", "sold_price": 472_000},
        ],
        "avg_comp_price": 465_000,
    }


def estimate_offer(
    comp_avg: int, discount_pct: int, tool_context: ToolContext
) -> dict:
    """Calculate an offer price from comps with a discount."""
    offer = int(comp_avg * (1 - discount_pct / 100))
    tool_context.state["latest_offer"] = offer
    tool_context.state["offer_count"] = (
        tool_context.state.get("offer_count", 0) + 1
    )
    return {
        "comp_avg": comp_avg,
        "discount_pct": discount_pct,
        "offer_price": offer,
    }


root_agent = LlmAgent(
    name="event_stream_demo",
    model=MODEL,
    description="Demo agent that shows ADK event stream with tool calls and state.",
    instruction=(
        "You are a real estate pricing assistant.\n\n"
        "When the user asks about a property:\n"
        "1. Call lookup_comps with the address\n"
        "2. Call estimate_offer with the avg_comp_price and a 5% discount\n"
        "3. Summarize: comps found, average, and your recommended offer\n\n"
        "Always call both tools in order."
    ),
    tools=[lookup_comps, estimate_offer],
)
