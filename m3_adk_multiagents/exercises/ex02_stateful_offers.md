# Exercise 2 — Add State to the Negotiation Agent `[Core]`

## Goal
Modify `d03_sessions_state` to track the best offer so far and warn the user when they're going backwards (offering less than a previous offer). This reinforces ToolContext and session state persistence.

## Context
Demo 03 records offers in `offer_history` but doesn't do anything intelligent with the history. Your job: add a tool that compares the new offer against the running best, and warns the user if they're regressing.

## Steps

### Step 1 — Copy the demo
Copy `adk_demos/d03_sessions_state/` to `adk_demos/ex02_stateful_offers/`. Update `__init__.py` to import agent.

### Step 2 — Add a `submit_offer` tool

Replace the existing `record_offer` tool with a smarter version:

```python
def submit_offer(price: int, tool_context: ToolContext) -> dict:
    """Submit an offer and check it against negotiation history."""
    history = tool_context.state.get("offer_history", [])
    best_so_far = max(history) if history else 0

    history.append(price)
    tool_context.state["offer_history"] = history
    tool_context.state["best_offer"] = max(history)

    result = {
        "recorded_price": price,
        "total_offers": len(history),
        "best_offer": max(history),
    }

    if price < best_so_far:
        result["warning"] = (
            f"This offer (${price:,}) is LOWER than your previous best "
            f"(${best_so_far:,}). The seller will likely reject a regression."
        )

    return result
```

### Step 3 — Update instructions

Tell the agent to:
- Always call `submit_offer` when the user proposes a price
- If the tool returns a `warning`, relay it to the user and suggest they reconsider
- Track how many offers remain (max 5 rounds)

### Step 4 — Test

```bash
adk web m3_adk_multiagents/adk_demos/ex02_stateful_offers/
```

Try this sequence:
1. "Offer $430,000"
2. "Offer $445,000"
3. "Offer $440,000" — should trigger the regression warning

## Verify
- Regression warning appears when offering less than the previous best
- State persists across turns within the same session
- `best_offer` state key is always the max of all offers

## Reflection question
> The `user:` prefix on state keys scopes them to a user across sessions. When would you use `app:` vs `user:` vs `temp:` prefixes in a real negotiation scenario?
