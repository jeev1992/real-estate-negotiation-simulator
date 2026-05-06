# Exercise 1 — Add a `get_walk_score` Tool to the Pricing Server `[Starter]`

## Goal

Add a new MCP tool `get_walk_score(zip_code: str)` to `m2_mcp/pricing_server.py`. Then verify that an LLM agent can discover and use it without any agent-side changes.

This is the most common day-one task you'll do with MCP at work: **expose a new capability from a server, watch every consumer pick it up automatically.**

## What you're building

A tool that returns a walkability + transit + bike score for a Texas ZIP code. Hardcode realistic values for `78701`, `78702`, `78703`; provide a sensible fallback for everything else.

```python
@mcp.tool()
def get_walk_score(zip_code: str) -> dict:
    """Get walkability, transit, and bike scores for a US ZIP code (0-100 scale)."""
    ...
```

Return shape:
```python
{
    "zip_code": "78701",
    "walk_score": 82,           # 0-100
    "transit_score": 47,
    "bike_score": 71,
    "walk_category": "Very Walkable",
    "summary": "Most errands can be accomplished on foot.",
}
```

## Steps

1. Open `m2_mcp/pricing_server.py`.
2. Add the new tool with `@mcp.tool()` decorator. Match the style of the existing `get_market_price` and `calculate_discount` tools.
3. Verify the server registers it:
   ```bash
   python m2_mcp/pricing_server.py --check
   ```
   Output should list **three** tools now.
4. Run the agent and observe:
   ```bash
   adk web m2_mcp/solution/ex01_walk_score_tool/
   ```
   Pick **`walk_score_agent`** from the dropdown.
5. Test with these queries in sequence:

   | Query | Expected tool call | Why it matters |
   |---|---|---|
   | *"Is the 78701 area walkable?"* | `get_walk_score` | The LLM discovers and calls your new tool automatically |
   | *"What's 742 Evergreen Terrace worth?"* | `get_market_price` | Proves existing tools still work — you didn't break anything |
   | *"Is 742 Evergreen Terrace fairly priced and walkable?"* | `get_market_price` + `get_walk_score` | LLM composes **two** tools for a multi-faceted question |
   | *"Can I get some reduction in price as I have a $500K budget in the 78701 area, and how easy is it there to get things nearby without using a car?"* | `calculate_discount` + `get_walk_score` | LLM picks `calculate_discount` for pricing strategy **and** your new tool for walkability — without being told which tools exist |

6. Open the **Info tab** in the `adk web` UI — it should show 3 tools: `get_market_price`, `calculate_discount`, `get_walk_score`.

## Verify

- `--check` shows 3 tools: `get_market_price`, `calculate_discount`, `get_walk_score`
- The agent calls `get_walk_score` for walkability questions **without any change to `agent.py`**
- The agent calls `get_market_price` for pricing questions
- The agent calls `calculate_discount` + `get_walk_score` together when asked about both discount strategy and walkability
- The Info tab lists all three tools

## Reflection

When you ran `--check`, the new tool appeared automatically. You did not register it anywhere. **What about the function makes it discoverable to the MCP server, the JSON Schema, and the LLM — all three?**

Hint: trace the path from your Python function to what the LLM sees. There are roughly four transformations.

---

> **Solution:** see `solution/ex01_walk_score_tool/` for the complete, runnable code. The instructor will walk through it live during the review session.
