# Solution 2: Compare Naive vs FSM Failure Modes

## Completed comparison table

| # | Failure Mode | Fixed by FSM? | Explanation |
|---|---|---|---|
| 1 | Raw string communication | **No** | FSM controls lifecycle, not message format. Fixed by **A2A typed messages** in M3/M4. |
| 2 | No schema validation | **No** | FSM doesn't validate message content. Fixed by **negotiation_types.py** `NegotiationMessage` TypedDict in M3. |
| 3 | No state machine (while True) | **Yes** | The FSM replaces `while True` with explicit states and a transition table. |
| 4 | No turn limits | **Yes** | `process_turn()` enforces `max_turns` automatically. |
| 5 | Ambiguous parsing (regex) | **No** | FSM doesn't handle message parsing. Fixed by **structured JSON** messages in M3 (`negotiation_types.py`). |
| 6 | No termination guarantees | **Yes** | Terminal states (AGREED, FAILED) have empty transition sets. Turn counter is bounded. Mathematical guarantee. |
| 7 | Silent failures | **Partially** | `check_invariants()` catches FSM-level bugs, but message-level silent failures are still possible. Fully fixed by typed messages in M3. |
| 8 | No grounded context (hardcoded prices) | **No** | FSM is about lifecycle, not data sourcing. Fixed by **MCP servers** in M2. |
| 9 | No observability | **Partially** | `__repr__`, `check_invariants()`, and explicit state tracking improve visibility. Full observability comes from **LangGraph state history** in M3. |
| 10 | No evaluation metrics | **No** | FSM doesn't measure negotiation quality. Could be added via history analysis in M3's LangGraph state. |

## Unsolved failure modes mapped to modules

| Failure Mode | Fixed By |
|---|---|
| #1 Raw strings | M3/M4 — `negotiation_types.py` (typed messages) |
| #2 No schema validation | M3/M4 — `NegotiationMessage` TypedDict + Pydantic in M4 |
| #5 Ambiguous parsing | M3/M4 — explicit `price` field replaces regex extraction |
| #7 Silent failures (full fix) | M3 — LangGraph error nodes + structured error responses |
| #8 No grounded context | M2 — MCP servers (`pricing_server.py`, `inventory_server.py`) |
| #9 No observability (full fix) | M3 — LangGraph `history` list with append-only reducer |
| #10 No evaluation | M3 — `print_negotiation_results()` in `langgraph_flow.py` |

## What to observe when running the naive version

Run `python m1_baseline/naive_negotiation.py` and compare against the failure mode table above.

**Demo 1** (ZOPA exists — Buyer max $460K, Seller min $445K):
- Closes in ~3 turns at ~$453K — looks like it works!
- Example: Buyer opens at $424,580 → Seller counters $453,150 → Buyer says "ACCEPT" → Seller says "DEAL!"
- Looks correct — but only because the LLM happened to write the price in a format the regex could grab
- The regex `\$?(\d[\d,]*)` grabs the *first* number it finds. If the seller had mentioned renovation costs or comps first, the buyer would have latched onto the wrong number (Failure Mode #1/#5).

**Demo 2** (No ZOPA — Buyer max $420K, Seller min $450K):
- You might expect the loop to run all 8 turns (the demo cap) since no deal is mathematically possible.
- **Actual result**: The seller says "DEAL!" at $420,000 after only 3 turns — **below its own $450K floor**.
- This is **Failure Mode #6** (string-match termination) in action: the LLM generated the word "DEAL" and the naive `if "DEAL" in response:` check triggered an early exit at a price the seller should never have accepted.
- The code itself flags this: _"NOTICE: LLM accidentally used 'DEAL' or 'REJECT' and triggered early exit. Stopped for the wrong reason."_
- **Key insight**: The naive version can't distinguish between a genuine acceptance and an LLM that happens to use the word "DEAL" in its response.

**Failure Mode Demos** (printed after Demo 2):
- Five concrete examples (#1–#5) that demonstrate regex parsing bugs, silent failures, the no-ZOPA infinite loop, hardcoded prices, and false-positive string matching.
- Compare each one against the FSM table above: #3, #4, #6 are solved; the rest require M2–M4.

## Reflection answer

Yes, the FSM provides a **basic form** of observability via `check_invariants()` (detects impossible states) and `__repr__` (shows current state + turn count). However, it doesn't record history, which is critical for understanding _how_ a negotiation reached its outcome. LangGraph's `Annotated[list, operator.add]` reducer provides full round-by-round audit trails, which is true observability.
