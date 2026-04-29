# Module 1 — Slide Deck Specification

---

## Slide 1: Module 1 Title

**Title:** Module 1 — Why Naive AI Agents Break

**Body:**

**The goal:** See exactly how a "simple" LLM negotiation fails — then fix it

By the end of this module you'll have:
- Watched a naive negotiation **work by luck** (Demo 1)
- Watched it **fail catastrophically** (Demo 2)
- Seen **5 concrete failure modes** with code examples
- Built a **finite state machine** that guarantees termination

Every problem in this module maps to a solution in Modules 2 and 3.

```bash
python m1_baseline/naive_negotiation.py   # requires OPENAI_API_KEY
python m1_baseline/state_machine.py       # no API key needed
```

---

## Slide 2: The 10 Problems

**Title:** 10 Ways Naive Agent Systems Fail

**Body:**

```python
# naive_negotiation.py — the "obvious" implementation
while True:                           # Problem #3: no state machine
    message = _call_llm(prompt)       # Problem #1: raw strings
    price = re.search(r'\$?(\d[\d,]*)', message)  # Problem #5: fragile regex
    if "DEAL" in message.upper():     # Problem #6: unreliable termination
        break
```

| # | Problem | What goes wrong | Fixed by |
|---|---------|----------------|----------|
| 1 | Raw strings | LLM returns anything | A2A structured messages |
| 2 | No schema | Can't validate response | Pydantic / A2A DataPart |
| 3 | No state machine | `while True` loop | FSM (this module) → LoopAgent (M3) |
| 4 | No turn limits | Can loop forever | `max_turns` → `max_iterations` |
| 5 | Fragile regex | Extracts wrong price | `price: float` field |
| 6 | No termination guarantee | "DEAL-breaker" matches "DEAL" | Terminal states / `submit_decision` |
| 7 | Silent failures | Bad parse → keeps going | Pydantic validation |
| 8 | Hardcoded prices | No market data | MCP servers (M2) |
| 9 | No observability | Can't audit what happened | ADK events / A2A lifecycle |
| 10 | No evaluation | Can't measure quality | Session analytics |

These aren't hypothetical — we'll see #5 and #6 happen live in the demo.

---

## Slide 3: Demo 1 — When It Works (By Luck)

**Title:** Demo 1 — "It Works!" (Fragile)

**Body:**

```bash
python m1_baseline/naive_negotiation.py
```

**Setup:** Buyer max $460K vs Seller min $445K — there IS overlap (ZOPA exists).

**What happened:**
```
[Turn 0] Buyer:  "I offer $424,580"
[Turn 1] Seller: "Counter-offer of $453,150"
[Turn 2] Buyer:  "ACCEPT at $453,150"
[Turn 3] Seller: "DEAL! Sale at $453,150"
```

**Looks great!** Deal in 3 turns, buyer saved $31,850. But notice:
- The buyer happened to say "ACCEPT" — what if it said "I agree"? No termination.
- The seller happened to say "DEAL!" — what if it said "Sold!"? Loop continues.
- The regex happened to grab the right price — what if the seller mentioned renovation costs first?

**This worked by luck, not by design.** The LLM's phrasing determined whether the code terminated correctly.

---

## Slide 4: Demo 2 — The Infinite Loop

**Title:** Demo 2 — When It Breaks (No ZOPA)

**Body:**

**Setup:** Buyer max $420K vs Seller min $450K — NO overlap. Agreement is **mathematically impossible**.

**What happened:**
```
[Turn 0] Buyer:  "$387,660"
[Turn 1] Seller: "Counter at $453,150"
[Turn 2] Buyer:  "Final offer $420,000"          ← hit max budget
[Turn 3] Seller: "Counter at $450,000"           ← hit floor
[Turn 4] Buyer:  "Final offer $420,000"           ← stuck
[Turn 5] Seller: "Counter at $450,000"            ← stuck
[Turn 6] Buyer:  "Final offer $420,000"           ← stuck
[Turn 7] Seller: "DEAL! Sale at $420,000"         ← WAIT WHAT?!
```

**The seller accepted $420,000 — which is BELOW its own minimum of $450,000.**

The LLM got tired of repeating itself and said "DEAL!" The string match `"DEAL" in message.upper()` triggered, and the negotiation "succeeded" at an impossible price.

**This is Failure Mode #6:** The LLM decides termination, not the code. The system has no way to enforce business rules.

In production with `max_turns=100`, this would burn 100 LLM API calls before the emergency exit — for a negotiation that was doomed from turn 1.

---

## Slide 5: Failure Modes (Static Demos)

**Title:** 5 Concrete Failure Modes

**Body:**

**Failure 1 — Wrong price extracted:**
```
LLM: "I spent $350,000 on renovations, my counter is $477,000"
Regex: $350,000  ← WRONG! Got renovation cost, not the offer
```

**Failure 2 — Silent parse failure:**
```
LLM: "I'd like to offer four hundred and thirty thousand dollars"
Regex: None  ← negotiation continues on corrupted data, no error raised
```

