# Exercise 2 — Stuck-Detection in Session State `[Core]`

## Goal

Modify the negotiation orchestrator to **detect when the negotiation has stalled** — two or more consecutive rounds where the offer moves less than $5,000 — and **escalate early** to terminate the loop. This builds the production pattern for *non-progressing agent detection*.

## Context

The current orchestrator uses two stop conditions:
- `max_iterations=5` (hard cap)
- Seller's `submit_decision(action='ACCEPT', ...)` (deal reached)

Both are correct but coarse. In a real no-ZOPA scenario, the agents will repeat near-identical offers for all 5 rounds — burning $5+ in API calls — before the cap finally fires. **A smarter loop detects the stall and exits at round 3 or 4 instead of running through 5.**

## What you're building

A modified `negotiation` agent in a new package:

```
solution/ex02_stuck_detection/
└── negotiation/
    ├── __init__.py
    └── agent.py
```

Requirements:

1. After each round (i.e., in `after_agent_callback` on the `seller`), append the round's offers to `state['offer_history']`. Each entry should record at least the buyer offer and seller response price.

2. Add a *stall check*: if the last 2 entries in `offer_history` have **price movement < $5,000 across both rounds**, set `escalate=True` (loop exits early) and write `state['stall_reason']` for visibility.

3. Keep the existing acceptance check — `submit_decision(action='ACCEPT')` should still escalate. Stall is a *second* exit condition, not a replacement.

4. The buyer/seller agents themselves don't need to change much — just ensure their offers get tracked.

## Steps

1. Copy the canonical orchestrator from `negotiation_agents/negotiation/agent.py` as your starting point.
2. Add a function `_track_round(callback_context)` that runs after the seller and appends to `offer_history`. You can extract prices from `state['buyer_offer']` and `state['seller_decision']`.
3. Add a function `_check_stall(callback_context)` that inspects the last 3 entries and escalates if movement is below threshold.
4. Combine: `after_agent_callback=_track_round` (which then calls `_check_stall` internally), or use a sequence — your choice.
5. Run the healthy scenario:
   ```bash
   adk web m3_adk_multiagents/solution/ex02_stuck_detection/
   ```
6. Pick **`negotiation`** from the dropdown.
7. Send: *"Start the negotiation for 742 Evergreen Terrace."*
   - Watch the **terminal** for `[stall-check]` round logs.
   - With default settings (buyer max $460K, seller floor $445K), ZOPA exists → should end on `ACCEPT` around round 2–3.
8. To test the stalled scenario:
   - Stop `adk web` (Ctrl+C).
   - Set the environment variable to drop the buyer's budget below the seller's floor:
     ```powershell
     $env:STALL_DEMO = "true"
     ```
   - Restart:
     ```bash
     adk web m3_adk_multiagents/solution/ex02_stuck_detection/
     ```
   - New session, send: *"Start the negotiation."*
   - The buyer's budget is now $440K, the seller's floor is $445K — no ZOPA.
   - Expected: stall detected at round 3–4 with `[stall-check] STALL DETECTED` in terminal.
   - Check the **State tab** — `stall_reason` should be populated.
   - Unset when done:
     ```powershell
     Remove-Item Env:STALL_DEMO
     ```

## Verify

- Healthy negotiation (with ZOPA): exits on `ACCEPT` as before, never triggers the stall check
- Doomed negotiation (no ZOPA): exits at round 3-4 with `state['stall_reason']` populated
- Without your stall check, the same doomed scenario runs 5 rounds — you can compare

## Reflection

The stall threshold ($5K, 2 rounds) is hardcoded. In production, what would you parametrize and why?

Hint: think about the **calibration problem** — too aggressive a threshold ends real negotiations early; too lenient burns API calls. How would you choose the threshold *without guessing*?

---

> **Solution:** see `solution/ex02_stuck_detection/` for the complete, runnable orchestrator. The instructor will walk through it live during the review session.
