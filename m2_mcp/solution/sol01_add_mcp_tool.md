# Solution 1: Add a New MCP Tool

## How to apply

The tool is already in `m2_mcp/pricing_server.py` as a **commented-out block** marked with `── Exercise 1 ──`. Search for `Exercise 1` and uncomment the entire `get_property_tax_estimate` function (including the `@mcp.tool()` decorator).

## The uncommented code

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

## Why this works
The `@mcp.tool()` decorator automatically:
- Registers the function name as the tool name
- Inspects the type hints to generate the JSON Schema for parameters
- Serializes the return dict as a JSON text content block

No configuration file or registration step is needed — the decorator handles discovery.

## Verify
```bash
python m2_mcp/pricing_server.py
```
Server starts with the new tool registered alongside `get_market_price` and `calculate_discount`.
