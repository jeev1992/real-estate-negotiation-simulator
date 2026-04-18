"""
Real Estate Inventory MCP Server
==================================
An MCP server exposing real estate inventory and seller constraint data.

MCP CONCEPT:
  This server simulates an MLS (Multiple Listing Service) inventory system.
  It exposes two tools — one public (inventory data both agents can use)
  and one restricted (seller's minimum price, only the seller should access).

  In a real system, MCP auth would enforce this restriction.
  In our workshop, it's a teaching convention: the buyer agent simply
  doesn't connect to get_minimum_acceptable_price.

TOOLS EXPOSED:
  • get_inventory_level(zip_code)
      Returns: active listings, days on market avg, market condition,
               absorption rate — publicly available market data

  • get_minimum_acceptable_price(property_id)
      Returns: the seller's absolute floor price and reasoning
      ⚠️  In real estate, ONLY the seller's agent knows this.
      Our seller agent uses this; buyer agent does NOT connect to it.

TRANSPORT:
  stdio (default): python inventory_server.py
  SSE:             python inventory_server.py --sse --port 8002
"""

import argparse
import random
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP


# ─── Initialize Server ────────────────────────────────────────────────────────

mcp = FastMCP(
    "real-estate-inventory"
)


# ─── Simulated Inventory Database ─────────────────────────────────────────────

INVENTORY_DATA: dict[str, dict] = {
    "78701": {
        "zip_code": "78701",
        "city": "Austin",
        "neighborhood": "South Austin",
        "active_listings": 47,
        "new_listings_30_days": 18,
        "closed_sales_30_days": 15,
        "avg_days_on_market": 22,
        "median_days_on_market": 18,
        "absorption_rate_months": 3.1,
        "price_reductions_pct": 12,  # % of listings with price drops
        "list_to_sale_ratio": 0.971,
        "market_condition": "balanced",
        "buyer_competition_level": "moderate",
        "notes": "Balanced market with moderate buyer activity. Standard negotiation expected.",
    },
    "78702": {
        "zip_code": "78702",
        "city": "Austin",
        "neighborhood": "East Austin",
        "active_listings": 23,
        "new_listings_30_days": 22,
        "closed_sales_30_days": 21,
        "avg_days_on_market": 9,
        "median_days_on_market": 7,
        "absorption_rate_months": 1.1,
        "price_reductions_pct": 3,
        "list_to_sale_ratio": 1.018,
        "market_condition": "hot",
        "buyer_competition_level": "very_high",
        "notes": "Very hot market. Multiple offers common. Buyers should act fast and offer strong.",
    },
    "78703": {
        "zip_code": "78703",
        "city": "Austin",
        "neighborhood": "Clarksville",
        "active_listings": 89,
        "new_listings_30_days": 14,
        "closed_sales_30_days": 13,
        "avg_days_on_market": 48,
        "median_days_on_market": 42,
        "absorption_rate_months": 6.8,
        "price_reductions_pct": 31,
        "list_to_sale_ratio": 0.943,
        "market_condition": "cold",
        "buyer_competition_level": "low",
        "notes": "Buyer's market. Negotiate aggressively. Sellers are motivated.",
    },
}

# Seller constraint data — ONLY the seller should access this
# In real life: this comes from the seller's listing agreement
SELLER_CONSTRAINTS: dict[str, dict] = {
    "742-evergreen-austin-78701": {
        "property_id": "742-evergreen-austin-78701",
        "display_address": "742 Evergreen Terrace, Austin, TX 78701",
        "list_price": 485_000,
        "minimum_acceptable_price": 445_000,
        "ideal_price": 465_000,
        "seller_motivation_level": "moderate",  # low | moderate | high
        "must_close_by": "2025-03-31",
        "seller_situation": "Seller has purchased another home and needs proceeds",
        "price_floor_reasoning": (
            "Seller owes $380,000 on mortgage. After agent commission (3%) "
            "and closing costs (~$8,000), seller needs minimum $445,000 to "
            "cover all obligations and have funds for the new home down payment."
        ),
        "concessions_willing_to_make": [
            "Cover buyer's title insurance ($1,200)",
            "Include all appliances",
            "Flexible closing date within 30–60 days",
        ],
        "dealbreakers": [
            "Cannot go below $445,000 — mortgage payoff requirement",
            "Cannot delay closing past March 31, 2025",
        ],
    }
}


# ─── MCP Tools ────────────────────────────────────────────────────────────────

