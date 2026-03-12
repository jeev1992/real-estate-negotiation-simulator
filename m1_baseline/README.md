# Module 1 — Baseline (`m1_baseline`)

This is where the workshop starts. **No API keys needed.**

The goal of this module is to show *why* naive agent systems break — and to introduce the first fix: a Finite State Machine (FSM) that guarantees the negotiation always ends.

---

## What this module teaches

> "Before you build the right thing, you need to feel the wrong thing."

The two files in this module are deliberately paired:

| File | What it is |
|---|---|
| `naive_negotiation.py` | A broken negotiation — 10 failure modes on purpose |
| `state_machine.py` | The first fix — a state machine that guarantees termination |

Running them back-to-back shows you the exact problem and the exact fix.

---

## File breakdown

### `naive_negotiation.py` — The broken version

This is intentionally bad code. It represents how most developers write their first agent system: agents exchanging raw strings in a `while True` loop with no structure.

**The 10 failure modes built into this file:**

| # | Failure | What it causes |
|---|---|---|
| 1 | Raw string messages | Agent B can't reliably parse Agent A's intent |
| 2 | No schema | Messages can be anything — no validation |
| 3 | `while True` loop | No state tracking, no structure |
| 4 | No turn limit | Can loop forever |
| 5 | Fragile regex | Extracts the wrong price from `"I paid $350K, now asking $477K"` |
| 6 | No termination guarantee | "Almost done" is not the same as "guaranteed to stop" |
| 7 | Silent failures | Bad parse = wrong number, no error thrown |
| 8 | Hardcoded prices | No real market data — agents negotiate blindly |
| 9 | No observability | Can't see what happened or why |
| 10 | No evaluation | Can't measure if the result was good |

**What to watch for when you run it:**
- Does it actually finish?
- Does the price it agrees on make any sense?
- What happens if you run it twice — do you get the same result?

### `state_machine.py` — The first fix

This file introduces the `NegotiationFSM`: a Finite State Machine with four states.

```
IDLE -> NEGOTIATING -> AGREED   (deal reached)
                    -> FAILED   (no deal / too many turns)
```

The key insight is in the transition table. Terminal states (`AGREED`, `FAILED`) have **no outgoing transitions** — once you're in them, there is no way out. This is a mathematical guarantee that the negotiation *must* end.

```python
TRANSITIONS = {
    IDLE:         {START_NEGOTIATION: NEGOTIATING},
    NEGOTIATING:  {ACCEPT: AGREED, REJECT: FAILED, COUNTER: NEGOTIATING},
    AGREED:       set(),   # <-- terminal: no transitions possible
    FAILED:       set(),   # <-- terminal: no transitions possible
}
```

Compare this to `naive_negotiation.py`'s `while True` — same domain, completely different reliability guarantee.

---

## What problem does each later module solve?

```
naive_negotiation.py (the problem)
  |
  +-- state_machine.py       -> fixes #3, #4, #6 (FSM, turn limit, termination)
  |
  +-- m2_mcp/                -> fixes #8 (real pricing data via MCP tools)
  |
  +-- m3_langgraph_multiagents/ -> fixes #3, #9 (structured workflow + observability)
  |
  +-- m4_adk_multiagents/    -> fixes #1, #2, #5 (A2A protocol: structured messages + schema)
```

Every module you learn fixes one or more rows in that failure table.

---

## How to run

No API keys needed for either file.

```bash
# Run from the negotiation_workshop/ directory

# Part 1: Watch the naive version (it may finish, may not — that's the point)
python m1_baseline/naive_negotiation.py

# Part 2: Run the FSM demo (always terminates, prints state transitions)
python m1_baseline/state_machine.py
```

**What to expect from `naive_negotiation.py`:**
- It runs a few rounds of text-based negotiation
- Watch for garbled prices and unpredictable endings
- Notice there is no guarantee it ends cleanly

**What to expect from `state_machine.py`:**
- It runs a short demo showing state transitions
- Every transition is printed: `IDLE -> NEGOTIATING -> AGREED`
- It always terminates — try changing the inputs and see that it still does

---

## Exercises

| Exercise | Difficulty | Task |
|---|---|---|
| `ex01_identify_failure_modes.md` | `[Core]` | Add a TIMEOUT terminal state to the FSM — new enum, transition table, deadline check, invariants |
| `ex02_fsm_termination_check.md` | `[Core]` | Run naive vs FSM side by side, fill in a comparison table mapping each failure mode to its fix |
| `ex03_stretch_fsm_different_language.md` | `[Stretch]` | Reimplement the FSM core in TypeScript to prove the pattern is language-independent |

Solutions are in `m1_baseline/solution/`. Each exercise includes a reflection question.

---

## Quick mental model

- If you're confused about *why* this module exists, re-read the 10 failure modes above.
- If you want to see the termination proof, look at the `TRANSITIONS` dict in `state_machine.py`.
- The FSM from this module lives on in `m3_langgraph_multiagents/langgraph_flow.py`, which builds on the same idea using LangGraph's graph routing.
