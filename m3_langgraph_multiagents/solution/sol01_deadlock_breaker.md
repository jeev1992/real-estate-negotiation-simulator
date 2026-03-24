# Solution 1: Add a Deadlock-Breaker Conditional Edge

## Code changes

Two places in `m3_langgraph_multiagents/langgraph_flow.py` need updates.

### 1. Add stale-price detection in `seller_node()`

In `seller_node()`, add this block **before** the existing max-rounds deadlock guard (`if round_number >= state["max_rounds"]`):

```python
    # Stale-price deadlock detection (NEW)
    if new_status == "negotiating":
        history = state.get("history", [])
        if len(history) >= 4:
            recent = history[-4:]
            buyer_prices = [e.get("price") for e in recent if e.get("agent") == "buyer"]
            seller_prices = [e.get("price") for e in recent if e.get("agent") == "seller"]

            if (len(buyer_prices) >= 2 and len(seller_prices) >= 2
                    and buyer_prices[-1] == buyer_prices[-2]
                    and seller_prices[-1] == seller_prices[-2]):
                new_status = "deadlocked"
                print(f"[LangGraph] Stale prices detected -- deadlock")
```

This sets `status = "deadlocked"` in the state **from the node** (which owns state mutations). The router then sees the terminal status and routes to END.

### 2. Update `route_after_seller()`

The existing router already handles this correctly — the first check is:
```python
if status != "negotiating":
    return "end"
```
Since the node now sets `status = "deadlocked"`, the router sees it and returns `"end"`. **No router changes needed.** The stale-price detection lives in the node (state owner), not the router (pure reader).

Optionally, you can add redundant stale-price detection in the router as a safety net:

```python
def route_after_seller(state: dict) -> Literal["continue", "end"]:
    """
    Determine next step after seller node runs.

    Route to "continue" (loops back to buyer) if negotiation is still active.
    Route to "end" for all terminal states.

    ADDED: Stale-price detection — if both agents repeated their
    price for two consecutive rounds, force end to avoid wasting rounds.
    """
    status = state.get("status", "negotiating")

    if status != "negotiating":
        return "end"

    round_number = state.get("round_number", 0)
    max_rounds = state.get("max_rounds", 5)

    if round_number >= max_rounds:
        return "end"

    # Stale-price deadlock detection
    history = state.get("history", [])
    if len(history) >= 4:
        recent = history[-4:]
        buyer_prices = [e.get("price") for e in recent if e.get("agent") == "buyer"]
        seller_prices = [e.get("price") for e in recent if e.get("agent") == "seller"]

        if (len(buyer_prices) >= 2 and len(seller_prices) >= 2
                and buyer_prices[-1] == buyer_prices[-2]
                and seller_prices[-1] == seller_prices[-2]):
            print(f"[LangGraph Router] Stale prices detected — forcing deadlock")
            return "end"

    return "continue"
```

## Why this works

The stale-price check runs inside `seller_node()` — the node that owns state mutations. It inspects the last 4 history entries (2 buyer + 2 seller messages across 2 rounds). If both sides repeated their exact price, it sets `new_status = "deadlocked"`, which:
1. Gets returned in the node's partial state update
2. Is seen by `route_after_seller()` as a non-negotiating status → returns `"end"`
3. Shows up correctly in `print_negotiation_results()` as a deadlock

This follows the LangGraph principle: **nodes mutate state, routers read state**.

## Reflection answer

Yes, this could theoretically end a negotiation that might have succeeded on the next round — but only if one agent was about to change its price after holding steady for two consecutive rounds. This is unlikely in practice because LLM agents typically either keep moving or explicitly walk away.

To reduce false positives, increase the threshold to 3 rounds (check `history[-6:]` with 3 matching prices per agent). The trade-off: more rounds consumed before detecting a genuine deadlock.

## Verify
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 5
```
