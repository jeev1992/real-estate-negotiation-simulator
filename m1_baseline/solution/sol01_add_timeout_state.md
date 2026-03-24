# Solution 1: Add a TIMEOUT Terminal State

## How to apply

All the code is already in `m1_baseline/state_machine.py` as **commented-out blocks** marked with `── Exercise 1 ──`. Search for `Exercise 1` to find all 11 locations, and uncomment/edit each one.

The changes fall into six categories:

### 1. Add import and new enum members

```python
import time                    # Add at top of file

class NegotiationState(Enum):
    IDLE        = auto()
    NEGOTIATING = auto()
    AGREED      = auto()
    FAILED      = auto()
    TIMEOUT     = auto()       # NEW

class FailureReason(Enum):
    MAX_TURNS_EXCEEDED  = auto()
    REJECTED_BY_BUYER   = auto()
    REJECTED_BY_SELLER  = auto()
    WALL_CLOCK_TIMEOUT  = auto()   # NEW
```

### 2. Update FSMContext

```python
@dataclass
class FSMContext:
    turn_count:        int                      = 0
    max_turns:         int                      = 5
    agreed_price:      Optional[float]          = None
    failure_reason:    Optional[FailureReason]  = None
    deadline_seconds:  float                    = 60.0    # NEW
    start_time:        float                    = 0.0     # NEW
```

### 3. Update the transition table

```python
TRANSITIONS: dict[NegotiationState, set[NegotiationState]] = {
    NegotiationState.IDLE:        {NegotiationState.NEGOTIATING, NegotiationState.FAILED},
    NegotiationState.NEGOTIATING: {NegotiationState.NEGOTIATING, NegotiationState.AGREED,
                                   NegotiationState.FAILED, NegotiationState.TIMEOUT},
    NegotiationState.AGREED:      set(),
    NegotiationState.FAILED:      set(),
    NegotiationState.TIMEOUT:     set(),    # TERMINAL: empty set
}
```

### 4. Update `start()` to record the start time

```python
def start(self) -> bool:
    if self.state != NegotiationState.IDLE:
        return False
    self.state = NegotiationState.NEGOTIATING
    self.context.start_time = time.time()   # NEW
    return True
```

### 5. Update `process_turn()` with deadline check

Add this block at the beginning of `process_turn()`, right after the `if not self.is_active` check:

```python
# Wall-clock timeout check (NEW)
elapsed = time.time() - self.context.start_time
if elapsed > self.context.deadline_seconds:
    self.state = NegotiationState.TIMEOUT
    self.context.failure_reason = FailureReason.WALL_CLOCK_TIMEOUT
    return False
```

### 6. Update `is_terminal()` and `check_invariants()`

```python
def is_terminal(self) -> bool:
    return self.state in {NegotiationState.AGREED, NegotiationState.FAILED, NegotiationState.TIMEOUT}
```

In `check_invariants()`, add:
```python
if self.state == NegotiationState.TIMEOUT:
    assert self.context.failure_reason is not None, (
        "TIMEOUT state requires failure_reason to be set"
    )
```

## Termination proof

Adding `TIMEOUT` does **not** break the termination guarantee because:
1. `TIMEOUT` has an empty transition set (no outgoing transitions), so once entered it cannot be exited.
2. The deadline check in `process_turn()` provides an **additional** path to a terminal state, which can only make termination happen sooner, never later.

## Verify
```bash
python m1_baseline/state_machine.py
```
