# Exercise 1 — Add a TIMEOUT Terminal State `[Core]`

## Goal
Extend the FSM with a new terminal state that fires when wall-clock time exceeds a limit. This teaches you:
- How the transition table controls reachable states
- Why terminal states must have empty transition sets
- How to preserve the termination guarantee when modifying an FSM

## What to look for
The FSM's termination guarantee relies on **two properties**:
1. Terminal states (`AGREED`, `FAILED`) have **empty transition sets** — once entered, they cannot be exited.
2. Every path either reaches a terminal state or increments a bounded counter.

Your new `TIMEOUT` state must satisfy both properties.

## Steps

Open `m1_baseline/state_machine.py`. All the code you need is already in the file as **commented-out blocks** marked with `── Exercise 1 ──`. Your job is to find each block, understand what it does, and uncomment it.

There are **11 locations** to update. Search for `Exercise 1` in the file to find them all.

### Step 1 — Add the new state and reason
Uncomment `TIMEOUT = auto()` in `NegotiationState` and `WALL_CLOCK_TIMEOUT = auto()` in `FailureReason`.

### Step 2 — Add context fields
Uncomment `deadline_seconds` and `start_time` in `FSMContext`.

### Step 3 — Update the transition table
Add `NegotiationState.TIMEOUT` to the `NEGOTIATING` target set, and uncomment the `NegotiationState.TIMEOUT: set()` terminal entry.

### Step 4 — Update `__init__`
Add `deadline_seconds: float = 60.0` to the `__init__` signature and pass it to `FSMContext`.

### Step 5 — Update `is_terminal()`
Add `NegotiationState.TIMEOUT` to the set in `is_terminal()`.

### Step 6 — Record start time
Uncomment `self.context.start_time = time.time()` in `start()`.

### Step 7 — Add deadline check
Uncomment the wall-clock timeout check block in `process_turn()`.

### Step 8 — Update `check_invariants()` and demo
Uncomment the TIMEOUT invariant check, and uncomment Scenario 4 in `demo_fsm()`.

## Verify
```bash
python m1_baseline/state_machine.py
```
All four scenarios should pass (including the new Scenario 4: Wall-Clock Timeout). The TIMEOUT state should fire for a 1ms deadline and be "sticky" — further calls to `accept()` return `False`.

## Reflection question
> Does adding `TIMEOUT` break the termination guarantee? Write a 1–2 sentence informal proof that it does not. (Hint: what matters is the transition set of the new state.)
