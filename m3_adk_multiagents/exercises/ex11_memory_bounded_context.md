# Exercise 11 — Memory-Bounded Context Window `[Stretch]`

## Goal

Handle the practical problem of **negotiation memory growing too large for the LLM context window** by implementing a summarization and eviction strategy inside a `before_model_callback`.

## Context

Exercises 08 and 10 accumulate memory — deal journals, offer histories, episodic negotiation records. In a demo with 3-5 rounds, this is fine. In production, an agent that runs 20+ round negotiations or accumulates 50+ past deals will exceed the context window.

The "infinite memory is a lie" problem:
- GPT-4o has ~128K tokens of context. A 20-round negotiation with tool calls can consume 50K+ tokens in history alone.
- `user:deal_journal` with 50 entries could be 10K+ tokens injected into the instruction via `{user:deal_journal}`.
- At some point, the LLM starts ignoring or hallucinating over data that's pushed to the middle of the context window (the "lost in the middle" phenomenon).

Your job: build a `before_model_callback` that detects when accumulated memory is too large and compresses it — keeping recent detail while summarizing older history.

## What you're building

A modified negotiation orchestrator with memory management:

```
solution/ex11_memory_bounded_context/
└── negotiation/
    ├── __init__.py
    └── agent.py
```

Requirements:

1. **Extended negotiation** — set `max_iterations=10` and use a tight price gap (buyer max $460K, seller floor $458K) so negotiations run many rounds without quick convergence.

2. **Offer memory accumulation** — same as Exercise 10, accumulate structured entries in `state["negotiation_memory"]` after each round.

3. **Memory compression callback** — a `before_model_callback` on the buyer that triggers when `negotiation_memory` has more than `MAX_DETAILED_ROUNDS` entries (e.g., 4). When triggered:
   - **Summarize old rounds**: take entries `[0..n-3]` and compress into a single text summary:
     ```
     Rounds 1-5 summary: Price moved from $430K to $452K. 
     Avg buyer increase: $4.4K/round. Avg seller decrease: $3.2K/round.
     Seller concession rate declining (started 2.1%, now 0.8%).
     ```
   - **Keep recent rounds**: the last 3 entries stay as full structured data
   - **Write the summary to state**: `state["memory_summary"]` = the compressed text
   - **Replace the memory in state**: `state["negotiation_memory"]` = only the last 3 entries
   - **Log the compression**: print `[memory] Compressed rounds 1-5 into summary (was 8 entries, now 3 + summary)`

4. **Inject summary into instruction** — the buyer's instruction should reference both:
   ```
   NEGOTIATION HISTORY SUMMARY (older rounds):
   {memory_summary}

   RECENT ROUNDS (full detail):
   {negotiation_memory}
   ```

5. **Compression metrics** — track `state["memory_compressions"]` (how many times compression fired) for observability.

## Steps

1. Copy the Exercise 10 solution (or the canonical orchestrator) as your starting point.
2. Set `max_iterations=10` and adjust buyer/seller budgets for a tight gap.
3. Write `_compress_memory(callback_context)` as a `before_model_callback` on the buyer:
   ```python
   def _compress_memory(callback_context):
       state = callback_context.state
       memory = state.get("negotiation_memory", [])
       if len(memory) <= MAX_DETAILED_ROUNDS:
           return None  # no compression needed
       
       # Split: old rounds → summarize, recent rounds → keep
       old_rounds = memory[:-KEEP_RECENT]
       recent_rounds = memory[-KEEP_RECENT:]
       
       # Build summary text from old_rounds
       summary = _build_summary(old_rounds, state.get("memory_summary", ""))
       
       # Update state
       state["memory_summary"] = summary
       state["negotiation_memory"] = recent_rounds
       state["memory_compressions"] = state.get("memory_compressions", 0) + 1
       
       print(f"[memory] Compressed {len(old_rounds)} old rounds into summary")
       return None  # allow the model call to proceed
   ```
4. Write `_build_summary(old_rounds, existing_summary)` that:
   - Computes aggregate stats: price range, average movement, concession trends
   - Appends to any existing summary (incremental compression)
   - Returns a concise text string (aim for < 200 words)
5. Update the buyer instruction with `{memory_summary}` and `{negotiation_memory}` placeholders.
6. Run:
   ```bash
   adk web m3_adk_multiagents/solution/ex11_memory_bounded_context/
   ```
7. Send: *"Start the negotiation for 742 Evergreen Terrace."*
8. Watch the terminal — after round 4+, you should see `[memory] Compressed...` messages.
9. Check the **State tab** at different points:
   - Rounds 1-4: `negotiation_memory` grows, no `memory_summary`
   - Rounds 5+: `memory_summary` appears, `negotiation_memory` is trimmed to 3 entries
   - `memory_compressions` increments each time

## Verify

- Negotiation runs 6+ rounds (tight gap prevents quick ACCEPT)
- `negotiation_memory` never exceeds `MAX_DETAILED_ROUNDS` entries
- `memory_summary` appears after the first compression
- Summary contains aggregate stats (price range, avg movement, trends)
- The buyer still negotiates coherently despite compressed history
- Terminal shows compression events with entry counts
- `memory_compressions` counter in State tab

## Reflection

This exercise teaches **memory management** — a critical production pattern:

| Strategy | Tradeoff |
|----------|----------|
| Keep everything | Context overflow, "lost in the middle", high token cost |
| Keep only recent | Loses strategic context ("how did we get here?") |
| **Summarize + recent** | Best of both — trends preserved, detail where it matters |

**Design decisions to consider:**
- **What to keep**: the last N rounds? The best offer? The worst rejection?
- **What to summarize**: statistics vs. narrative? Numbers vs. trends?
- **When to compress**: fixed threshold? Token estimate? Dynamic based on model?
- **Incremental vs. full recompute**: append to existing summary, or regenerate from scratch each time?

**Advanced**: Instead of a hardcoded summary function, you could use a *summarizer LLM agent* (`AgentTool`) to compress the memory. This gives better natural language summaries but costs an extra LLM call per compression. When is that tradeoff worth it?

---

> **Solution:** see `solution/ex11_memory_bounded_context/` for the complete, runnable orchestrator. The instructor will walk through it live during the review session.
