# Module 1 — Demo Walkthrough & Concept Notes

> **Audience:** Learners reviewing Module 1 after the workshop, or anyone working through the demos for the first time who wants narrative context for what they're seeing.
> **Prerequisites:** None — these notes assume you're seeing the M1 demos for the first time.
> **Read this *while* running:** `m1_baseline/naive_negotiation.py` and `m1_baseline/state_machine.py`. Each section corresponds to one demo run.
> **Read this next:** [`agents_fundamentals.md`](agents_fundamentals.md) for the conceptual deep-dive that this demo motivates.
>
> **TL;DR:** This file is a guided tour of what you'll see when you run each M1 demo — what the output looks like, why it looks that way, what bug it's exposing, and how the FSM fixes it. Read it as a companion to running the code, not as a standalone reference.

---

## naive_negotiation.py — The Intentionally Broken Baseline

**File:** `m1_baseline/naive_negotiation.py` (~520 lines)

### What it teaches
Everything that goes wrong when you build the "obvious" LLM agent system: raw strings, regex parsing, `while True`, no termination guarantee, hardcoded data. This is the motivating failure for the entire workshop.

### How to run

```bash
python m1_baseline/naive_negotiation.py   # requires OPENAI_API_KEY
```

Runs 3 demos in order: optimistic case, impossible case, static failure modes.

---

### Demo 1 — "When It Works (By Luck)"

**Setup:** Buyer max $460K vs Seller min $445K — ZOPA exists ($445K–$460K overlap).

**Actual output:**
```
[Turn 0] Alice (Buyer):
  I am prepared to offer $424,580 for the property...

[Turn 1] Bob (Seller):
  ...I am prepared to present a counter-offer of $453,150.

[Turn 2] Alice (Buyer):
  ACCEPT: I am delighted to proceed at $453,150.

[Turn 3] Bob (Seller):
  DEAL! We have a sale at $453,150.00. Congratulations!

[OK] Deal reached at $453,150.00 after 3 turns
Buyer saved $31,850 from listing price of $485,000
```

**Why it "worked":**
- The seller's counter ($453,150) happened to be below buyer's max ($460K)
- The buyer's LLM happened to start its response with "ACCEPT"
- The seller's LLM happened to say "DEAL!"
- The regex happened to extract the right price

