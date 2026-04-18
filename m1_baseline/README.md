# Module 1 — Baseline (`m1_baseline`)

This is where the workshop starts.

- `naive_negotiation.py` — **requires `OPENAI_API_KEY`** (makes real GPT-4o calls)
- `state_machine.py` — **no API key needed** (pure Python FSM demo)

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
    IDLE:        {NEGOTIATING, FAILED},
    NEGOTIATING: {NEGOTIATING, AGREED, FAILED},
    AGREED:      set(),   # <-- terminal: no transitions possible
    FAILED:      set(),   # <-- terminal: no transitions possible
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
  +-- m3_adk_multiagents/    -> fixes #1, #2, #3, #5, #9 (A2A protocol + ADK runtime: structured messages, schema, workflow agents, event/streaming observability)
```

Every module you learn fixes one or more rows in that failure table.

---

## How to run

```bash
# Run from the real-estate-negotiation-simulator/ directory

# Part 1: Watch the naive version (requires OPENAI_API_KEY — makes real GPT-4o calls)
python m1_baseline/naive_negotiation.py

# Part 2: Run the FSM demo (no API key needed — always terminates)
python m1_baseline/state_machine.py
```

**What to expect from `naive_negotiation.py`:**

*Demo 1 — "Works by luck" (Buyer max $460K, Seller min $445K — ZOPA exists):*
- Real GPT-4o calls are made for every turn
- Typically closes in 3–4 turns at a price like $453K — within the zone of agreement
- The price is correct by accident: if the seller had mentioned any other number first, the regex would have grabbed that instead
- Run it twice — you may get a different path to the same outcome

*Demo 2 — "Impossible agreement" (Buyer max $420K, Seller min $450K — no ZOPA):*
- There is mathematically no price both sides will accept
- The loop runs for 8 turns (demo cap), then triggers the emergency exit
- Every single LLM call is wasted — the agents can never converge
- In production with a 100-turn cap this costs ~$1+ per doomed negotiation

*Demo 3 — Static failure mode examples:*
- No LLM needed — shows the regex and string-matching bugs directly
- Demonstrates all 10 failure modes with concrete input/output pairs

**What to expect from `state_machine.py`:**
- It runs a short demo showing state transitions
- Every transition is printed: `IDLE -> NEGOTIATING -> AGREED`
- It always terminates — try changing the inputs and see that it still does

---

## Exercises

| Exercise | Difficulty | Task |
|---|---|---|
| `ex01_add_timeout_state.md` | `[Core]` | Add a TIMEOUT terminal state to the FSM — new enum, transition table, deadline check, invariants |
| `ex02_compare_failure_modes.md` | `[Core]` | Run naive vs FSM side by side, fill in a comparison table mapping each failure mode to its fix |

Solutions are in `m1_baseline/solution/`. Each exercise includes a reflection question.

---

## Quick mental model

- If you're confused about *why* this module exists, re-read the 10 failure modes above.
- If you want to see the termination proof, look at the `TRANSITIONS` dict in `state_machine.py`.
- The FSM idea from this module reappears in Module 3 — Google ADK's workflow agents (`SequentialAgent`, `LoopAgent`) encode the same termination guarantees at the agent-orchestration level.
