"""
Demo 09 — ADK Event Stream
============================
An agent with tools that demonstrates the ADK event stream — the sequence
of Events emitted by Runner.run_async(). Every model call and tool call
produces an Event with content, actions, and metadata.

This demo prints all events to the terminal so you can see:
  - Which agent authored each event
  - Tool call requests and tool results as they happen
  - State deltas attached to events
  - The final response marker

ADK CONCEPTS:
  - Event: the unit of output from Runner.run_async()
  - event.author: which agent produced this event
  - event.content.parts: text, function_call, or function_response
  - event.actions: state_delta, escalate, transfer_to_agent
  - event.is_final_response(): marks the last text output
  - ToolContext state writes appear as state deltas in events

Run:
    adk web m3_adk_multiagents/adk_demos/d09_event_stream/

Note: The event details are visible in the adk web UI's "Events" panel
on the right side. This agent also prints events to the terminal for
instructor walkthroughs.
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
        "2. Call estimate_offer with the avg_comp_price and a 5%% discount\n"
        "3. Summarize: comps found, average, and your recommended offer\n\n"
        "Always call both tools in order."
    ),
    tools=[lookup_comps, estimate_offer],
)