@mcp.tool()
def get_inventory_level(zip_code: str) -> dict:
    """
    Get real estate inventory and market activity data for a ZIP code.

    This is PUBLIC market data — both buyer and seller agents can use this
    to understand market conditions and calibrate their negotiation strategy.

    MCP NOTE: In production, this would call the MLS API or Realtor.com.
    MCP abstracts this — agents call the same tool regardless of the
    underlying data source.

    Args:
        zip_code: 5-digit ZIP code (e.g., "78701" for South Austin)

    Returns:
        Inventory statistics, market condition, and negotiation context.
    """
    # Step 1) Lookup known ZIP data for deterministic workshop outputs.
    data = INVENTORY_DATA.get(zip_code)

    if not data:
        # Step 2) Fallback for unknown ZIPs so tool stays useful for ad-hoc demos.
        # In production this would query MLS/provider APIs.
        absorption = round(random.uniform(2.0, 5.0), 1)
        dom = random.randint(15, 45)
        active = random.randint(30, 100)
        closed = random.randint(10, 30)

        condition = (
            "hot" if absorption < 2 else
            "cold" if absorption > 5 else
            "balanced"
        )

        data = {
            "zip_code": zip_code,
            "city": "Austin",
            "neighborhood": "Austin Metro",
            "active_listings": active,
            "new_listings_30_days": random.randint(10, 30),
            "closed_sales_30_days": closed,
            "avg_days_on_market": dom,
            "median_days_on_market": int(dom * 0.85),
            "absorption_rate_months": absorption,
            "price_reductions_pct": random.randint(8, 25),
            "list_to_sale_ratio": round(random.uniform(0.95, 1.02), 3),
            "market_condition": condition,
            "buyer_competition_level": "moderate",
            "notes": f"Data generated for {zip_code}. Absorption rate: {absorption} months.",
        }

    # Step 3) Add negotiation interpretation layer on top of raw market metrics.
    # This keeps clients simple: they receive both data and decision context.
    condition = data["market_condition"]
    buyer_leverage = {
        "hot": "Minimal — seller has leverage",
        "balanced": "Moderate — balanced negotiation",
        "cold": "Strong — buyer has leverage",
    }.get(condition, "Unknown")

    price_drop_expectation = {
        "hot": "0–2% — little room to negotiate",
        "balanced": "2–5% — typical negotiation range",
        "cold": "5–10% — significant negotiation room",
    }.get(condition, "Unknown")

    # Final MCP payload returned to caller.
    return {
        "zip_code": data["zip_code"],
        "location": {
            "city": data["city"],
            "neighborhood": data["neighborhood"],
        },
        "activity_30_days": {
            "active_listings": data["active_listings"],
            "new_listings": data["new_listings_30_days"],
            "closed_sales": data["closed_sales_30_days"],
            "absorption_rate_months": data["absorption_rate_months"],
        },
        "time_on_market": {
            "avg_days": data["avg_days_on_market"],
            "median_days": data["median_days_on_market"],
        },
        "pricing_metrics": {
            "pct_with_price_reductions": data["price_reductions_pct"],
            "list_to_sale_ratio": data["list_to_sale_ratio"],
            "typical_close_vs_list_pct": round((data["list_to_sale_ratio"] - 1) * 100, 1),
        },
        "market_assessment": {
            "condition": data["market_condition"],
            "buyer_competition": data["buyer_competition_level"],
            "market_notes": data["notes"],
        },
        "negotiation_analysis": {
            "buyer_leverage": buyer_leverage,
            "expected_price_drop_pct": price_drop_expectation,
            "urgency_for_buyer": (
                "High — act quickly" if condition == "hot" else
                "Low — take time to negotiate" if condition == "cold" else
                "Moderate — reasonable pace"
            ),
            "seller_motivation": (
                "Low" if condition == "hot" else
                "High" if condition == "cold" else
                "Moderate"
            ),
        },
        "data_source": "MCP Inventory Server (simulated MLS data)",
    }


