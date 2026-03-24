# Solution 1: Add Price Gap Tracking to History

## How to apply

The code is already in `m3_langgraph_multiagents/langgraph_flow.py` as **commented-out blocks** marked with `── Exercise 1 ──`. Search for `Exercise 1` to find all 3 locations and uncomment them.

### 1. Price gap computation in `seller_node()`

Uncomment the block that computes `price_gap_pct`:

```python
buyer_offer = state.get("buyer_current_offer", 0)
seller_counter = seller_message.get("price", 0)
price_gap_pct = None
if buyer_offer > 0 and seller_counter > 0:
    price_gap_pct = round(
        abs(seller_counter - buyer_offer) / max(seller_counter, buyer_offer) * 100, 1
    )
```

### 2. Add to history entry

Uncomment `"price_gap_pct": price_gap_pct` in the `history_entry` dict.

### 3. Update the results display

In `print_negotiation_results()`, replace the pre-exercise history table with the Gap% version (uncomment the new one, delete the old one).

## Why this works

The gap percentage is computed in `seller_node()` because that's the only point where both the buyer's current offer and the seller's counter are known for the same round. It gets stored in the history entry which is appended via the `operator.add` reducer, so it accumulates across rounds automatically.

## Expected output

```
NEGOTIATION HISTORY:
  Rnd    Agent             Type        Price     Gap%
  -----------------------------------------------------
    1    buyer            OFFER     $425,000
    1   seller    COUNTER_OFFER     $477,000   10.9%
    2    buyer            OFFER     $435,000
    2   seller    COUNTER_OFFER     $472,000    7.8%
    3    buyer            OFFER     $445,000
    3   seller           ACCEPT     $445,000    0.0%
```

## Reflection answer

Only seller entries have `price_gap_pct` because when the buyer makes an offer, the seller hasn't responded yet — there's no pair of prices to compare. The gap only makes sense after both sides have spoken in the same round.

## Verify
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 5
```
