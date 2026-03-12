# Solution 1: Add a Deadlock-Breaker Conditional Edge

## Code change
In `m3_langgraph_multiagents/langgraph_flow.py`, replace the `route_after_seller` function:

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

The router is a **pure function** that only reads state. It checks the last 4 history entries (2 buyer + 2 seller messages across 2 rounds). If both sides repeated their exact price, further rounds won't produce progress.

The graph's existing termination logic handles the rest:
- When the router returns `"end"`, the graph transitions to `END`
- The final status will be `"deadlocked"` if no terminal message was set by a node
- Alternatively, the final status may be `"negotiating"` which `print_negotiation_results()` still displays

## Reflection answer

Yes, this could theoretically end a negotiation that might have succeeded on the next round — but only if one agent was about to change its price after holding steady for two consecutive rounds. This is unlikely in practice because LLM agents typically either keep moving or explicitly walk away.

To reduce false positives, increase the threshold to 3 rounds (check `history[-6:]` with 3 matching prices per agent). The trade-off: more rounds consumed before detecting a genuine deadlock.

## Verify
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 5
```
