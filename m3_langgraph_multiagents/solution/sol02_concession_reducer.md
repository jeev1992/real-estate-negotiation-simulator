# Solution 2: Add a Concessions Reducer

## How to apply

The code is already in `m3_langgraph_multiagents/langgraph_flow.py` as **commented-out blocks** marked with `── Exercise 2 ──`. Search for `Exercise 2` to find all 7 locations and uncomment them.

### 1. State field

In `NegotiationState`, uncomment:
```python
concessions: Annotated[list[dict], operator.add]
```

### 2. Initial state

In `initial_state()`, uncomment:
```python
"concessions": [],
```

### 3. Buyer concession tracking

In `buyer_node()`, uncomment the concession computation block and the `"concessions"` key in the return dict.

### 4. Seller concession tracking

In `seller_node()`, uncomment the concession computation block and the `"concessions"` key in the return dict.

### 5. Results display

In `print_negotiation_results()`, uncomment the CONCESSION ANALYSIS display block.

## Why this works

The `Annotated[list[dict], operator.add]` reducer tells LangGraph: when a node returns `{"concessions": [new_entry]}`, **append** the new entry to the existing list rather than replacing it. This is the same pattern used by `history` — it's the fundamental mechanism for accumulating data across graph iterations.

Each node computes `moved` as the difference between the agent's new price and their previous price. Positive values mean the buyer raised their offer (↑); negative values mean the seller lowered their counter (↓).

## Expected output

```
CONCESSION ANALYSIS:
  Rnd    Agent         From           To        Moved
  -----------------------------------------------------
    1   seller $   485,000 $   477,000 ↓$    8,000
    2    buyer $   425,000 $   435,000 ↑$   10,000
    2   seller $   477,000 $   472,000 ↓$    5,000
    3    buyer $   435,000 $   445,000 ↑$   10,000
    3   seller $   472,000 $   445,000 ↓$   27,000
```

## Reflection answer

Without `Annotated[list, operator.add]`, returning `{"concessions": [new_entry]}` would **replace** the entire list with just `[new_entry]`, losing all previous entries. The `operator.add` reducer changes the merge behavior to `existing_list + new_list`, which is append. This is essential for any field that accumulates data across multiple node invocations.

## Verify
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 5
```
