# Exercise 3 — Reimplement the FSM Core in TypeScript `[Stretch]`

## Goal
Prove that the FSM termination pattern is **framework-independent** by reimplementing the core state machine in a different language. This demonstrates that the guarantees come from the mathematical structure (finite states, bounded counters, empty terminal transition sets), not from Python-specific features.

## Why this matters
In production, negotiation agents may run in different runtimes (Python backend, TypeScript frontend, Go microservice). The FSM pattern must work everywhere. If your termination guarantee only works in Python, it's not a real guarantee — it's an implementation detail.

## Steps

### Step 1 — Set up a TypeScript file

Create `m1_baseline/state_machine.ts`:

```typescript
// Negotiation FSM — TypeScript implementation
// Prove: same states, same transition table, same guarantee

enum NegotiationState {
    IDLE = "IDLE",
    NEGOTIATING = "NEGOTIATING",
    AGREED = "AGREED",
    FAILED = "FAILED",
}

enum FailureReason {
    MAX_TURNS_EXCEEDED = "MAX_TURNS_EXCEEDED",
    REJECTED_BY_BUYER = "REJECTED_BY_BUYER",
    REJECTED_BY_SELLER = "REJECTED_BY_SELLER",
}
```

### Step 2 — Implement the transition table and core methods

Port these from the Python version:
- `TRANSITIONS` map: `Map<NegotiationState, Set<NegotiationState>>`
- `isTerminal()`: check if current state's transition set is empty
- `start()`: IDLE → NEGOTIATING
- `processTurn()`: increment counter, enforce max_turns
- `accept(price)`: NEGOTIATING → AGREED
- `reject()`: NEGOTIATING → FAILED

### Step 3 — Implement `checkInvariants()`

Port the invariant checks:
- Turn count ≥ 0 and ≤ max_turns
- AGREED state has agreed_price set
- FAILED state has failure_reason set
- Terminal states have empty transition sets

### Step 4 — Write a demo that matches the Python output

Run the same three scenarios:
1. Deal reached (AGREED)
2. Buyer rejected (FAILED)
3. Max turns exceeded (FAILED)

### Step 5 — Compare

Run both implementations side by side:
```bash
python m1_baseline/state_machine.py
npx ts-node m1_baseline/state_machine.ts
```

## Verify
- Both implementations produce the same state transitions for all 3 scenarios
- `checkInvariants()` catches the same violations
- The termination guarantee holds: terminal states have empty transition sets

## Reflection question
> Did the transition table structure change at all between Python and TypeScript? What does this tell you about where the termination guarantee actually lives — in the language, or in the data structure?
