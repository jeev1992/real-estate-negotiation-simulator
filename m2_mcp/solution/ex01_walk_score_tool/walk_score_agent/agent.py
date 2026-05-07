"""
Walk Score Agent — wraps the ex01 solution pricing server (with get_walk_score)
so it can be launched via `adk web`.

    adk web m2_mcp/solution/ex01_walk_score_tool/
"""

import os
import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)

_PRICING_SERVER = str(
    Path(__file__).resolve().parent.parent / "pricing_server.py"
)

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

root_agent = LlmAgent(
    name="walk_score_agent",
    model=MODEL,
    description="Real estate agent with walk score tool (ex01 solution).",
    instruction=(
        "You are a real estate advisor for Austin, TX.\n\n"
        "You have MCP tools auto-discovered from a pricing server, "
        "including a walk score tool. Use whichever tools are relevant "
        "to the user's question. Always call tools before giving estimates."
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
)
