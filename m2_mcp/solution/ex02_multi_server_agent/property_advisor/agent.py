"""
Solution — Exercise 2: Multi-server LlmAgent
==============================================

A `property_advisor` agent that connects to BOTH the pricing server and
the inventory server simultaneously, exposing all four tools to GPT-4o.

This is the same pattern as `seller_agent/agent.py`, but written from
scratch — and without the `before_tool_callback` allowlist (so the
agent can use every tool from both servers).

To demo:

    adk web m3_adk_multiagents/adk_demos/property_advisor/
    # OR (when this folder is symlinked / copied to adk_demos/):
    adk web m3_adk_multiagents/adk_demos/

    Then pick `property_advisor` from the dropdown and ask:
      - "What's 742 Evergreen Terrace worth?"
      - "What's the seller's minimum?"
      - "Walk me through whether to make an offer."
"""

import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)

# Resolve absolute paths to both MCP server scripts.
# This file lives at:
#   m2_mcp/solution/ex02_multi_server_agent/property_advisor/agent.py
# We need:                                ^---- parents[3] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m2_mcp" / "inventory_server.py")


def _mcp_toolset(server_path: str) -> MCPToolset:
    """Build a stdio-based MCPToolset pointing at a Python MCP server file."""
    return MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=[server_path],
            )
        )
    )


# ─── The agent ────────────────────────────────────────────────────────────────
#
# Key teaching point: `tools=[toolset_a, toolset_b]` causes ADK to merge
# the discovered tools from BOTH servers into a single tool catalog for
# the LLM. The model doesn't know which server hosts which tool — it just
# sees a unified function-calling list.

root_agent = LlmAgent(
    name="property_advisor",
    model="openai/gpt-4o",
    description=(
        "Real-estate advisor that combines market data (pricing) with "
        "inventory and seller-side data."
    ),
    instruction=(
        "You are a helpful real-estate advisor for a buyer evaluating "
        "742 Evergreen Terrace, Austin, TX 78701 (listed at $485,000).\n\n"
        "You have access to multiple data sources via MCP tools:\n"
        "- Pricing data (market value, comparable sales, discount analysis)\n"
        "- Inventory data (listings, market conditions, seller constraints)\n\n"
        "Use whichever tools are relevant for the user's question. For "
        "complex questions ('should I make an offer?'), call multiple "
        "tools and synthesize the results. Always cite the data you "
        "used in your answer."
    ),
    tools=[
        _mcp_toolset(_PRICING_SERVER),    # exposes get_market_price, calculate_discount
        _mcp_toolset(_INVENTORY_SERVER),  # exposes get_inventory_level, get_minimum_acceptable_price
    ],
    # Note: NO `before_tool_callback` here. Compare this to seller_agent —
    # this advisor can freely call any tool from either server. In a
    # production buyer-side advisor, you would NOT want this; you'd add
    # an allowlist that blocks `get_minimum_acceptable_price`.
)
