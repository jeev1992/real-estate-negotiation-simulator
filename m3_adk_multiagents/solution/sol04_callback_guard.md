# Solution 4 — Add a Callback Guard

## Updated `buyer_agent/agent.py` (relevant section)

```python
from datetime import datetime, timezone

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

_BUYER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_property_tax_estimate",
}

_BUYER_BUDGET = 460_000


def buyer_guard(tool: BaseTool, args: dict, tool_context: ToolContext):
    """Combined allowlist + argument validation + logging.

    Three checks in order:
    1. Log every call (observability)
    2. Block unauthorized tools (access control)
    3. Block arguments exceeding budget (business rule)
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] TOOL CALL: {tool.name}({args})")

    # Check 1: Allowlist
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        print(f"[{timestamp}] BLOCKED: unauthorized tool '{tool.name}'")
        return {"error": f"tool '{tool.name}' is not authorized for the buyer"}

    # Check 2: Argument validation
    for key, value in args.items():
        if isinstance(value, (int, float)) and value > _BUYER_BUDGET:
            print(f"[{timestamp}] BLOCKED: {key}={value} exceeds budget")
            return {
                "error": (
                    f"argument '{key}' value ${value:,.0f} exceeds "
                    f"buyer budget of ${_BUYER_BUDGET:,}"
                )
            }

    return None  # Allow the call


# In root_agent definition:
# before_tool_callback=buyer_guard,
```

## Key takeaways

- `before_tool_callback` returns `None` to allow, or a `dict` to block (the dict becomes the tool's "result")
- The blocked result is fed back to the LLM as if the tool had run — the LLM typically adjusts its strategy
- Logging in callbacks gives you an audit trail without modifying agent instructions
- Order matters: check allowlist before argument validation (fail fast on unauthorized tools)

## Reflection answer
> Synchronous callbacks add latency to every tool call. In production:
> - Use async logging (emit to a queue, don't block on I/O)
> - Cache allowlists in memory (don't hit a database per call)
> - For argument validation at scale, consider validating in the tool itself rather than a callback, since callbacks run for ALL tools
> - For critical guardrails (budget caps), the callback approach is correct — you want to block BEFORE the tool executes
