# Exercise 2 — Add Automatic Convergence Accept `[Core]`

## Goal
Add logic so that when the buyer's offer and seller's counter are within 2% of each other, the negotiation automatically concludes with `agreed` status at the midpoint price. This teaches you how to add **business logic to graph nodes** and how nodes communicate through shared state.

## What to look for
In `m3_langgraph_multiagents/langgraph_flow.py`:
- `seller_node()` has access to both `buyer_current_offer` (from state) and the seller's response price
- The node returns partial state updates that LangGraph merges
- The `status` field drives routing decisions downstream

## Steps

### Step 1 — Identify where to add the check
The convergence check belongs at the end of `seller_node()`, after the seller has generated its counter-offer but before returning the state update. At this point, both the buyer's latest offer and the seller's counter are known.

### Step 2 — Add the convergence logic
In `seller_node()`, after computing `new_status` and before the final `return` statement, add:

```python
# Convergence auto-accept: if offers are within 2%, agree at midpoint
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
```

### Step 3 — Make sure the return dict uses the updated values
The existing return statement already uses `new_status` and `agreed_price`, so no further changes are needed if you update those variables in place.

## Verify
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 5
```

Run multiple times. When buyer and seller prices converge to within 2%, you should see the auto-accept message and the negotiation ending early with a midpoint deal.

## Reflection question
> What happens if you set the convergence threshold to 0% (exact match only)? What about 10%? Think about the trade-off between letting agents negotiate for a better price vs. ending the negotiation efficiently.
