"""
Solution — Exercise 4: Mediator agent with AgentTool
======================================================

A `mediator` LlmAgent that wraps two specialists as AgentTools:

  • buyer_specialist  — reports the buyer's budget ceiling
  • seller_specialist — calls the inventory MCP server for the seller's floor

The mediator's instruction tells it to call both, then propose a midpoint.
The mediator's LLM decides *when* to call each specialist; we don't wire
the calls explicitly.

Hierarchical delegation: parent LLM decides → child LLM executes → parent
synthesizes. Three LLM calls per user question (one mediator + two specialists).

To demo:

    adk web m3_adk_multiagents/solution/ex04_mediator_agent/

    Pick `mediator`, send: "What's a fair price for 742 Evergreen Terrace?"

    Watch the events panel — you'll see two tool calls (buyer_specialist,
    seller_specialist) plus the mediator's synthesis.
"""

import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)

import os

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_INVENTORY_SERVER = str(_REPO_ROOT / "m2_mcp" / "inventory_server.py")


# ─── Specialist 1: buyer_specialist ───────────────────────────────────────────
#
# Knows the buyer's budget ($460,000). Hardcoded into the instruction.
# Returns one short sentence — that's what the mediator will see as its
# "tool result."

buyer_specialist = LlmAgent(
    name="buyer_specialist",
    model=MODEL,
    description=(
        "Reports the buyer's maximum budget for property purchase. "
        "Call this when you need to know the buyer's hard ceiling."
    ),
    instruction=(
        "You represent the buyer for 742 Evergreen Terrace. Their "
        "maximum budget is $460,000.\n\n"
        "When asked, respond with EXACTLY ONE sentence stating the "
        "buyer's maximum budget. Format: 'The buyer's maximum budget "
        "is $460,000.'"
    ),
    # No tools — pure prompt-driven specialist.
)


# ─── Specialist 2: seller_specialist ──────────────────────────────────────────
#
# Has access to the inventory MCP server, so it can look up the *real*
# floor price via get_minimum_acceptable_price. The mediator only sees
# this specialist's text response — it never sees the raw tool result.

seller_specialist = LlmAgent(
    name="seller_specialist",
    model=MODEL,
    description=(
        "Reports the seller's minimum acceptable price for property sales. "
        "Call this when you need to know the seller's floor. "
        "Uses real seller-side data via MCP."
    ),
    instruction=(
        "You represent the seller of 742 Evergreen Terrace.\n\n"
        "When asked for the seller's floor price, you MUST call "
        "`get_minimum_acceptable_price` with property_id="
        "'742-evergreen-austin-78701' to retrieve the real floor.\n\n"
        "Respond with EXACTLY ONE sentence. Format: 'The seller's "
        "minimum acceptable price is $X.'"
    ),
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_INVENTORY_SERVER],
                )
            )
        )
    ],
)


# ─── The mediator (the parent agent) ──────────────────────────────────────────
#
# The mediator's `tools=[...]` contains the two specialists wrapped as
# AgentTools. From the mediator's LLM's perspective, these look identical
# to function tools — same JSON Schema shape, same call interface.
#
# What's different: when the mediator's LLM calls `buyer_specialist`,
# ADK runs the WHOLE buyer_specialist agent (its own LLM call, its own
# tools), then returns the specialist's final text as the "tool result"
# back into the mediator's conversation.

root_agent = LlmAgent(
    name="mediator",
    model=MODEL,
    description=(
        "Real estate negotiation mediator. Proposes fair midpoint prices "
        "by consulting both buyer-side and seller-side specialists."
    ),
    instruction=(
        "You are an impartial real estate mediator for 742 Evergreen Terrace.\n\n"
        "When asked about pricing or whether a deal is possible:\n"
        "1. Call `buyer_specialist` to learn the buyer's maximum budget.\n"
        "2. Call `seller_specialist` to learn the seller's minimum acceptable price.\n"
        "3. If buyer_max >= seller_min, propose the **midpoint** as a fair price.\n"
        "4. If buyer_max < seller_min, explain that no deal is possible — "
        "   there is no Zone of Possible Agreement.\n\n"
        "Always call BOTH specialists. Show your reasoning by citing both "
        "numbers in your final answer."
    ),
    tools=[
        AgentTool(agent=buyer_specialist),    # parent calls child as a tool
        AgentTool(agent=seller_specialist),
    ],
)