**What could have gone wrong (but didn't this time):**

| Risk | What would happen |
|------|-------------------|
| Buyer says "I agree" instead of "ACCEPT" | Seller doesn't detect acceptance → loop continues |
| Seller says "Sold!" instead of "DEAL!" | No termination trigger → loop continues |
| Seller mentions renovation costs before counter price | Regex grabs wrong number |
| LLM returns written-out number ("four hundred fifty") | Regex returns None → silent failure |

**Key insight:** The code worked because the LLM's phrasing happened to match the regex and string checks. Change the temperature, the model, or the prompt wording — and it breaks.

---

### Demo 2 — "The Infinite Loop (No ZOPA)"

**Setup:** Buyer max $420K vs Seller min $450K — NO overlap. Agreement is mathematically impossible.

**Actual output:**
```
[Turn 0] Buyer:  "$387,660"
[Turn 1] Seller: "Counter at $453,150"
[Turn 2] Buyer:  "Final offer $420,000"          ← hit max budget
[Turn 3] Seller: "Counter at $450,000"           ← hit floor
[Turn 4] Buyer:  "Final offer $420,000"           ← stuck, repeating
[Turn 5] Seller: "Counter at $450,000"            ← stuck, repeating
[Turn 6] Buyer:  "Final offer $420,000"           ← still stuck
[Turn 7] Seller: "DEAL! Sale at $420,000"         ← WHAT?!
```

**Result:** `success=True, price=$420,000` — the seller accepted a price BELOW its own minimum ($450K).

**What happened:**

1. The buyer hit its max budget ($420K) at turn 2 and kept repeating "final offer $420,000"
2. The seller hit its floor ($450K) at turn 3 and kept repeating "counter at $450,000"
3. After 4 rounds of identical messages, the LLM got fatigued and said "DEAL!" at $420K
4. `"DEAL" in message.upper()` matched → termination triggered
5. The regex extracted $420,000 → reported as the deal price
6. **No code checked whether $420K >= seller's minimum.** The business rule was violated silently.

**This is Failure Mode #6:** The LLM decides termination, not the code. The system has no way to enforce business rules. The seller's constraint (`min_price = 450_000`) exists only as a prompt hint — the LLM is free to ignore it.

**Cost implication:** Even with the demo cap at 8 turns, this burned 8 LLM API calls for a negotiation that was doomed from turn 1. In production with `max_turns=100`, that's 100 wasted calls — potentially $1+ in API costs with zero chance of a valid outcome.

**How the FSM fixes this:** `NegotiationFSM.process_turn()` increments `turn_count` each round. At `max_turns=5`, it transitions to `FAILED` with `failure_reason=MAX_TURNS_EXCEEDED`. The loop stops by design, not by LLM whim. Cost: 0 additional API calls for the termination decision.

---

### Demo 3 — Static Failure Modes

These use hardcoded strings — no LLM calls. They demonstrate exactly how the regex and string matching break.

**Failure 1 — Ambiguous price extraction:**
```
Input:  "I spent $350,000 on renovations, but my counter-offer is $477,000"
Regex:  r'\$?(\d[\d,]*)'
Output: $350,000  ← WRONG! Got renovation cost, not the offer.
```
The regex grabs the FIRST number. If the LLM mentions any dollar amount before the actual offer, the parser extracts the wrong price. The negotiation proceeds on corrupted data with no error.

**Fix (M3):** `submit_decision(action="COUNTER", price=477000)` — the price is a typed `int` parameter, not parsed from prose.

**Failure 2 — Silent parse failure:**
```
Input:  "I'd like to offer four hundred and thirty thousand dollars"
Regex:  None  ← no digits found
```
The regex returns `None`. The buyer's `respond_to_counter()` falls through to: `"My offer stands at $424,580"` — repeating the previous offer. The negotiation silently continues on stale data. No error is raised, no log entry, no way to detect the corruption.

**Fix (M3):** Pydantic validation / structured tool parameters. Missing required fields raise immediately.

**Failure 3 — No ZOPA (infinite loop):**
```
Buyer max: $430,000  |  Seller min: $450,000  |  Gap: $20,000
```
These agents can NEVER agree. But `while True` has no awareness of this. It will run until:
- The emergency exit at `max_turns` (100 in production → 100 wasted API calls)
- Or the LLM accidentally says "DEAL" or "REJECT" (Demo 2 showed this happening)

**Fix (M1):** `FSM.process_turn()` at `max_turns=5` → `FAILED`. Deterministic, cheap, immediate.

**Failure 4 — Hardcoded prices:**
```python
SELLER_MIN_PRICE = 445_000   # in source code, visible to everyone
```
The seller's floor is a Python constant. It can't be updated without a code change. It's visible to anyone reading the source. In a real negotiation, this would be confidential seller data retrieved at runtime.

**Fix (M2):** `get_minimum_acceptable_price()` from the MCP inventory server. The price lives in the server, not the agent code. The buyer's allowlist blocks this tool — information asymmetry enforced at runtime.

**Failure 5 — String-match termination:**
```
"DEAL-breaker — I won't go lower"     → matches "DEAL"  ← FALSE POSITIVE
"I think we're close, let's finalize" → no match         ← MISSED AGREEMENT
"I simply cannot go lower"            → no match         ← MISSED REJECTION
```
The termination check `"DEAL" in message.upper()` matches substrings. "DEAL-breaker" triggers a false deal. "Let's finalize" (a clear agreement signal) is missed entirely.

**Fix (M3):** `submit_decision(action="ACCEPT", price=445000)` — structured tool call, not text parsing. The callback reads `state["seller_decision"]["action"]`, a dict field. No substring matching.

**Meta-observation:** We hit this exact bug in M3 during development. The seller's MCP tool returned "minimum acceptable price" — and `"ACCEPT" in "acceptable"` was `True`, false-triggering the acceptance callback. The fix was `submit_decision` — a structured signal instead of text parsing.

---

## state_machine.py — The Termination Guarantee

**File:** `m1_baseline/state_machine.py` (~350 lines)

### What it teaches
How a finite state machine guarantees that the negotiation loop MUST stop — by design, not by luck. Terminal states have empty transition sets. Combined with a turn cap, the loop is bounded.

### How to run

```bash
python m1_baseline/state_machine.py   # no API key needed
```

No LLM calls. Pure logic. Runs 3 scenarios.

### Key code elements

```python
class NegotiationState(Enum):
    IDLE        = auto()    # Not started
    NEGOTIATING = auto()    # Offers being exchanged
    AGREED      = auto()    # Terminal: deal ✓
    FAILED      = auto()    # Terminal: no deal ✗

TRANSITIONS = {
    IDLE:        {NEGOTIATING, FAILED},
    NEGOTIATING: {NEGOTIATING, AGREED, FAILED},
    AGREED:      set(),    # ← EMPTY = no way out
    FAILED:      set(),    # ← EMPTY = no way out
}
```

**Why it MUST stop:**
1. `AGREED` and `FAILED` have empty transition sets — once entered, the FSM can't move
2. `process_turn()` increments `turn_count`, capped at `max_turns`
3. Either an agent calls `accept()`/`reject()`, or the cap forces `FAILED`
4. The `while not fsm.is_terminal()` loop exits because one of these MUST happen

### Scenario 1 — Deal reached (round 3 of 5)

```
Initial:        NegotiationFSM(state=IDLE, turn=0/5)
After start():  NegotiationFSM(state=NEGOTIATING, turn=0/5)
Round 1:        NegotiationFSM(state=NEGOTIATING, turn=1/5)  →  continues=True
Round 2:        NegotiationFSM(state=NEGOTIATING, turn=2/5)  →  continues=True
Round 3:        NegotiationFSM(state=NEGOTIATING, turn=3/5)  →  continues=True
After accept(): NegotiationFSM(state=AGREED, turn=3/5)
is_terminal():  True
agreed_price:   $449,000
Invariants:     PASS
```

**Key observation:** The FSM accepted at round 3 of 5. It didn't need all 5 rounds. The cap is a safety net, not a target. This maps to ADK's `max_iterations=5` — the LoopAgent stops early when `escalate=True`, and the cap prevents runaway if escalation never fires.

### Scenario 2 — Buyer walks away (round 2)

```
After reject(): NegotiationFSM(state=FAILED, turn=2/5)
is_terminal():  True
failure_reason: REJECTED_BY_BUYER
accept() after reject: returned False  ← state is LOCKED
```

**Key observation:** After `reject()`, the FSM is in `FAILED` — a terminal state. Calling `accept(price=440000)` returns `False`. The terminal state is sticky — you can't get out. This is the safety guarantee: once a terminal decision is made, it can't be overridden. In the naive version, there's no concept of "locked" — the loop keeps going.

### Scenario 3 — Max turns exceeded

```
Round 1: returned=True, state=NEGOTIATING
Round 2: returned=True, state=NEGOTIATING
Round 3: returned=True, state=NEGOTIATING
Round 4: returned=True, state=NEGOTIATING
Round 5: returned=False, state=FAILED   ← forced by cap
  → Terminated at round 5
failure_reason: MAX_TURNS_EXCEEDED
```

**Key observation:** The code tried 9 rounds but the FSM stopped at 5. `process_turn()` returned `False` and transitioned to `FAILED` automatically. No emergency exit needed — the termination is by design.

**Compare to Demo 2:** The naive version ran 7 turns (capped at 8 for the demo, 100 in production) and "agreed" at an impossible price. The FSM would have stopped at turn 5 with `FAILED` — zero wasted API calls after the cap.

---

## Connection to the rest of the workshop

### M1 → M2 (MCP)

| M1 Problem | M2 Solution |
|------------|-------------|
| #8 Hardcoded prices (`SELLER_MIN_PRICE = 445_000`) | `get_minimum_acceptable_price()` from MCP inventory server |
| Prices visible in source code | Floor price lives in the server, not the agent |
| No market data for offers | `get_market_price()` + `calculate_discount()` from MCP pricing server |
| Can't update prices without code change | MCP server returns current data at runtime |

### M1 → M3 (ADK)

| M1 Concept | M3 Equivalent |
|------------|---------------|
| `NegotiationState` enum | `LoopAgent` + `SequentialAgent` |
| `max_turns = 5` | `max_iterations = 5` |
| `is_terminal()` → True | `escalate = True` → LoopAgent stops |
| `TRANSITIONS[AGREED] = set()` | `_check_agreement` callback |
| `process_turn()` increments counter | LoopAgent tracks iteration count |
| Terminal states are sticky | Escalation prevents next iteration |

### The `submit_decision` connection

The fragile parsing in `naive_negotiation.py` (problems #5 and #6) is exactly what we hit in M3 when building the negotiation orchestrator:

1. **M1 problem:** `"DEAL" in message.upper()` matches "DEAL-breaker" (false positive)
2. **M3 version 1:** `"ACCEPT" in response.upper()` matched "minimum acceptable price" (false positive from MCP tool output)
3. **M3 fix:** `submit_decision(action="ACCEPT", price=445000)` — structured tool call, callback reads `state["seller_decision"]["action"]`, no text parsing

The progression: **M1 shows the problem → M3 hits it again in practice → structured tools fix it permanently.**

---

## Key teaching points for class

1. **"This code is intentionally broken."** Start by showing the header comment. Set the expectation that Demo 1 will "work" but Demo 2 will reveal the fragility.

2. **"Watch Demo 2 carefully."** The seller accepted below its own floor. The LLM got fatigued and said "DEAL!" — no code caught the violation. This is the motivating failure for the entire architecture.

3. **"The regex is the villain."** `r'\$?(\d[\d,]*)'` — optional dollar sign, first number wins. Show Failure Mode 1 (renovation cost extracted instead of counter) and Failure Mode 2 (written-out number → None → silent failure).

4. **"Terminal states have empty transition sets."** Draw the FSM diagram. `TRANSITIONS[AGREED] = set()` means no outgoing edges. Once you're in AGREED, you can't leave. That emptiness IS the guarantee.

5. **"The FSM has no LLM."** `state_machine.py` doesn't call any API. It's pure logic. The guarantee comes from the state machine structure, not from prompt engineering.

6. **"Everything in this module maps forward."** Show the problem→solution table. Students should mentally tag each problem as they see it, knowing they'll see the fix in M2 or M3.

---

## Questions students might ask

**"Why not just use structured output (JSON mode) to fix the parsing?"**
Good instinct — and M3 does this via `submit_decision` tool parameters. But structured output alone doesn't fix problems #3 (no state machine), #4 (no turn limits), or #6 (no termination guarantee). The FSM is still needed for control flow.

**"Why not use function calling from the start?"**
Because function calling still requires the LLM to decide WHEN to call the function. If the LLM says "I accept your offer" in prose without calling the accept function, the system misses it. `submit_decision` in M3 works because the instruction says "you MUST call submit_decision" — but that's still a prompt-level suggestion, not a code-level guarantee.

**"Does the FSM replace the LLM?"**
No — the FSM controls the LOOP, not the REASONING. In M3's orchestrator, the LLM still decides what price to offer and what justification to write. The FSM (via LoopAgent) controls how many rounds happen and when to stop.

**"Why 5 max turns?"**
Arbitrary but practical. Real estate negotiations typically take 2-4 rounds. 5 gives room for back-and-forth with a tight cap. In M3, `max_iterations=5` is the same number. Change it to 3 and the agents have less room to negotiate. Change it to 10 and you burn more API calls.
