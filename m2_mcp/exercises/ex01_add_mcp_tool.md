# Exercise 1: Add a New MCP Tool `[Starter]`

## Goal
Add a `get_property_tax_estimate` tool to the pricing server. This teaches you how the `@mcp.tool()` decorator exposes a Python function as a discoverable, callable tool over the MCP protocol.

## What to look for
Look at the existing tools in `m2_mcp/pricing_server.py` (`get_market_price` and `calculate_discount`). Notice how each:
- Uses the `@mcp.tool()` decorator
- Has typed parameters with defaults
- Returns a `dict` that gets serialized to JSON

Your new tool follows the same pattern.

## Edit
In `m2_mcp/pricing_server.py`, add this function near other `@mcp.tool()` functions:

```python
@mcp.tool()
def get_property_tax_estimate(price: float, tax_rate: float = 0.02) -> dict:
   annual_tax = int(price * tax_rate)
   return {
      "price": price,
      "tax_rate": tax_rate,
      "estimated_annual_tax": annual_tax,
   }
```

## Verify
```bash
python m2_mcp/pricing_server.py
```

## Expected
Server starts normally with the new tool registered.
