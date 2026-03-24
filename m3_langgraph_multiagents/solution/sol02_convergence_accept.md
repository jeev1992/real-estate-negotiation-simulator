# Solution 2: Add Automatic Convergence Accept

## Code change
In `m3_langgraph_multiagents/langgraph_flow.py`, in `seller_node()`, add the convergence check after the deadlock guard and before the final `return` statement:

```python
async def seller_node(state: dict) -> dict:
    # ... existing code through new_status and agreed_price computation ...

    # Deadlock guard (existing)
    if round_number >= state["max_rounds"] and new_status == "negotiating":
        new_status = "deadlocked"
        print(f"[LangGraph] Max rounds reached -- deadlock")

    # ── NEW: Convergence auto-accept ──────────────────────────────────────
    if new_status == "negotiating":
        buyer_offer = state.get("buyer_current_offer", 0)
        seller_counter = seller_message.get("price", 0)

        if buyer_offer > 0 and seller_counter > 0:
            gap_pct = abs(seller_counter - buyer_offer) / max(seller_counter, buyer_offer)
            if gap_pct <= 0.02:
                midpoint = (buyer_offer + seller_counter) / 2
                agreed_price = round(midpoint)
                new_status = "agreed"
                print(f"[LangGraph] Auto-accept: offers within {gap_pct:.1%}, agreeing at ${agreed_price:,.0f}")
    # ── END NEW ───────────────────────────────────────────────────────────

    history_entry = {
        "round": seller_message["round"],
        "agent": "seller",
        "message_type": seller_message["message_type"],
        "price": seller_message.get("price"),
        "message": seller_message.get("message", "")[:200],
    }

    return {
        "seller_current_counter": seller_message.get("price") or state["seller_current_counter"],
        "status": new_status,
        "agreed_price": agreed_price,
        "last_seller_message": seller_message,
        "history": [history_entry],
    }
```

## Why this works

The convergence check runs **after** the seller has decided its counter-offer but **before** the state update is returned. At this point:
- `buyer_current_offer` in state is the buyer's latest offer from this round
- `seller_message.get("price")` is the seller's new counter-offer

If they're within 2%, we compute the midpoint, set `agreed_price`, and change `new_status` to `"agreed"`. The `route_after_seller()` router will see the terminal status and route to `END`.

## Design trade-offs

| Threshold | Effect |
|--|--|
| 0% (exact match) | Almost never triggers — agents rarely propose identical prices |
| 2% (default) | Good balance — catches near-agreements without being too aggressive |
| 5% | Triggers too early — agents may have negotiated a better price |
| 10% | Essentially short-circuits the negotiation |

The 2% threshold works well for real estate because the gap at that point ($8K–$10K on a $485K property) is often within the range of closing cost adjustments.

## Verify
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 5
```
