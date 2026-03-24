# Exercise 2 — Compare Naive vs FSM Failure Modes `[Core]`

## Goal
Run both the naive and FSM negotiation implementations, observe the differences, and document which of the 10 intentional failure modes each system handles.

## What to look for
The naive implementation (`naive_negotiation.py`) has **10 documented failure modes** listed at the top of the file. The FSM (`state_machine.py`) was built to fix several of them. Your job is to determine which ones and why.

## Steps

### Step 1 — Run the naive negotiation and observe

> **Note**: `naive_negotiation.py` makes real GPT-4o calls. You will need `OPENAI_API_KEY` set in your `.env` file.

```bash
python m1_baseline/naive_negotiation.py
```

Watch the output carefully. Note:
- **Demo 1** (Buyer max $460K, Seller min $445K): How many turns does it take to close? Does the price land inside the $445K–$460K zone of agreement?
- **Demo 2** (Buyer max $420K, Seller min $450K): Does it loop all 8 turns as you'd expect? If it exits early, what triggered the exit — and is the final price actually valid for both sides?
- **Failure Mode Demos** (printed after Demo 2): Five static examples showing regex parsing bugs, silent failures, the no-ZOPA problem, hardcoded prices, and false-positive string matching. Which of these could the FSM catch?

### Step 2 — Run the FSM demo and observe
```bash
python m1_baseline/state_machine.py
```

Note:
- How many terminal states exist? What are they?
- Can the FSM ever loop forever? Why not?
- How does the FSM handle an invalid transition attempt?

### Step 3 — Fill in the comparison table

Copy this table and fill in the "Fixed by FSM?" column with Yes/No and a brief explanation:

| # | Failure Mode | Fixed by FSM? | Explanation |
|---|---|---|---|
| 1 | Raw string communication | | |
| 2 | No schema validation | | |
| 3 | No state machine (while True) | | |
| 4 | No turn limits | | |
| 5 | Ambiguous parsing (regex) | | |
| 6 | No termination guarantees | | |
| 7 | Silent failures | | |
| 8 | No grounded context (hardcoded prices) | | |
| 9 | No observability | | |
| 10 | No evaluation metrics | | |

### Step 4 — Identify what's still missing
After filling in the table, answer: **Which failure modes require solutions beyond the FSM?** Map each unsolved failure mode to the module that fixes it (M2 MCP, M3 LangGraph, or M4 A2A).

## Verify
There is no code change to verify for this exercise — your deliverable is the completed table and analysis.

## Reflection question
> The FSM solves problems #3, #4, and #6 directly. But does it help with problem #9 (observability) at all? Look at `check_invariants()` and the `__repr__` method — is that a form of observability?
