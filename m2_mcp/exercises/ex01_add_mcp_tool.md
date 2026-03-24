# Exercise 1: Add a New MCP Tool `[Starter]`

## Goal
Add a `get_property_tax_estimate` tool to the pricing server. This teaches you how the `@mcp.tool()` decorator exposes a Python function as a discoverable, callable tool over the MCP protocol.

## What to look for
Look at the existing tools in `m2_mcp/pricing_server.py` (`get_market_price` and `calculate_discount`). Notice how each:
- Uses the `@mcp.tool()` decorator
- Has typed parameters with defaults
- Returns a `dict` that gets serialized to JSON

Your new tool follows the same pattern.

## Steps

Open `m2_mcp/pricing_server.py`. The new tool is already in the file as a **commented-out block** marked with `── Exercise 1 ──`. Find it (search for `Exercise 1`) and uncomment the entire function, including the `@mcp.tool()` decorator.

## Verify
```bash
python m2_mcp/pricing_server.py --check
```

## Expected
Output shows 3 tools: `get_market_price`, `calculate_discount`, `get_property_tax_estimate`.
