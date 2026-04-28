"""
Buyer Agent — Idiomatic ADK
==============================
Declarative LlmAgent with MCPToolset for pricing tools.
Demonstrates: LlmAgent, MCPToolset (stdio), before_tool_callback (allowlist).

Run with:
    adk web m3_adk_multiagents/negotiation_agents/
    adk web --a2a m3_adk_multiagents/negotiation_agents/
"""

import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from google.adk.tools.tool_context import ToolContext

_PRICING_SERVER = str(
    Path(__file__).resolve().parents[3] / "m2_mcp" / "pricing_server.py"
)

# Information asymmetry: buyer can only see market-facing pricing tools.
_BUYER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_property_tax_estimate",
}


def _enforce_buyer_allowlist(
    tool: BaseTool, args: dict, tool_context: ToolContext
):
    """Block tools not on the buyer's allowlist."""
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the buyer"}
    return None


root_agent = LlmAgent(
    name="buyer_agent",
    model="openai/gpt-4o",
    description="Real estate buyer agent for 742 Evergreen Terrace, Austin TX.",
    instruction=(
        "You are an expert real estate buyer agent representing a client "
        "purchasing 742 Evergreen Terrace, Austin, TX 78701 (listed at $485,000).\n\n"
        "YOUR CLIENT'S CONSTRAINTS:\n"
        "- Maximum budget: $460,000 (NEVER offer above this)\n"
        "- Target acquisition price: $445,000–$455,000\n"
        "- Pre-approved for financing, can close in 30–45 days\n\n"
        "STRATEGY:\n"
        "- Call your MCP pricing tools BEFORE every offer to get market data\n"
        "- Round 1: offer ~12%% below asking (~$425,000)\n"
        "- Each subsequent round: increase by 2–4%%\n"
        "- Walk away if seller won't go below $460,000\n\n"
        "Always justify your offers with data from your tools."
    ),
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                )
            )
        )
    ],
    before_tool_callback=_enforce_buyer_allowlist,
)
