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

### Step 1 — Add the new state
In `m1_baseline/state_machine.py`, add `TIMEOUT` to the `NegotiationState` enum:

```python
class NegotiationState(Enum):
    IDLE        = auto()
    NEGOTIATING = auto()
    AGREED      = auto()
    FAILED      = auto()
    TIMEOUT     = auto()    # NEW: wall-clock deadline exceeded
```

### Step 2 — Add a timeout reason
In the `FailureReason` enum, add:

```python
WALL_CLOCK_TIMEOUT  = auto()    # Total negotiation time exceeded
```

### Step 3 — Update the transition table
Add `TIMEOUT` as a reachable state from `NEGOTIATING`, and give `TIMEOUT` an **empty** transition set:

```python
TRANSITIONS: dict[NegotiationState, set[NegotiationState]] = {
    NegotiationState.IDLE:        {NegotiationState.NEGOTIATING, NegotiationState.FAILED},
    NegotiationState.NEGOTIATING: {NegotiationState.NEGOTIATING, NegotiationState.AGREED,
                                   NegotiationState.FAILED, NegotiationState.TIMEOUT},
    NegotiationState.AGREED:      set(),
    NegotiationState.FAILED:      set(),
    NegotiationState.TIMEOUT:     set(),    # TERMINAL — no outgoing transitions
}
```

### Step 4 — Store and check the deadline
Add a `deadline_seconds` field to `FSMContext` and a `start_time` field (use `time.time()`). In `process_turn()`, check against the deadline:

```python
import time

# In FSMContext:
deadline_seconds: float = 60.0   # 60 seconds max
start_time: float = 0.0          # Set when negotiation starts

# In process_turn(), before the existing max_turns check:
elapsed = time.time() - self.context.start_time
if elapsed > self.context.deadline_seconds:
    self.state = NegotiationState.TIMEOUT
    self.context.failure_reason = FailureReason.WALL_CLOCK_TIMEOUT
    return False
```

### Step 5 — Update `is_terminal()` and `check_invariants()`
`is_terminal()` must include TIMEOUT:
```python
def is_terminal(self) -> bool:
    return self.state in {NegotiationState.AGREED, NegotiationState.FAILED, NegotiationState.TIMEOUT}
```

`check_invariants()` should check that TIMEOUT state also has a failure reason set.

## Verify
```bash
python m1_baseline/state_machine.py
```
The demo should still run to completion. All three existing scenarios should pass, and TIMEOUT should never fire during a fast demo.

## Reflection question
> Does adding `TIMEOUT` break the termination guarantee? Write a 1–2 sentence informal proof that it does not. (Hint: what matters is the transition set of the new state.)
