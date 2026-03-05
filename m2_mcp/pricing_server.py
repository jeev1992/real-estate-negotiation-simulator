"""
Real Estate Pricing MCP Server
================================
An MCP server that exposes real estate pricing tools to AI agents.

MCP CONCEPT:
  This server wraps simulated real estate pricing data (in production:
  Zillow API, Redfin, MLS database) and exposes it as MCP tools.
  Any MCP-compatible agent can discover and call these tools without
  knowing where the data comes from.

TRANSPORT OPTIONS:
  stdio (default) — client spawns this as a subprocess
    python pricing_server.py

  SSE (HTTP)      — runs as standalone HTTP server, multiple clients
    python pricing_server.py --sse --port 8001

TOOLS EXPOSED:
  • get_market_price(address, property_type)
      Returns comparable sales, estimated value, price analysis

  • calculate_discount(base_price, market_condition, days_on_market)
      Returns suggested offer range, discount percentages, negotiation tips

HOW AGENTS USE THIS:
  Buyer agent: Calls get_market_price to justify offers
               Calls calculate_discount to determine offer range
  Seller agent: Calls get_market_price to understand buyer's perspective
                Calls calculate_discount to anticipate buyer's strategy
"""

import argparse
import random
from typing import Literal

# FastMCP is the Pythonic way to build MCP servers
# Install: pip install mcp
from mcp.server.fastmcp import FastMCP


# ─── Initialize FastMCP Server ────────────────────────────────────────────────

mcp = FastMCP(
    "real-estate-pricing",
    description=(
        "Provides real estate market pricing data, comparable sales analysis, "
        "and discount calculation for property negotiations in Austin, TX."
    )
)


# ─── Simulated Data Store ─────────────────────────────────────────────────────
# In production, these would be calls to Zillow API, Redfin, MLS database, etc.
# MCP abstracts this — agents don't care WHERE the data comes from.

PROPERTY_DATABASE: dict[str, dict] = {
    "742 evergreen terrace, austin, tx 78701": {
        "display_address": "742 Evergreen Terrace, Austin, TX 78701",
        "type": "single_family",
        "bedrooms": 4,
        "bathrooms": 3,
        "sqft": 2400,
        "lot_sqft": 8500,
        "year_built": 2005,
        "list_price": 485_000,
        "estimated_value": 462_000,
        "price_per_sqft": 202,
        "days_on_market": 18,
        "neighborhood": "South Austin",
        "zip_code": "78701",
        "school_rating": 8,
        "hoa_monthly": 0,
        "tax_annual": 9_800,
        "recent_upgrades": [
            "Kitchen renovation (2023) - $45,000",
            "New roof (2022) - $18,000",
            "HVAC replacement (2021) - $12,000",
        ],
        "comparable_sales": [
            {
                "address": "738 Evergreen Terrace, Austin, TX",
                "price": 458_000,
                "sqft": 2_350,
                "price_per_sqft": 195,
                "days_ago": 12,
                "bed_bath": "4/2"
            },
            {
                "address": "751 Evergreen Terrace, Austin, TX",
                "price": 471_500,
                "sqft": 2_520,
                "price_per_sqft": 187,
                "days_ago": 28,
                "bed_bath": "4/3"
            },
            {
                "address": "820 Maple Creek Dr, Austin, TX",
                "price": 456_000,
                "sqft": 2_280,
                "price_per_sqft": 200,
                "days_ago": 41,
                "bed_bath": "3/3"
            },
            {
                "address": "715 Bluebell Ave, Austin, TX",
                "price": 468_000,
                "sqft": 2_400,
                "price_per_sqft": 195,
                "days_ago": 55,
                "bed_bath": "4/3"
            },
        ]
    }
}