@mcp.tool()
def get_minimum_acceptable_price(property_id: str) -> dict:
    """
    Get the seller's minimum acceptable price and constraint analysis.

    ⚠️  ACCESS CONTROL NOTE:
    In a real estate transaction, ONLY the seller's agent knows the seller's
    floor price. This tool simulates that confidential data.

    In our workshop:
    - SELLER AGENT connects to this tool (it's their agent's information)
    - BUYER AGENT does NOT connect to this tool (information asymmetry)

    In production MCP systems, access control would be enforced via:
    - API keys per agent
    - OAuth scopes
    - MCP server-level auth checks

    Args:
        property_id: Unique property identifier
                     (e.g., "742-evergreen-austin-78701")

    Returns:
        Seller's floor price, motivation level, and negotiation constraints.
    """
    # Step 1) Resolve seller-specific constraints for the property.
    constraints = SELLER_CONSTRAINTS.get(property_id)

    if not constraints:
        # Step 2) Generate fallback constraints for unknown IDs.
        # This preserves demo continuity while clearly marking simulated behavior.
        list_price = random.randint(400_000, 600_000)
        min_price = int(list_price * random.uniform(0.90, 0.95))
        ideal_price = int(list_price * random.uniform(0.96, 0.99))

        constraints = {
            "property_id": property_id,
            "display_address": f"Property {property_id}",
            "list_price": list_price,
            "minimum_acceptable_price": min_price,
            "ideal_price": ideal_price,
            "seller_motivation_level": random.choice(["low", "moderate", "high"]),
            "must_close_by": None,
            "seller_situation": "Standard sale",
            "price_floor_reasoning": (
                f"Seller's mortgage and costs require minimum ${min_price:,}."
            ),
            "concessions_willing_to_make": ["Standard concessions"],
            "dealbreakers": [f"Cannot go below ${min_price:,}"],
        }

    # Step 3) Compute negotiation room so seller agent can set strategy bounds.
    list_price = constraints["list_price"]
    min_price = constraints["minimum_acceptable_price"]
    ideal_price = constraints["ideal_price"]
    negotiation_room = list_price - min_price

    # Final payload intentionally includes both numbers and strategy hints.
    return {
        "property_id": constraints["property_id"],
        "address": constraints["display_address"],
        "pricing_constraints": {
            "list_price": list_price,
            "minimum_acceptable_price": min_price,
            "ideal_closing_price": ideal_price,
            "absolute_negotiation_room": negotiation_room,
            "negotiation_room_pct": round(negotiation_room / list_price * 100, 1),
        },
        "seller_profile": {
            "motivation_level": constraints["seller_motivation_level"],
            "must_close_by": constraints.get("must_close_by"),
            "situation": constraints["seller_situation"],
        },
        "floor_price_reasoning": constraints["price_floor_reasoning"],
        "concessions_available": constraints["concessions_willing_to_make"],
        "dealbreakers": constraints["dealbreakers"],
        "strategy_for_seller_agent": {
            "your_floor": min_price,
            "your_target": ideal_price,
            "max_concession_amount": negotiation_room,
            "recommended_opening_counter": int(list_price * 0.985),
            "increment_strategy": "Drop by $5,000–$8,000 per round until floor",
            "walk_away_trigger": f"Any offer below ${min_price:,}",
        },
        "data_source": "MCP Inventory Server — SELLER CONFIDENTIAL",
        "access_warning": (
            "This data represents the seller's confidential floor price. "
            "In production, this would be protected by MCP authentication. "
            "Only the seller's agent should access this tool."
        ),
    }


# ─── MCP Resource: read-only directory of seller floor prices ─────────────────
#
# Why a Resource instead of a Tool?
#   - Tools are *actions* the model chooses to invoke (with arguments).
#   - Resources are *documents* the host can attach as context up front.
#   The floor-prices catalog never takes arguments and is naturally a doc.

@mcp.resource("inventory://floor-prices")
def floor_prices_resource() -> str:
    """JSON catalog of seller floor prices for every known property.

    Hosts can fetch this resource and inject it into the system prompt
    so the seller agent never needs to call a tool just to know its own
    constraints.
    """
    catalog = {
        pid: {
            "address": data["display_address"],
            "list_price": data["list_price"],
            "minimum_acceptable_price": data["minimum_acceptable_price"],
            "ideal_price": data["ideal_price"],
            "motivation": data["seller_motivation_level"],
        }
        for pid, data in SELLER_CONSTRAINTS.items()
    }
    return json.dumps(catalog, indent=2)


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Real Estate Inventory MCP Server"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Import check: verify server loads correctly then exit 0. No network I/O.",
    )
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Use SSE transport (HTTP server mode)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8002,
        help="Port for SSE transport (default: 8002)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for SSE transport (default: 0.0.0.0)"
    )
    args = parser.parse_args()

    if args.check:
        # Lightweight health check for CI/scripts.
        tools = list(mcp._tool_manager._tools.keys())
        print(f"inventory_server OK  tools={tools}")
        sys.exit(0)
    elif args.sse:
        # SSE mode: long-running HTTP endpoint, suitable for multiple clients.
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        print(f"Real Estate Inventory MCP Server (SSE mode)")
        print(f"   Listening on: http://{args.host}:{args.port}/sse")
        mcp.run(transport="sse")
    else:
        # stdio mode: spawned subprocess transport (default for in-process agent orchestration).
        mcp.run()
