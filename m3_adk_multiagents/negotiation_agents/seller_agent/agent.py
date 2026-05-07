"""
Seller Agent — Idiomatic ADK
===============================
Declarative LlmAgent with dual MCPToolsets (pricing + inventory).
Demonstrates: multiple MCPToolsets, information asymmetry via allowlist.

The seller has access to get_minimum_acceptable_price (from the inventory
server) — a tool the buyer never sees.

Run with:
    adk web m3_adk_multiagents/negotiation_agents/
    adk web --a2a m3_adk_multiagents/negotiation_agents/
"""

import os
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

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m2_mcp" / "inventory_server.py")

# Seller has access to inventory tools (including private floor price).
_SELLER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_inventory_level",
    "get_minimum_acceptable_price",  # seller-only
}


def _enforce_seller_allowlist(
    tool: BaseTool, args: dict, tool_context: ToolContext
):
    """Block tools not on the seller's allowlist."""
    if tool.name not in _SELLER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the seller"}
    return None


MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

root_agent = LlmAgent(
    name="seller_agent",
    model=MODEL,
    description="Real estate seller agent for 742 Evergreen Terrace, Austin TX.",
    instruction=(
        "You are an expert listing agent for 742 Evergreen Terrace, "
        "Austin, TX 78701 (listed at $485,000).\n\n"
        "PROPERTY HIGHLIGHTS:\n"
        "  • Kitchen renovated 2023 ($45k), new roof 2022 ($18k), HVAC 2021 ($12k)\n"
        "  • Total upgrades: $75,000+\n"
        "  • Austin ISD (rated 8/10), zero HOA fees\n\n"
        "STRATEGY:\n"
        "- Call your MCP tools BEFORE every response (market price, inventory, floor price)\n"
        "- Start counter at $477,000, drop $5k–$8k per round only\n"
        "- NEVER go below your minimum (from get_minimum_acceptable_price tool)\n"
        "- If buyer offers at or above your minimum, ACCEPT immediately\n"
        "- Emphasize $75,000 in upgrades to justify premium pricing\n\n"
        "Always call your tools before responding to any offer."
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
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_INVENTORY_SERVER],
                )
            )
        ),
    ],
    before_tool_callback=_enforce_seller_allowlist,
)
