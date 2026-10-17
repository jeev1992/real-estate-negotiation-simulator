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
m2_adk_multiagents/solution/ex06_human_in_the_loop/
└── negotiation/
    ├── __init__.py
    └── agent.py
```

Requirements:

1. **After each round**, inspect `state['seller_decision']`. If `action == "ACCEPT"`:
   - If `price <= 455_000`: auto-approve. Print `[AUTO-APPROVED] Deal at $X — within threshold`, record the outcome in state, and escalate (end the loop).
   - If `price > 455_000`: **pause for human approval**. Print `[PENDING APPROVAL] Deal at $X — above threshold, asking user`, write `state['pending_approval'] = {"price": X, "threshold": 455_000}`, and escalate — the loop stops and the question goes to the human.

2. **Counter-offers** (`action == "COUNTER"`) proceed without any checkpoint — same as before.

3. The `$455,000` threshold should be a module-level constant `AUTO_APPROVE_CEILING = 455_000` — easy to reconfigure.

4. **Ask the human in the chat UI, not with `input()`.** `adk web` runs your agent inside a web server, so an `input()` call would block the server, not prompt the user. Instead, wrap the negotiation loop in a **parent `LlmAgent`** (via `AgentTool`). When the loop exits with a pending approval, the parent asks the user in the chat whether to APPROVE or REJECT.

5. **Record the human's answer in code.** Give the parent two function tools:
   - `approve_deal` — prints `[APPROVED] Human approved deal at $X.`, clears `pending_approval`, marks the deal closed in state.
   - `reject_deal` — prints `[REJECTED] Human rejected deal at $X.`, clears `pending_approval`, and overwrites `state['seller_decision']` to `{"action": "COUNTER", "price": X}` so calling the loop again continues the negotiation.

   The parent's instruction should template the state it needs (e.g. `{pending_approval?}`, `{deal_outcome?}`) — an LLM can't "read the session state" unless you put it in its prompt.

## Steps

1. Copy the orchestrator from `negotiation_agents/negotiation/agent.py`.
2. Add the three-tier check as an `after_agent_callback` on the round (`SequentialAgent`), so it runs after the seller each round:
   ```python
   AUTO_APPROVE_CEILING = 455_000

   def _check_agreement_with_approval(callback_context):
       decision = callback_context.state.get("seller_decision")
       if not isinstance(decision, dict) or decision.get("action") != "ACCEPT":
           return None  # Not an acceptance — proceed normally

       price = decision["price"]
       if price <= AUTO_APPROVE_CEILING:
           print(f"[AUTO-APPROVED] Deal at ${price:,} — within threshold")
           callback_context.state["deal_outcome"] = f"Deal auto-approved at ${price:,}."
           callback_context.actions.escalate = True
           return None

       # Human checkpoint: stop the loop and hand the question to the parent agent
       print(f"[PENDING APPROVAL] Deal at ${price:,} — above threshold, asking user")
       callback_context.state["pending_approval"] = {"price": price, "threshold": AUTO_APPROVE_CEILING}
       callback_context.actions.escalate = True
       return None
   ```
   > **ADK gotcha:** an `after_agent_callback` only emits an event when it returns content or **changes state**. Setting `actions.escalate = True` on its own is silently dropped and the loop keeps going — so always pair it with a state write (here, `deal_outcome` / `pending_approval`).
3. Write `approve_deal(tool_context)` and `reject_deal(tool_context)` as function tools (requirement 5).
4. Make the root agent an `LlmAgent` with `tools=[AgentTool(agent=negotiation_loop), approve_deal, reject_deal]` and an instruction that shows `{pending_approval?}` and tells it to ask the user, then call the matching tool.
5. Run:
   ```bash
   adk web m2_adk_multiagents/solution/ex06_human_in_the_loop/
   ```
6. Open `http://localhost:8000`, pick **`negotiation`** from the dropdown.
7. Send: **"Start the negotiation for 742 Evergreen Terrace."**
8. Watch the **chat UI** and the **terminal**. The negotiation runs automatically (buyer ↔ seller). When the seller accepts:

   | Scenario | What happens in the chat | What to do |
   |---|---|---|
   | Deal ≤ $455K | Agent reports: "Deal auto-approved at $X" | Nothing — auto-approved |
   | Deal > $455K | Agent asks: "The seller wants to accept at $X. Do you APPROVE or REJECT this deal?" | Reply **APPROVE** or **REJECT** in the chat |
   | You reply APPROVE | Agent calls `approve_deal`, confirms the deal is closed at $X | Done |
   | You reply REJECT | Agent calls `reject_deal`, confirms the rejection, asks whether to keep negotiating | Reply yes to run more rounds |

   The solution's buyer opens at about $457,000, so the seller's acceptance usually lands above the threshold and you get the approval question.

9. Try both paths:
   - **First run:** when asked, reply **REJECT**. Confirm the rejection and check the State tab: `seller_decision` is now a COUNTER.
   - **Second run:** click **New Session**, start again, reply **APPROVE**. Confirm the deal closes.

## Verify

- **Deal at or below $455K**: `[AUTO-APPROVED]` printed, no approval question, loop exits
- **Deal above $455K**: `[PENDING APPROVAL]` printed, `pending_approval` in state, the agent asks APPROVE or REJECT in the chat
- **Reply APPROVE**: `approve_deal` is called, `[APPROVED]` printed, `deal_finalized` is true, `pending_approval` cleared
- **Reply REJECT**: `reject_deal` is called, `[REJECTED]` printed, `seller_decision` becomes `{"action": "COUNTER", ...}`; asking to continue runs more rounds
- **Counter-offers**: no approval question at any price — checkpoints only fire on `ACCEPT`
- Threshold is a single constant — changing `AUTO_APPROVE_CEILING` to `460_000` makes a $457K deal auto-approve

## Reflection

You've implemented a **three-tier governance model**: auto-approve (low-stakes), human checkpoint (high-stakes), hard block (Exercise 1's budget cap). In production, these tiers are everywhere:

- **Where else could the approval come from?** Here the human answers in the chat. Think: Slack approval workflows, email confirmations, dashboard buttons, webhook callbacks. How would you make the agent *wait* for an async human response that arrives hours later?
- **What happens if the human never responds?** The deal stays pending forever. How would you add a timeout — and what should the *default* action be on timeout? (Auto-approve? Auto-reject? Escalate to a manager?)
- **Could an adversarial agent bypass this checkpoint?** The checkpoint reads `state['seller_decision']`. What if the seller writes a different state key? How would you make the checkpoint tamper-proof?

---

> **Solution:** see `solution/ex06_human_in_the_loop/` for the complete, runnable orchestrator. The instructor will walk through it live during the review session.
