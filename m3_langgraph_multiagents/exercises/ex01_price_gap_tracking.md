# Exercise 1 — Add Price Gap Tracking to History `[Core]`

## Goal
Add a `price_gap_pct` field to each seller history entry showing how far apart the buyer and seller are. Then update the results display to show a `Gap%` column. This teaches you how **nodes enrich shared state** and how downstream code reads accumulated history.

## What to look for
In `m3_langgraph_multiagents/langgraph_flow.py`:
- `seller_node()` builds a `history_entry` dict each round
- `print_negotiation_results()` reads the `history` list and prints a table
- Both buyer's current offer and seller's counter are available in `seller_node()`

## Steps

Open `m3_langgraph_multiagents/langgraph_flow.py` and search for `Exercise 1`. There are **3 locations** to update.

### Step 1 — Compute the price gap
In `seller_node()`, uncomment the block that computes `price_gap_pct` from the buyer's offer and seller's counter.

### Step 2 — Add it to the history entry
In the same function, uncomment the `"price_gap_pct": price_gap_pct` line inside the `history_entry` dict.

### Step 3 — Update the results display
In `print_negotiation_results()`, replace the existing history table header and loop with the commented-out version that includes the `Gap%` column. Delete the pre-exercise version below it.

## Verify
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 5
```

The history table should now show a `Gap%` column on seller rows, with the percentage narrowing each round (e.g., 10.9% → 7.8% → 0.0%).

## Reflection question
> Why does only the seller's history entry get `price_gap_pct` and not the buyer's? (Hint: when the buyer makes an offer, the seller hasn't responded yet — there's no counter to compare against.)