**Failure 3 — Infinite loop (no ZOPA):**
```
Buyer max: $430,000  |  Seller min: $450,000  |  Gap: $20,000
These agents can NEVER agree. while True runs forever.
```

**Failure 4 — Hardcoded prices:**
```python
SELLER_MIN_PRICE = 445_000  # visible in source code, stale, no market data
# Should come from: MCP get_minimum_acceptable_price()
```

**Failure 5 — String matching is unreliable:**
```
"DEAL-breaker — I won't go lower"  →  matches "DEAL"  ← FALSE POSITIVE
"I think we're close, let's finalize"  →  no match  ← MISSED AGREEMENT
```

Every one of these is fixed by a specific component in M2 or M3.

---

## Slide 6: The FSM Fix

**Title:** Finite State Machine — Guaranteed Termination

**Body:**

```python
class NegotiationState(Enum):
    IDLE        = auto()
    NEGOTIATING = auto()
    AGREED      = auto()   # Terminal ✓
    FAILED      = auto()   # Terminal ✗

TRANSITIONS = {
    IDLE:        {NEGOTIATING, FAILED},
    NEGOTIATING: {NEGOTIATING, AGREED, FAILED},
    AGREED:      set(),    # ← EMPTY = no way out
    FAILED:      set(),    # ← EMPTY = no way out
}
```

**Why it MUST stop:**
1. Terminal states have **empty transition sets** — once entered, can't leave
2. Every turn increments `turn_count`, capped at `max_turns`
3. Either an agent reaches AGREED/FAILED, or the cap forces FAILED

**Diagram:**
```
         IDLE
          │
    start()
          │
          ▼
    ┌──────────┐
    │NEGOTIATING│◄─── process_turn() loops here
    └────┬─────┘      (turn_count increments each time)
         │
    ┌────┼────┐
    │         │
accept()  reject() / max_turns
    │         │
    ▼         ▼
 AGREED    FAILED
 set()     set()     ← EMPTY = terminal, locked forever
```

---

## Slide 7: FSM Demo Results

**Title:** FSM — What Actually Happened

**Body:**

```bash
python m1_baseline/state_machine.py   # no API key needed
```

**Scenario 1 — Deal reached (round 3 of 5):**
```
IDLE → NEGOTIATING → round 1 → round 2 → round 3 → AGREED ($449,000)
is_terminal(): True  |  Invariants: PASS
```

**Scenario 2 — Buyer walks away (round 2):**
```
IDLE → NEGOTIATING → round 1 → round 2 → reject() → FAILED
accept() after reject: returned False  ← state is LOCKED
```

**Scenario 3 — Max turns exceeded:**
```
Round 1: True  →  Round 2: True  →  ...  →  Round 5: False → FAILED
failure_reason: MAX_TURNS_EXCEEDED
```

**The key guarantee:** In Demo 2 (no ZOPA, $420K vs $450K), the naive version ran 7+ turns and "agreed" at an impossible price. The FSM would hit `max_turns=5` → FAILED. Zero wasted API calls after that.

---

## Slide 8: From FSM to ADK

**Title:** M1 → M3 — Same Principle, Different Scale

**Body:**

| M1 FSM | M3 ADK |
|--------|--------|
| `NegotiationState` enum | `LoopAgent` + `SequentialAgent` |
| `max_turns = 5` | `max_iterations = 5` |
| `is_terminal()` | `escalate = True` |
| `TRANSITIONS[AGREED] = set()` | `_check_agreement` callback |
| `process_turn()` increments counter | LoopAgent tracks iteration count |
| No LLM, pure logic | Real LLM + MCP tools |

**The FSM is the conceptual foundation.** ADK's LoopAgent is the same idea — bounded iteration with explicit terminal conditions — but at the scale of real agents with tools, state, and network communication.

**What the FSM doesn't solve** (and M2/M3 do):
- Problem #8: Hardcoded prices → MCP servers (M2)
- Problem #1: Raw strings → A2A structured messages (M3)
- Problem #5: Fragile regex → `submit_decision` tool (M3)
- Problem #9: No observability → ADK event stream (M3)

---

## Slide 9: Exercises

**Title:** Hands-On Exercises

**Body:**

| Exercise | Difficulty | Task |
|----------|-----------|------|
| `ex01_add_timeout_state.md` | Core | Add a `TIMEOUT` terminal state to the FSM |
| `ex02_compare_failure_modes.md` | Core | Compare naive vs FSM failure handling |

**Exercise 1 — Add TIMEOUT:**
- Add `TIMEOUT` to `NegotiationState`
- Add `WALL_CLOCK_TIMEOUT` to `FailureReason`
- Add deadline check in `process_turn()`
- Verify: `TRANSITIONS[TIMEOUT] = set()` — still terminates

**Key insight:** Adding a new terminal state **cannot break** the termination guarantee because terminal states have empty transition sets. More terminal states = more paths to stopping, never fewer.

Solutions are in `m1_baseline/solution/`.
