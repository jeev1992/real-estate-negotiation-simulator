# Exercise 4 — Add a Callback Guard `[Core]`

## Goal
Add a `before_tool_callback` to the buyer agent (`negotiation_agents/buyer_agent/`) that logs every tool call with a timestamp and blocks any tool call where the arguments contain a price above the buyer's budget ($460,000). This reinforces Demo 08 (callbacks).

## Context
The buyer agent already has an allowlist callback that blocks unauthorized tools. But it doesn't enforce business rules on the tool *arguments*. A tool could be allowed but called with invalid parameters.

## Steps

### Step 1 — Read the current callback
Open `negotiation_agents/buyer_agent/agent.py`. Look at `_enforce_buyer_allowlist` — it checks `tool.name` but ignores `args`.

### Step 2 — Create a new callback that does both

Write a function that:

1. **Logs** every tool call (tool name, arguments, timestamp)
2. **Blocks** the allowlist (same as current — reject tools not in `_BUYER_ALLOWED_TOOLS`)
3. **Validates arguments**: if any argument value is a number > 460,000, block the call with an error message

```python
from datetime import datetime, timezone

def buyer_guard(tool: BaseTool, args: dict, tool_context: ToolContext):
    """Combined allowlist + argument validation + logging."""
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] TOOL CALL: {tool.name}({args})")

    # Allowlist check
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        print(f"[{timestamp}] BLOCKED: unauthorized tool '{tool.name}'")
        return {"error": f"tool '{tool.name}' is not authorized for the buyer"}

    # Argument validation — no price above budget
    for key, value in args.items():
        if isinstance(value, (int, float)) and value > 460_000:
            print(f"[{timestamp}] BLOCKED: {key}={value} exceeds budget")
            return {"error": f"argument '{key}' value ${value:,.0f} exceeds buyer budget of $460,000"}

    return None
```

### Step 3 — Replace the callback

Change `before_tool_callback=_enforce_buyer_allowlist` to `before_tool_callback=buyer_guard` in the `root_agent` definition.

### Step 4 — Test

```bash
adk web m3_adk_multiagents/negotiation_agents/
```

Select `buyer_agent`, and ask it to evaluate a property priced at $500,000. Watch the terminal logs — the callback should block tool calls with prices exceeding budget.

## Verify
- Every tool call is logged with a timestamp in the terminal
- Unauthorized tools are still blocked (same as before)
- Tool calls with price arguments above $460,000 are blocked with a clear error message
- The agent receives the error and adjusts its behavior

## Reflection question
> This callback runs synchronously before every tool call. In a high-throughput system with many concurrent agents, what's the performance impact? Would you do this validation differently in production?
