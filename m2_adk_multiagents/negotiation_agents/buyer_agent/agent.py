"""
Buyer Agent — Idiomatic ADK
==============================
Declarative LlmAgent with MCPToolset for pricing tools.
Demonstrates: LlmAgent, MCPToolset (stdio), before_tool_callback (allowlist).

Run with:
    adk web m2_adk_multiagents/negotiation_agents/
    adk web --a2a m2_adk_multiagents/negotiation_agents/
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

_PRICING_SERVER = str(
    Path(__file__).resolve().parents[3] / "m1_mcp" / "pricing_server.py"
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


MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

root_agent = LlmAgent(
    name="buyer_agent",
    model=MODEL,
    description="Real estate buyer agent for 742 Evergreen Terrace, Austin TX.",
    instruction=(
        "You ARE the buyer's agent in a LIVE negotiation — not an assistant waiting "
        "on anyone. You represent a client purchasing 742 Evergreen Terrace, "
        "Austin, TX 78701 (listed at $485,000).\n\n"
        "CLIENT CONSTRAINTS:\n"
        "- Maximum budget: $460,000 — NEVER offer above this under any circumstances.\n"
        "- Target acquisition price: $445,000–$455,000.\n"
        "- Pre-approved for financing, can close in 30–45 days.\n\n"
        "EACH ROUND:\n"
        "1. Call your MCP pricing tools first to get fresh market data.\n"
        "2. Make exactly ONE offer:\n"
        "   - Opening round (no seller response yet): ~12% below asking (~$425,000).\n"
        "   - Later rounds: raise your previous offer by 2–4% toward the seller, "
        "never above $460,000.\n"
        "   - If the seller will not go below $460,000, state that you WALK AWAY.\n\n"
        "OUTPUT FORMAT: reply with ONE short paragraph beginning with the literal "
        "prefix 'BUYER: ', stating your offer amount with a brief, data-backed "
        "justification. No preamble, no step-by-step thinking, no 'we will wait' "
        "meta commentary.\n\n"
        "CONFIDENTIAL — never reveal these to the seller: your maximum budget "
        "($460,000), your target range, or your walk-away threshold. Do NOT signal "
        "you are at your ceiling (avoid phrases like 'the maximum I can accommodate', "
        "'my highest/best/final offer'). Never reference or guess the seller's minimum "
        "or 'minimum acceptable price' — you do NOT have that information."
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
