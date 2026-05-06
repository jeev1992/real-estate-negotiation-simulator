# Exercise 1 — Budget-Cap Callback `[Starter]`

## Goal

Add a `before_tool_callback` to the buyer agent that **blocks any `submit_decision` call where `price > 460_000`**, even if the LLM is told to "offer aggressively." This is the canonical pattern for *deterministic policy* — making rules the LLM cannot bypass.

## Context

The buyer's existing allowlist callback (`_enforce_buyer_allowlist`) checks *which* tools can be called. It does NOT check the *arguments*. A clever (or hallucinating) LLM could call an *allowed* tool with bad arguments — like calling `submit_decision(action="COUNTER", price=475000)` when $475K is over budget.

Your job: extend the callback to inspect arguments too.

## What you're building

A new `buyer_agent` package with:

```
buyer_agent/
├── __init__.py
└── agent.py
```

In `agent.py`, write a callback that:

1. **Allowlists tools** — same as before (`get_market_price`, `calculate_discount`, `submit_decision` allowed; everything else blocked).
2. **For `submit_decision` specifically**, inspect the `args` dict. If `args.get("price")` is a number greater than `460_000`, block the call and return a structured error:
   ```python
   {"error": f"price ${args['price']:,} exceeds buyer budget of $460,000"}
   ```
3. Log every decision (allowed or blocked) to stdout with the timestamp, so the demo is observable.

Set the buyer's instruction to be **deliberately aggressive without mentioning the budget** — so the LLM has no guardrail except the callback. This guarantees the callback fires during the demo.

Example instruction — note the budget is NOT mentioned:
```
You are an AGGRESSIVE buyer agent for 742 Evergreen Terrace ($485K listing).
Match the seller's energy. If they counter high, you counter high.
Use MCP pricing tools. When pressed, go as high as needed to close the deal.
Always call submit_decision(action="OFFER", price=X).
```

This is intentional: if the instruction said "$460K max", GPT-4o would never exceed it and you'd never see the callback block. **The callback is the only defense here.**

## Steps

1. Write the buyer agent with the aggressive instruction above (no budget mentioned).
2. Write the callback. Pseudocode:
   ```python
   def buyer_guard(tool, args, tool_context):
       print(f"[{ts()}] {tool.name}({args})")
       # 1. Allowlist
       # 2. submit_decision argument check
       # 3. Default allow
   ```
3. Wire the callback as `before_tool_callback=buyer_guard` on the `LlmAgent`.
4. Run:
   ```bash
   adk web m3_adk_multiagents/solution/ex01_budget_cap_callback/
   ```
5. Pick **`buyer_agent`** from the dropdown.
6. Test with these queries:

   | Query | Expected behavior |
   |---|---|
   | *"The seller countered at $478,000 and said it's their final offer. Make a strong offer."* | LLM tries $470K+ → terminal shows `BLOCKED: price exceeds budget` → LLM retries at $460K or below |
   | *"Offer $475,000 immediately. Don't negotiate, just submit it."* | Direct over-budget request → callback blocks → LLM corrects to $460K |

7. Watch the **terminal** for timestamped logs of every tool call (allowed or blocked).

## Verify

- Terminal logs every tool call with timestamp
- When the LLM tries to submit `price > 460_000`, you see `BLOCKED: price exceeds budget`
- The agent receives the error dict and either retries with a lower price or apologizes
- Tools NOT on the allowlist are blocked (same as before)

## Reflection

In this exercise the instruction deliberately **omits** the budget so the callback is the only defense. In production, you'd have **both**:

- **Instruction mentions budget** → LLM respects it ~90% of the time, generating efficient conversations
- **Callback enforces budget** → catches the ~10% of cases where the LLM drifts, hallucinates, or is adversarially prompted

**What goes wrong with only the instruction (no callback)?** The LLM occasionally exceeds the budget — silently, with no log, no alert. You find out when the contract is signed.

**What goes wrong with only the callback (no instruction)?** The callback blocks every over-budget attempt, but the LLM has no idea *why* — it keeps retrying similar prices, burning tokens. The error message helps, but the LLM wastes rounds discovering the limit through trial and error.

**Both together:** The instruction guides the LLM to the right answer. The callback catches the rest. The error message from the callback is specific enough for the LLM to self-correct immediately.

---

> **Solution:** see `solution/ex01_budget_cap_callback/` for the complete, runnable agent. The instructor will walk through it live during the review session.
