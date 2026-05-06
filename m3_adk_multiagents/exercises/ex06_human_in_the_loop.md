# Exercise 6 — Human-in-the-Loop Checkpoint `[Core]`

## Goal

Add an `after_agent_callback` to the negotiation orchestrator that **pauses and requires human approval** before the seller can accept any deal above $455,000. This teaches the production pattern of *human-in-the-loop governance* — ensuring autonomous agents don't make high-stakes decisions without oversight.

## Context

The current orchestrator has two exit conditions: seller calls `submit_decision(action='ACCEPT')` or `max_iterations` is reached. In both cases, the decision is **fully autonomous** — no human ever reviews it.

For a $450K real estate deal, that's reckless. Production agent systems need governance checkpoints:

- **Low-stakes decisions**: agent proceeds autonomously (counter-offers under $5K movement)
- **High-stakes decisions**: agent pauses, presents its reasoning, waits for human approval
- **Forbidden decisions**: callback blocks entirely (like the budget cap in Exercise 1)

Your checkpoint falls in the middle tier: the agent *can* accept, but a human must confirm.

## What you're building

A modified negotiation orchestrator:

```
m3_adk_multiagents/solution/ex06_human_in_the_loop/
└── negotiation/
    ├── __init__.py
    └── agent.py
```

Requirements:

1. **After the seller responds**, inspect `state['seller_decision']`. If `action == "ACCEPT"`:
   - If `price <= 455_000`: auto-approve. Print `[AUTO-APPROVED] Deal at $X — within auto-approval threshold.` and escalate (end loop).
   - If `price > 455_000`: **pause for human approval**. Print the deal details and prompt:
     ```
     ╔══════════════════════════════════════════════════════╗
     ║  HUMAN APPROVAL REQUIRED                            ║
     ║  Seller wants to accept at $457,000                 ║
     ║  This exceeds the auto-approval threshold ($455K)   ║
     ╚══════════════════════════════════════════════════════╝
     Approve this deal? [y/n]:
     ```
   - If the human types `y`: escalate (accept the deal). Print `[APPROVED] Human approved deal at $X.`
   - If the human types `n`: **do NOT escalate**. Overwrite `state['seller_decision']` to `{"action": "COUNTER", "price": price}` and print `[REJECTED] Human rejected deal. Continuing negotiation.` The loop continues with another round.

2. **Counter-offers** (`action == "COUNTER"`) proceed without any checkpoint — same as before.

3. The `$455,000` threshold should be a module-level constant `AUTO_APPROVE_CEILING = 455_000` — easy to reconfigure.

4. Use Python's built-in `input()` for the human prompt. This works in terminal; `adk web` won't support interactive input, so **test this exercise via a script or terminal, not the web UI**.

## Steps

1. Copy the orchestrator from `negotiation_agents/negotiation/agent.py`.
2. Modify `_check_agreement` (or add a new callback) to implement the three-tier logic:
   ```python
   AUTO_APPROVE_CEILING = 455_000

   def _check_agreement_with_approval(callback_context):
       decision = callback_context.state.get("seller_decision")
       if not isinstance(decision, dict) or decision.get("action") != "ACCEPT":
           return None  # Not an acceptance — proceed normally

       price = decision["price"]
       if price <= AUTO_APPROVE_CEILING:
           print(f"[AUTO-APPROVED] Deal at ${price:,}")
           callback_context.actions.escalate = True
           return None

       # Human checkpoint
       print(f"\n{'═'*54}")
       print(f"  HUMAN APPROVAL REQUIRED")
       print(f"  Seller wants to accept at ${price:,}")
       print(f"  Auto-approval threshold: ${AUTO_APPROVE_CEILING:,}")
       print(f"{'═'*54}")
       answer = input("Approve this deal? [y/n]: ").strip().lower()

       if answer == "y":
           print(f"[APPROVED] Human approved deal at ${price:,}")
           callback_context.actions.escalate = True
       else:
           print(f"[REJECTED] Human rejected. Continuing negotiation.")
           callback_context.state["seller_decision"] = {
               "action": "COUNTER",
               "price": price,
           }
       return None
   ```
3. Wire the callback on the seller agent: `after_agent_callback=_check_agreement_with_approval`.
4. Test scenario 1 — set buyer max to $450K so the deal closes below threshold → should auto-approve.
5. Test scenario 2 — set buyer max to $460K so the deal closes above $455K → should prompt for approval.
6. Test scenario 3 — get prompted, type `n` → negotiation should continue for another round.

## Verify

- **Deal at $452K**: `[AUTO-APPROVED]` printed, no human prompt, loop exits
- **Deal at $457K**: approval prompt displayed, typing `y` exits the loop with `[APPROVED]`
- **Deal at $457K, type `n`**: `[REJECTED]` printed, loop continues, seller makes another counter-offer next round
- **Counter-offers**: no approval prompt at any price — checkpoints only fire on `ACCEPT`
- Threshold is a single constant — changing `AUTO_APPROVE_CEILING` to `460_000` moves the goalpost

## Reflection

You've implemented a **three-tier governance model**: auto-approve (low-stakes), human checkpoint (high-stakes), hard block (Exercise 1's budget cap). In production, these tiers are everywhere:

- **What would you use instead of `input()` in a production system?** Think: Slack approval workflows, email confirmations, dashboard buttons, webhook callbacks. How would you make the agent *wait* for an async human response?
- **What happens if the human never responds?** Your current implementation blocks forever. How would you add a timeout — and what should the *default* action be on timeout? (Auto-approve? Auto-reject? Escalate to a manager?)
- **Could an adversarial agent bypass this checkpoint?** The checkpoint reads `state['seller_decision']`. What if the seller writes a different state key? How would you make the checkpoint tamper-proof?

---

> **Solution:** see `solution/ex06_human_in_the_loop/` for the complete, runnable orchestrator. The instructor will walk through it live during the review session.
