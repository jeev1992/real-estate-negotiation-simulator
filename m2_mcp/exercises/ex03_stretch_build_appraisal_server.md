# Exercise 3 — Build an Appraisal MCP Server `[Stretch]`

## Goal
Build a third MCP server (`appraisal_server.py`) that provides comparable sales data, then connect it to the seller agent. This teaches you how to build an **MCP server from scratch** and how information asymmetry works — the seller gets appraisal data the buyer doesn't have access to.

## Why this matters
In real negotiations, sellers often have access to professional appraisals with comparable sales data (**comps**). This data asymmetry is intentional: the seller knows what nearby homes sold for, which helps them justify their price. The buyer only has public market data (from the pricing server).

## Steps

### Step 1 — Create the server

Create `m2_mcp/appraisal_server.py` with two tools:

```python
"""
Appraisal MCP Server — Comparable Sales Data
=============================================
Provides comparable sales ("comps") data for seller agents.
Seller-only access: demonstrates information asymmetry.

Run:
  python m2_mcp/appraisal_server.py
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("appraisal-server")


@mcp.tool()
def get_comparable_sales(address: str, radius_miles: float = 1.0) -> dict:
    """
    Return recent comparable sales near the given property.
    In production, this would query an MLS or public records API.
    """
    # Simulated comps for 742 Evergreen Terrace area
    comps = [
        {"address": "738 Evergreen Terrace", "sold_price": 472_000,
         "sold_date": "2025-11-15", "sqft": 2350, "beds": 4, "baths": 3},
        {"address": "801 Oak Lane", "sold_price": 489_000,
         "sold_date": "2025-10-22", "sqft": 2500, "beds": 4, "baths": 3},
        {"address": "612 Maple Drive", "sold_price": 465_000,
         "sold_date": "2025-12-01", "sqft": 2200, "beds": 3, "baths": 2},
    ]
    avg_price = sum(c["sold_price"] for c in comps) / len(comps)
    avg_per_sqft = sum(c["sold_price"] / c["sqft"] for c in comps) / len(comps)

    return {
        "address": address,
        "radius_miles": radius_miles,
        "comparable_sales": comps,
        "average_sold_price": round(avg_price),
        "average_price_per_sqft": round(avg_per_sqft, 2),
        "data_source": "simulated_mls",
    }


@mcp.tool()
def get_appraisal_estimate(address: str, sqft: int = 2400) -> dict:
    """
    Return an appraisal value estimate based on comps and square footage.
    """
    # Use simulated comp data to estimate value
    avg_per_sqft = 198.50  # From our simulated comps
    estimated_value = round(avg_per_sqft * sqft)

    return {
        "address": address,
        "sqft": sqft,
        "price_per_sqft": avg_per_sqft,
        "estimated_value": estimated_value,
        "confidence": "moderate",
        "note": "Based on 3 comparable sales within 1 mile, last 90 days",
    }


if __name__ == "__main__":
    import sys
    if "--sse" in sys.argv:
        mcp.run(transport="sse")
    else:
        mcp.run()
```

### Step 2 — Connect to the seller agent

In `m3_langgraph_multiagents/seller_simple.py`, add the appraisal server to the seller's MCP planner prompt so it can query comps when deciding counter-offer prices.

You'll need to:
1. Add a `call_appraisal_mcp()` helper (similar to `call_pricing_mcp()` and `call_inventory_mcp()`)
2. Add the new tools to `SELLER_MCP_PLANNER_PROMPT`
3. Handle the new tool calls in `_gather_mcp_context()`

### Step 3 — Test the full pipeline

```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 3
```

Watch for the seller referencing comparable sales in its counter-offer messages.

## Verify
- `python m2_mcp/appraisal_server.py` starts without errors
- The seller agent can call `get_comparable_sales` and `get_appraisal_estimate`
- The seller's counter-offers reference comp data (e.g., "nearby homes sold for...")

## Reflection question
> You now have three MCP servers: pricing (buyer), inventory (seller), and appraisal (seller). The buyer has access to 1 server; the seller has access to 3. How does this information asymmetry affect the negotiation dynamic? Is it realistic?
