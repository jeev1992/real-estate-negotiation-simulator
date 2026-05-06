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

Set the buyer's instruction to be **deliberately aggressive** — something that would cause GPT-4o to occasionally try offers above $460K — so the callback actually fires during the demo.

## Steps

1. Copy the buyer's instruction style from `negotiation_agents/buyer_agent/agent.py`. Change the strategy text to be deliberately aggressive (e.g., *"Open at $475K to anchor high; only retreat if pushed."*) — this will make the LLM occasionally generate an over-budget offer.
2. Write the callback. Pseudocode:
   ```python
   def buyer_guard(tool, args, tool_context):
       print(f"[{ts()}] {tool.name}({args})")
       # 1. Allowlist
       # 2. submit_decision argument check
       # 3. Default allow
   ```
3. Wire the callback as `before_tool_callback=buyer_guard` on the `LlmAgent`.
4. Run via `adk web`, ask the buyer for a counter-offer to a $477K seller counter, and watch the terminal.

## Verify

- Terminal logs every tool call with timestamp
- When the LLM tries to submit `price > 460_000`, you see `BLOCKED: price exceeds budget`
- The agent receives the error dict and either retries with a lower price or apologizes
- Tools NOT on the allowlist are blocked (same as before)

## Reflection

The instruction tells the LLM the budget is $460K. The callback enforces it. **What goes wrong if you only have the instruction (no callback)?** What goes wrong if you only have the callback (instruction doesn't mention the budget)?

Hint: instructions and callbacks are two layers of defense. They fail differently.

---

> **Solution:** see `solution/ex01_budget_cap_callback/` for the complete, runnable agent. The instructor will walk through it live during the review session.
