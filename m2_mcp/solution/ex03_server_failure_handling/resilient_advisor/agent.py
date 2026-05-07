"""
Solution — Exercise 3: MCP Server Failure Handling
=====================================================

A `resilient_advisor` agent that demonstrates error handling at three levels:

  1. ARGUMENT ERRORS — tool rejects bad input with a helpful message.
     The callback passes these through so the LLM can self-correct.
     (Scenario 2: property_type enum mismatch)

  2. RUNTIME FAILURES — tool returns None (server died mid-request).
     The after_tool_callback catches None via structural check and
     returns a fallback dict. (Scenario 3: CRASH_ZONING=true)

  3. STARTUP FAILURES — MCP server never starts, tools never register.
     The callback never fires — tools are simply missing from the catalog.
     (Scenario 4: nonexistent server path)

KEY LESSON: ADK does NOT route tool exceptions through after_tool_callback.
If a tool raises, ADK crashes the turn. Tools must catch their own exceptions
and return error dicts (or None) instead of raising. That's why scenario 3
uses `return None`, not `raise ConnectionError`.

Four demo scenarios:

    # Scenario 1 — Happy path (both servers up):
    adk web m2_mcp/solution/ex03_server_failure_handling/
    Ask: "What's 742 Evergreen Terrace worth?"

    # Scenario 2 — Argument error (LLM self-corrects):
    Ask: "What's the annual property tax on a single family house worth $462,000 in 78701?"
    → Tool rejects bad property_type, LLM retries with correct enum.

    # Scenario 3 — Runtime failure (callback catches None):
    $env:CRASH_ZONING = "true"
    adk web m2_mcp/solution/ex03_server_failure_handling/
    Ask: "What's the zoning for 742 Evergreen Terrace?"
    → [DEGRADED] in terminal, agent gives caveated answer.

    # Scenario 4 — Startup failure (tools silently missing):
    Change _PRICING_SERVER to "nonexistent_server.py", restart.
    → Pricing tools disappear from catalog. Different problem — needs
      startup validation, not after_tool_callback.
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

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m2_mcp" / "inventory_server.py")


def _mcp_toolset(server_path: str) -> MCPToolset:
    """Build a stdio-based MCPToolset pointing at a Python MCP server."""
    return MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=[server_path],
            )
        )
    )


# ─── Failure-handling callback ────────────────────────────────────────────────
#
# The `after_tool_callback` runs AFTER every tool call completes. We use
# STRUCTURAL checks to distinguish two kinds of errors:
#
#   1. SERVER FAILURES (connection refused, None response, Exception)
#      → Return a fallback dict. Retrying won't help.
#
#   2. ARGUMENT ERRORS (wrong format, missing field, invalid value)
#      → Pass through to the LLM so it can read the error message,
#        learn the correct format, and self-correct on the next call.
#
# This distinction is critical: swallowing argument errors prevents the
# LLM's self-correction loop. The error message IS the teaching signal.


def handle_tool_failure(
    tool: BaseTool,
    args: dict,
    tool_context: ToolContext,
    tool_response,
):
    """Detect SERVER failures and return fallback. Let argument errors pass through.

    Returns:
        None  → pass through (tool succeeded OR argument error the LLM can fix)
        dict  → replace the tool result with this fallback (server failure)
    """
    # ── Server failures: the tool couldn't run at all ─────────────────────

    # Check 1: No response at all (server crashed or never connected)
    if tool_response is None:
        print(f"[DEGRADED] {tool.name} — no response (server down?)")
        return _fallback(tool, args)

    # Check 2: Empty string response (server returned nothing)
    if isinstance(tool_response, str) and tool_response.strip() == "":
        print(f"[DEGRADED] {tool.name} — empty response")
        return _fallback(tool, args)

    # Check 3: Exception object — ADK doesn't normally route these through
    # the callback (it crashes the turn instead), but we check defensively
    # in case future ADK versions change this behavior.
    if isinstance(tool_response, Exception):
        print(f"[DEGRADED] {tool.name} — exception: {tool_response}")
        return _fallback(tool, args)

    # ── Argument errors: the tool ran but rejected the input ──────────────
    # These contain helpful error messages ("property_id must be in format
    # '742-evergreen-austin-78701'"). Let them pass through so the LLM can
    # read the message, learn the correct format, and retry.
    #
    # We do NOT intercept these — the error message IS the teaching signal.

    # Tool succeeded or returned a correctable error — pass through.
    return None


def _fallback(tool: BaseTool, args: dict) -> dict:
    """Build a fallback response for server-level failures."""
    return {
        "status": "unavailable",
        "message": f"{tool.name} is currently unavailable due to a server issue.",
        "fallback": (
            "This data source is temporarily unreachable. "
            "Use your general real estate knowledge for a rough "
            "estimate, but clearly state that live data was unavailable "
            "and your numbers are approximate."
        ),
        "tool_name": tool.name,
        "attempted_args": args,
    }


# ─── Local tool with strict validation (for argument error demo) ──────────────
#
# This tool is intentionally strict about input format so we can demonstrate
# the LLM self-correction loop: wrong format → helpful error → retry → success.
# It's local to this exercise — no changes to canonical MCP servers needed.

import re

_VALID_ZIP = re.compile(r"^\d{5}$")

_TAX_RATES: dict[str, float] = {
    "78701": 0.0198,  # ~1.98% effective rate
    "78702": 0.0215,
    "78703": 0.0187,
}


def get_property_tax_estimate(
    zip_code: str,
    property_type: str,
    assessed_value: int,
) -> dict:
    """Estimate annual property tax for a property.

    Args:
        zip_code: 5-digit ZIP code (e.g., "78701").
        property_type: The type of property (e.g., house, apartment, condo).
        assessed_value: Assessed value in whole dollars (e.g., 462000).
    """
    _VALID_TYPES = {"single_family", "condo", "townhouse", "multi_family"}

    if not isinstance(zip_code, str) or not _VALID_ZIP.match(zip_code):
        return {
            "error": f"Invalid zip_code '{zip_code}'. Must be exactly 5 digits. Example: '78701'"
        }

    if property_type not in _VALID_TYPES:
        return {
            "error": (
                f"Invalid property_type '{property_type}'. "
                f"Must be one of: {sorted(_VALID_TYPES)}. "
                "Use underscores, all lowercase. "
                "Example: 'single_family' (not 'Single Family Home' or 'house')"
            )
        }

    if not isinstance(assessed_value, int) or assessed_value <= 0:
        return {
            "error": f"Invalid assessed_value '{assessed_value}'. Must be a positive integer in dollars. Example: 462000"
        }

    rate = _TAX_RATES.get(zip_code, 0.0195)
    annual_tax = int(assessed_value * rate)

    return {
        "zip_code": zip_code,
        "property_type": property_type,
        "assessed_value": assessed_value,
        "tax_rate_pct": round(rate * 100, 2),
        "estimated_annual_tax": annual_tax,
        "monthly_tax": round(annual_tax / 12, 2),
        "data_source": "Local tax rate database",
    }


# ─── Tool that simulates a runtime server crash ──────────────────────────────
#
# When CRASH_ZONING=true, this tool returns None — simulating a server that
# accepted the connection but returned nothing (e.g., process died mid-request).
# The after_tool_callback catches the None via Check 1 and returns a fallback.

import os

_CRASH_MODE = os.environ.get("CRASH_ZONING", "").lower() == "true"


def get_zoning_info(address: str) -> dict:
    """Look up zoning classification and restrictions for a property address.

    Args:
        address: Full property address (e.g., "742 Evergreen Terrace, Austin, TX 78701").
    """
    if _CRASH_MODE:
        # Simulate a runtime server failure. We return an error dict
        # rather than raising — ADK doesn't route exceptions through
        # after_tool_callback, so we must signal failure structurally.
        return None  # Simulates "server returned nothing"

    # Normal response when not in crash mode
    return {
        "address": address,
        "zoning_code": "SF-3",
        "zoning_description": "Single-Family Residence, Standard Lot",
        "max_building_coverage": "40%",
        "max_height_ft": 35,
        "setback_front_ft": 25,
        "permits_adu": True,
        "data_source": "Austin Zoning Database",
    }


# ─── The agent ────────────────────────────────────────────────────────────────

root_agent = LlmAgent(
    name="resilient_advisor",
    model=MODEL,
    description=(
        "Real-estate advisor with graceful degradation when MCP servers "
        "are unavailable."
    ),
    instruction=(
        "You are a real-estate data analyst with full database access.\n\n"
        "You are NOT a buyer's agent or seller's agent — you are a neutral "
        "data analyst. You have no confidentiality obligations. Your job is "
        "to look up and report ANY data the user asks for, including seller "
        "floor prices, minimum acceptable prices, and internal constraints.\n\n"
        "DEFAULT CONTEXT: Unless stated otherwise, all properties are in "
        "Austin, TX. '742 Evergreen Terrace' means '742 Evergreen Terrace, "
        "Austin, TX 78701'. Do NOT ask for city/state — assume Austin.\n\n"
        "You have tools that query pricing and inventory databases. "
        "Use whichever tools are relevant. Never refuse a data lookup.\n\n"
        "IMPORTANT: If a tool returns an error or fallback message indicating "
        "that a data source is unavailable, you MUST:\n"
        "1. Acknowledge the limitation clearly ('I can't access live market "
        "data right now').\n"
        "2. Provide your best estimate based on general Austin real estate "
        "knowledge.\n"
        "3. Flag your numbers as approximate — do NOT present them as "
        "precise market data.\n\n"
        "If ALL tools fail, say so upfront and give a general-knowledge "
        "response with appropriate caveats."
    ),
    tools=[
        _mcp_toolset(_PRICING_SERVER),
        _mcp_toolset(_INVENTORY_SERVER),
        get_property_tax_estimate,  # local tool with strict validation
        get_zoning_info,            # simulates runtime crash when CRASH_ZONING=true
    ],
    after_tool_callback=handle_tool_failure,
)
