# Exercise 1 — Add a Deadlock-Breaker Conditional Edge `[Core]`

## Goal
Add a new routing condition that detects when the buyer and seller have each made the same offer twice in a row (stale prices), and forces the negotiation to end with a `deadlocked` status instead of continuing. This teaches you how **conditional edges** control graph flow in LangGraph.

## What to look for
In `m3_langgraph_multiagents/langgraph_flow.py`, study:
- `route_after_seller()` — the router function that decides whether to continue or end
- `NegotiationState` TypedDict — what fields are available to routers
- `seller_node()` return values — how `seller_current_counter` gets set
- The `history` list — how you can inspect previous rounds

Routers are **pure functions**: they read state and return a string key. No side effects.

## Steps

### Step 1 — Understand the current router
Read `route_after_seller()`. It currently checks:
1. Is the status terminal? → `"end"`
2. Has `round_number` reached `max_rounds`? → `"end"`
3. Otherwise → `"continue"`

### Step 2 — Add stale-price detection
Modify `route_after_seller()` to check if both agents have repeated their prices. Use the `history` list from state:

```python
def route_after_seller(state: dict) -> Literal["continue", "end"]:
    status = state.get("status", "negotiating")

    if status != "negotiating":
        return "end"

    round_number = state.get("round_number", 0)
    max_rounds = state.get("max_rounds", 5)

    if round_number >= max_rounds:
        return "end"

    # NEW: Detect stale prices (deadlock-breaker)
    history = state.get("history", [])
    if len(history) >= 4:
        # Get last 4 entries (2 full rounds: buyer, seller, buyer, seller)
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

### Step 3 — Handle the deadlock status
The router returns `"end"` but doesn't set the status. You need to update `seller_node()` to detect this case. After the existing deadlock guard (`if round_number >= state["max_rounds"]`), the status is already set to `"deadlocked"`. The router's stale-price detection provides an **additional** path to end, and the graph will stop.

Alternatively, you can set the status in the router itself by updating the state — but remember routers should be pure functions. The cleaner approach is to let the existing `deadlocked` status logic handle it.

## Verify
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 5
```

Run a few times. If the agents get stuck on the same prices for two consecutive rounds, the negotiation should end early instead of wasting remaining rounds.

## Reflection question
> Could this deadlock-breaker accidentally end a negotiation that would have succeeded? Under what conditions? How would you adjust the threshold (e.g., 3 rounds of stale prices instead of 2) to reduce false positives?
