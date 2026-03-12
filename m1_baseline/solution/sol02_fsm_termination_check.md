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

## Reflection answer

Yes, the FSM provides a **basic form** of observability via `check_invariants()` (detects impossible states) and `__repr__` (shows current state + turn count). However, it doesn't record history, which is critical for understanding _how_ a negotiation reached its outcome. LangGraph's `Annotated[list, operator.add]` reducer provides full round-by-round audit trails, which is true observability.
