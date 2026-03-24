# Exercise 2 — Add a Concessions Reducer `[Core]`

## Goal
Add a `concessions` field to the LangGraph state using `Annotated[list[dict], operator.add]` and track how much each agent moves from their previous position every round. This teaches you the **core LangGraph concept**: append-only reducers.

## What to look for
In `m3_langgraph_multiagents/langgraph_flow.py`:
- `NegotiationState` TypedDict uses `Annotated[list, operator.add]` for `history`
- `buyer_node()` and `seller_node()` return `{"history": [entry]}` and LangGraph **appends** (not replaces)
- The same pattern works for any list field you add

## Steps

Open `m3_langgraph_multiagents/langgraph_flow.py` and search for `Exercise 2`. There are **7 locations** to uncomment.

### Step 1 — Add the state field
In `NegotiationState`, uncomment the `concessions: Annotated[list[dict], operator.add]` field.

### Step 2 — Initialize it
In `initial_state()`, uncomment `"concessions": []`.

### Step 3 — Track buyer concessions
In `buyer_node()`, uncomment the concession tracking block that computes how much the buyer moved from their previous offer. Also uncomment the `"concessions": [concession_entry]` line in the return dict.

### Step 4 — Track seller concessions
In `seller_node()`, uncomment the concession tracking block for the seller. Also uncomment the `"concessions": [concession_entry]` line in the return dict.

### Step 5 — Display the results
In `print_negotiation_results()`, uncomment the CONCESSION ANALYSIS display block.

## Verify
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 5
```

You should see a CONCESSION ANALYSIS table showing each agent's price movement per round with ↑/↓ arrows.

## Reflection question
> Why does the `concessions` field use `Annotated[list[dict], operator.add]` instead of a plain `list[dict]`? What would happen if you used a plain list and returned `{"concessions": [new_entry]}`? (Try it and see.)
