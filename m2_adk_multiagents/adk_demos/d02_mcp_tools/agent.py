"""
Demo 02 — MCP Tools in ADK (remote server, with authentication)
=================================================================
LlmAgent with MCPToolset auto-discovering tools from the pricing MCP server —
this time a REMOTE server over Streamable HTTP that requires a signed token.
ADK connects, sends the token on every request, discovers the tools via the
MCP protocol, and offers them to the LLM as function-calling tools.

ADK CONCEPTS:
  - MCPToolset: connects to an MCP server and discovers tools automatically
  - StreamableHTTPConnectionParams: URL + headers (here the bearer token)
  - The LLM sees MCP tools exactly like local function tools

WHAT THE SERVER ENFORCES (m1_mcp/pricing_server.py --http):
  Authentication   no / invalid / expired token → 401, no tools at all
  Server authz     token without pricing:read  → 403
  Tool authz       get_market_price needs pricing:read,
                   calculate_discount needs pricing:analyze

Run (two terminals):
    python m1_mcp/pricing_server.py --http                     # terminal 1
    python utils/pricing_auth.py --role buyer --write-env      # buyer token → .env
    adk web m2_adk_multiagents/adk_demos/                       # terminal 2

Switch identity: mint a different role with --write-env and restart adk web.
"""

import os

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StreamableHTTPConnectionParams,
)
from google.genai import types

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")
PRICING_MCP_URL = os.environ.get("PRICING_MCP_URL", "http://127.0.0.1:8001/mcp")
PRICING_MCP_TOKEN = os.environ.get("PRICING_MCP_TOKEN", "").strip()

# No token → no Authorization header, and the server answers 401.
_headers = {"Authorization": f"Bearer {PRICING_MCP_TOKEN}"} if PRICING_MCP_TOKEN else {}


def _require_tools(callback_context: CallbackContext, llm_request: LlmRequest):
    """before_model: if the server rejected us (401/403), ADK loads no tools.

    Without tools the model would cheerfully promise to "look it up", so we
    answer for it instead of calling the LLM.
    """
    if llm_request.tools_dict:
        return None
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=(
        f"I can't reach the pricing tools: the MCP server at {PRICING_MCP_URL} rejected "
        "the connection or is not running, so no tools were loaded. Check that the server "
        "is started with --http and that PRICING_MCP_TOKEN is a valid, unexpired token "
        "(python utils/pricing_auth.py --role buyer --write-env), then restart adk web."
    ))]))

root_agent = LlmAgent(
    name="mcp_tools_agent",
    model=MODEL,
    description="Real estate pricing agent using a remote, token-protected MCP server.",
    instruction=(
        "You are a real estate pricing analyst for Austin, TX.\n\n"
        "You have MCP tools that were auto-discovered from a pricing server. "
        "You don't need to know their names in advance — ADK discovered them "
        "for you at startup via the MCP protocol.\n\n"
        "Always call your available tools before giving any estimates. "
        "Reference the tool results in your response.\n\n"
        "If a tool returns an authorization error, tell the user exactly which "
        "permission (scope) is missing. Never estimate the answer yourself instead."
    ),
    tools=[
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=PRICING_MCP_URL,
                headers=_headers,
                timeout=30.0,
            )
        )
    ],
    before_model_callback=_require_tools,
)
