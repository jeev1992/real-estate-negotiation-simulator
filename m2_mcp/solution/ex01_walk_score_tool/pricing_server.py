"""
Solution — Exercise 1: pricing_server.py with get_walk_score added
====================================================================

Same as the canonical m2_mcp/pricing_server.py, plus one new tool:

  • get_walk_score(zip_code) → walkability, transit, bike scores

To demo:

  # Verify the new tool registers (no API key needed):
  python m2_mcp/solution/ex01_walk_score_tool/pricing_server.py --check
  # Expect: 3 tools listed.

  # Run as MCP server alongside an agent:
  adk web m3_adk_multiagents/adk_demos/d02_mcp_tools/
  # Then ask: "Is the neighborhood around 742 Evergreen Terrace walkable?"
"""

import argparse
import random
import sys
from typing import Literal

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("real-estate-pricing")


# ─── Existing tools (abbreviated for the solution — full data lives in
#     m2_mcp/pricing_server.py; we re-implement only what's needed for demo) ──

PROPERTY_DATABASE: dict[str, dict] = {
    "742 evergreen terrace, austin, tx 78701": {
        "display_address": "742 Evergreen Terrace, Austin, TX 78701",
        "list_price": 485_000,
        "estimated_value": 462_000,
        "zip_code": "78701",
    }
}


@mcp.tool()
def get_market_price(address: str, property_type: str = "single_family") -> dict:
    """Return market price data for an address. (Abbreviated — see canonical
    pricing_server.py for the full version with comparable sales, etc.)"""
    data = PROPERTY_DATABASE.get(address.lower().strip(), {
        "display_address": address,
        "list_price": 485_000,
        "estimated_value": 462_000,
        "zip_code": "78701",
    })
    return {
        "address": data["display_address"],
        "list_price": data["list_price"],
        "estimated_value": data["estimated_value"],
        "zip_code": data["zip_code"],
    }


@mcp.tool()
def calculate_discount(
    base_price: float,
    market_condition: Literal["hot", "balanced", "cold"] = "balanced",
    days_on_market: int = 0,
    property_condition: Literal["excellent", "good", "fair", "poor"] = "good",
) -> dict:
    """Return suggested offer discount. (Abbreviated — see canonical version.)"""
    base = {"hot": 0.01, "balanced": 0.04, "cold": 0.07}[market_condition]
    return {
        "suggested_discount_pct": round(base * 100, 1),
        "suggested_offer": int(base_price * (1 - base)),
    }


# ─── NEW TOOL — Exercise 1 ────────────────────────────────────────────────────
#
# Style note: matches the existing tools exactly:
#   • @mcp.tool() decorator — auto-registers it
#   • Type-hinted parameters — auto-generates JSON Schema
#   • Docstring — becomes the tool description the LLM reads
#   • Returns dict — FastMCP wraps it as TextContent over the wire
#
# The student should write THIS function. Everything else is unchanged.

WALK_SCORE_DATA: dict[str, dict] = {
    "78701": {
        # Downtown Austin — dense, walkable, decent transit
        "walk_score": 82,
        "transit_score": 47,
        "bike_score": 71,
    },
    "78702": {
        # East Austin — very walkable, hot district
        "walk_score": 78,
        "transit_score": 41,
        "bike_score": 68,
    },
    "78703": {
        # Clarksville — quiet, less walkable, more car-dependent
        "walk_score": 56,
        "transit_score": 28,
        "bike_score": 49,
    },
}


def _categorize_walk_score(score: int) -> tuple[str, str]:
    """Map a 0-100 walk score to a category and summary, matching the
    public WalkScore methodology."""
    if score >= 90:
        return "Walker's Paradise", "Daily errands do not require a car."
    if score >= 70:
        return "Very Walkable", "Most errands can be accomplished on foot."
    if score >= 50:
        return "Somewhat Walkable", "Some errands can be accomplished on foot."
    if score >= 25:
        return "Car-Dependent", "Most errands require a car."
    return "Car-Dependent", "Almost all errands require a car."


@mcp.tool()
def get_walk_score(zip_code: str) -> dict:
    """Get walkability, transit, and bike scores for a US ZIP code.

    Each score is on a 0-100 scale, where 100 is best. Walk Score measures
    how friendly an area is to walking; Transit Score measures access to
    public transportation; Bike Score measures infrastructure for cycling.

    Returns a dict with all three scores plus a human-readable category and
    one-line summary of the walk score.

    Args:
        zip_code: A 5-digit US ZIP code (e.g., "78701").

    Returns:
        {
          "zip_code": str,
          "walk_score": int (0-100),
          "transit_score": int (0-100),
          "bike_score": int (0-100),
          "walk_category": str,
          "summary": str,
        }
    """
    # Step 1) Look up known ZIP first for deterministic demo behavior.
    data = WALK_SCORE_DATA.get(zip_code)

    if data is None:
        # Step 2) Fallback for unknown ZIPs — synthesize plausible values
        # so the demo continues to work for any input.
        data = {
            "walk_score": random.randint(30, 75),
            "transit_score": random.randint(15, 50),
            "bike_score": random.randint(25, 65),
        }

    # Step 3) Derive the human-readable layer on top of raw scores.
    category, summary = _categorize_walk_score(data["walk_score"])

    return {
        "zip_code": zip_code,
        "walk_score": data["walk_score"],
        "transit_score": data["transit_score"],
        "bike_score": data["bike_score"],
        "walk_category": category,
        "summary": summary,
    }


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="Verify all tools register, then exit.")
    parser.add_argument("--sse", action="store_true")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    if args.check:
        tools = list(mcp._tool_manager._tools.keys())
        print(f"pricing_server (ex01 solution) OK  tools={tools}")
        sys.exit(0)
    elif args.sse:
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        mcp.run()