# Market condition data by ZIP code
MARKET_DATA: dict[str, dict] = {
    "78701": {
        "condition": "balanced",
        "inventory_months": 3.2,
        "yoy_appreciation_pct": 4.1,
        "median_days_on_market": 22,
        "list_to_sale_ratio": 0.97,  # homes sell for 97% of list
    },
    "78702": {
        "condition": "hot",
        "inventory_months": 1.5,
        "yoy_appreciation_pct": 8.3,
        "median_days_on_market": 9,
        "list_to_sale_ratio": 1.02,  # over asking in hot market
    },
    "78703": {
        "condition": "cold",
        "inventory_months": 6.8,
        "yoy_appreciation_pct": 1.2,
        "median_days_on_market": 45,
        "list_to_sale_ratio": 0.94,
    },
    "default": {
        "condition": "balanced",
        "inventory_months": 3.5,
        "yoy_appreciation_pct": 3.5,
        "median_days_on_market": 25,
        "list_to_sale_ratio": 0.96,
    }
}


# ─── MCP Tools ────────────────────────────────────────────────────────────────

@mcp.tool()
def get_market_price(
    address: str,
    property_type: str = "single_family"
) -> dict:
    """
    Get comprehensive market pricing data for a property.

    Returns comparable recent sales, estimated market value, price per sqft,
    and market analysis to help agents understand fair market value.

    MCP NOTE: This tool abstracts the complexity of querying real estate
    databases. Agents call this tool without knowing whether data comes
    from Zillow, Redfin, MLS, or a local database.

    Args:
        address: Full property address (e.g., "742 Evergreen Terrace, Austin, TX 78701")
        property_type: Type of property — single_family, condo, townhouse, multi_family

    Returns:
        Comprehensive pricing data including comparables, market analysis,
        and negotiation context.
    """
    # Normalize address for lookup
    normalized = address.lower().strip()

    # Look up known property
    property_data = PROPERTY_DATABASE.get(normalized)

    if not property_data:
        # Generate realistic data for unknown addresses
        # In production: call Zillow/Redfin API here
        base_price = random.randint(380_000, 550_000)
        sqft = random.randint(1_800, 3_200)
        estimated_value = int(base_price * random.uniform(0.93, 0.99))
        comp_base = estimated_value

        property_data = {
            "display_address": address,
            "type": property_type,
            "bedrooms": random.randint(3, 5),
            "bathrooms": random.randint(2, 4),
            "sqft": sqft,
            "lot_sqft": random.randint(6_000, 12_000),
            "year_built": random.randint(1990, 2020),
            "list_price": base_price,
            "estimated_value": estimated_value,
            "price_per_sqft": int(base_price / sqft),
            "days_on_market": random.randint(5, 60),
            "neighborhood": "Austin Metro",
            "zip_code": "78701",
            "school_rating": random.randint(6, 9),
            "hoa_monthly": 0,
            "tax_annual": int(base_price * 0.020),
            "recent_upgrades": [],
            "comparable_sales": [
                {
                    "address": f"Similar Property {chr(65 + i)}, Austin, TX",
                    "price": int(comp_base * random.uniform(0.95, 1.05)),
                    "sqft": sqft + random.randint(-200, 200),
                    "price_per_sqft": int(comp_base / sqft),
                    "days_ago": random.randint(10, 60),
                    "bed_bath": "4/3"
                }
                for i in range(4)
            ]
        }

    # Calculate market statistics
    comp_prices = [c["price"] for c in property_data["comparable_sales"]]
    avg_comp_price = int(sum(comp_prices) / len(comp_prices))
    median_comp_price = sorted(comp_prices)[len(comp_prices) // 2]
    price_variance_pct = round(
        (property_data["list_price"] - avg_comp_price) / avg_comp_price * 100, 1
    )

    # Get market condition for this ZIP
    zip_code = property_data.get("zip_code", "default")
    market = MARKET_DATA.get(zip_code, MARKET_DATA["default"])

    return {
        "address": property_data["display_address"],
        "property_details": {
            "type": property_data["type"],
            "bedrooms": property_data["bedrooms"],
            "bathrooms": property_data["bathrooms"],
            "sqft": property_data["sqft"],
            "lot_sqft": property_data.get("lot_sqft"),
            "year_built": property_data["year_built"],
            "school_district_rating": property_data.get("school_rating"),
            "hoa_monthly": property_data.get("hoa_monthly", 0),
            "annual_property_tax": property_data.get("tax_annual"),
            "recent_upgrades": property_data.get("recent_upgrades", []),
        },
        "pricing": {
            "list_price": property_data["list_price"],
            "estimated_market_value": property_data["estimated_value"],
            "price_per_sqft": property_data["price_per_sqft"],
            "days_on_market": property_data["days_on_market"],
        },
        "comparable_sales": property_data["comparable_sales"],
        "market_statistics": {
            "avg_comparable_price": avg_comp_price,
            "median_comparable_price": median_comp_price,
            "price_vs_comps_pct": price_variance_pct,
            "is_overpriced": price_variance_pct > 3,
            "valuation_summary": (
                f"Property is listed {'above' if price_variance_pct > 0 else 'below'} "
                f"comparable sales by {abs(price_variance_pct):.1f}%"
            ),
        },
        "market_conditions": {
            "zip_code": zip_code,
            "market_type": market["condition"],
            "inventory_months_supply": market["inventory_months"],
            "yoy_appreciation_pct": market["yoy_appreciation_pct"],
            "median_days_on_market": market["median_days_on_market"],
            "typical_list_to_sale_ratio": market["list_to_sale_ratio"],
        },
        "negotiation_context": {
            "fair_market_value_range": {
                "low": int(avg_comp_price * 0.97),
                "high": int(avg_comp_price * 1.03),
            },
            "buyer_recommendation": (
                f"Fair offer range: ${int(avg_comp_price * 0.97):,} – ${int(avg_comp_price * 1.03):,}. "
                f"Property is {'overpriced' if price_variance_pct > 3 else 'fairly priced'} "
                f"relative to recent sales."
            ),
        },
        "data_source": "MCP Pricing Server (simulated MLS/Zillow data)",
    }


@mcp.tool()
def calculate_discount(
    base_price: float,
    market_condition: Literal["hot", "balanced", "cold"] = "balanced",
    days_on_market: int = 0,
    property_condition: Literal["excellent", "good", "fair", "poor"] = "good"
) -> dict:
    """
    Calculate appropriate discount range based on market conditions.

    Provides data-driven discount recommendations that agents can use
    to formulate and justify their negotiation positions.

    MCP NOTE: This tool encapsulates pricing business logic that would
    otherwise be duplicated across agents. By exposing it as an MCP tool,
    both the buyer (to determine offer) and seller (to anticipate buyer
    strategy) can use the same logic from the same source.

    Args:
        base_price: The listing price to calculate discount from
        market_condition: Market heat — "hot" (seller's market), "balanced", or "cold" (buyer's market)
        days_on_market: Days the property has been listed (longer = more negotiable)
        property_condition: Physical condition of the property

    Returns:
        Discount analysis with suggested offer ranges and negotiation tips.
    """
    # Base discount rates by market condition
    base_rates: dict[str, dict[str, float]] = {
        "hot":      {"min": 0.000, "max": 0.020},   # 0–2%   (seller's market)
        "balanced": {"min": 0.020, "max": 0.050},   # 2–5%
        "cold":     {"min": 0.050, "max": 0.100},   # 5–10%  (buyer's market)
    }

    # Days on market adjustment (each tier adds to discount room)
    dom_adjustment: float = 0.0
    if days_on_market >= 90:
        dom_adjustment = 0.040
    elif days_on_market >= 60:
        dom_adjustment = 0.025
    elif days_on_market >= 30:
        dom_adjustment = 0.012

    # Property condition adjustment
    condition_adjustment: dict[str, float] = {
        "excellent": -0.010,  # less room to negotiate
        "good":       0.000,
        "fair":       0.020,  # more room to negotiate
        "poor":       0.050,  # significant discount expected
    }
    cond_adj = condition_adjustment.get(property_condition, 0.0)

    # Calculate total discount range
    rates = base_rates.get(market_condition, base_rates["balanced"])
    min_discount = max(0, rates["min"] + dom_adjustment + cond_adj)
    max_discount = min(0.20, rates["max"] + dom_adjustment + cond_adj)  # cap at 20%

    # Calculate price points
    offer_conservative = int(base_price * (1 - min_discount))
    offer_moderate = int(base_price * (1 - (min_discount + max_discount) / 2))
    offer_aggressive = int(base_price * (1 - max_discount))
    offer_ultra_aggressive = int(base_price * (1 - max_discount - 0.02))

    # Generate negotiation tips based on conditions
    tips: list[str] = []

    if market_condition == "hot":
        tips.extend([
            "Market favors sellers — avoid lowball offers",
            "Consider waiving minor contingencies to strengthen offer",
            "Be prepared for multiple offer situations",
            "Move quickly; good properties don't last",
        ])
    elif market_condition == "cold":
        tips.extend([
            "Market favors buyers — room for aggressive negotiation",
            "Request all inspection contingencies",
            "Ask seller to cover closing costs",
            "Request repairs or price reductions after inspection",
        ])
    else:
        tips.extend([
            "Balanced market — reasonable negotiation expected",
            "Keep standard contingencies (inspection, financing)",
            "Use comparable sales data to justify your offer",
        ])

    if days_on_market > 30:
        tips.append(
            f"Property has been on market {days_on_market} days — "
            "seller may be more motivated to negotiate"
        )

    if property_condition in ("fair", "poor"):
        tips.append("Request inspection and estimate repair costs before finalizing offer")

    return {
        "inputs": {
            "base_price": base_price,
            "market_condition": market_condition,
            "days_on_market": days_on_market,
            "property_condition": property_condition,
        },
        "discount_analysis": {
            "min_discount_pct": round(min_discount * 100, 1),
            "max_discount_pct": round(max_discount * 100, 1),
            "dom_adjustment_pct": round(dom_adjustment * 100, 1),
            "condition_adjustment_pct": round(cond_adj * 100, 1),
        },
        "suggested_offer_prices": {
            "conservative": offer_conservative,
            "moderate": offer_moderate,
            "aggressive": offer_aggressive,
            "ultra_aggressive": offer_ultra_aggressive,
        },
        "expected_closing_price": int(base_price * (1 - min_discount - 0.01)),
        "reasoning": (
            f"In a {market_condition} market with {days_on_market} DOM and {property_condition} "
            f"property condition: expect {min_discount*100:.0f}–{max_discount*100:.0f}% "
            f"below asking price. Typical closing: ${int(base_price * (1 - min_discount - 0.01)):,}."
        ),
        "negotiation_tips": tips,
        "data_source": "MCP Pricing Server (simulated market analysis)",
    }


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Real Estate Pricing MCP Server — supports stdio and SSE transports"
    )
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Use SSE transport instead of stdio. Runs as HTTP server."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port number for SSE transport (default: 8001)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for SSE transport (default: 0.0.0.0)"
    )
    args = parser.parse_args()

    if args.sse:
        # SSE mode: run as standalone HTTP server
        # Multiple agents can connect to this same server instance
        print(f"🏠 Real Estate Pricing MCP Server (SSE mode)")
        print(f"   Listening on: http://{args.host}:{args.port}/sse")
        print(f"   Connect via: SseServerParams(url='http://localhost:{args.port}/sse')")
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        # stdio mode: communicate via stdin/stdout (default)
        # Client spawns this script as a subprocess
        # Used by: simple_agents version and ADK with StdioServerParameters
        mcp.run()
