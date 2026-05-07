# Exercise 7 — Parallel Multi-Seller Negotiation `[Stretch]`

## Goal

Build a buyer agent system that negotiates with **two sellers simultaneously** using `ParallelAgent`, then picks the better deal. This teaches the production pattern of *parallel fan-out with aggregation* — the agent equivalent of comparison shopping.

## Context

Demo d05 showed `ParallelAgent` gathering three independent research signals. That was read-only fan-out — no decisions, no tool calls. This exercise escalates the pattern: your parallel branches are **full negotiation agents** that call MCP tools, make offers, and produce structured outcomes.

The scenario: your buyer client is considering two properties:
- **742 Evergreen Terrace** (78701) — listed at $485,000  
- **1234 Oak Street** (78702) — listed at $510,000 (hot market, smaller discount expected)

The buyer wants to negotiate with both sellers at the same time and take the better deal.

## What you're building

A new agent package:

```
m3_adk_multiagents/solution/ex07_parallel_negotiation/
├── __init__.py
└── agent.py
```

Architecture:

```
root_agent (SequentialAgent)
├── parallel_negotiations (ParallelAgent)
│   ├── negotiation_a (LoopAgent)  ← buyer vs. seller for 742 Evergreen
│   │   └── round_a (SequentialAgent: buyer_a → seller_a)
│   └── negotiation_b (LoopAgent)  ← buyer vs. seller for 1234 Oak St
│       └── round_b (SequentialAgent: buyer_b → seller_b)
└── deal_picker (LlmAgent)  ← reads both outcomes, picks the best
```

Requirements:

1. **Two independent negotiation loops** — each is a LoopAgent wrapping a SequentialAgent (same pattern as the canonical negotiation), but for different properties.
   - `negotiation_a`: 742 Evergreen Terrace, buyer budget $460K, seller floor from MCP (canonical property)
   - `negotiation_b`: 1234 Oak Street, buyer budget $495K, seller floor $480K (hardcode a second property in your seller instruction since the MCP server only has 742 Evergreen data)
   
2. **Each negotiation writes to its own state keys**:
   - Negotiation A: `output_key="deal_a_result"` on its final round
   - Negotiation B: `output_key="deal_b_result"` on its final round
   - Use `after_agent_callback` on each LoopAgent to summarize the outcome into its output key

3. **`deal_picker`** — an `LlmAgent` that reads `{deal_a_result}` and `{deal_b_result}` from state and recommends which deal to take (or walk away from both). Its instruction should consider:
   - Final price
   - Property location and market condition
   - How many rounds it took (efficiency signal)
   - Whether the seller accepted or the loop hit max iterations

4. **ParallelAgent** wraps both LoopAgents so they run concurrently.

5. **SequentialAgent** wraps the ParallelAgent → deal_picker so the picker runs *after* both negotiations finish.

## Steps

1. Build `negotiation_a` first — this is essentially the canonical orchestrator from `negotiation_agents/negotiation/agent.py`. Make sure it writes its outcome to `state['deal_a_result']`.

2. Build `negotiation_b` — a second orchestrator for a different property. Since the MCP inventory server only has data for 742 Evergreen, the seller_b instruction should include the floor price directly: *"Your minimum is $480,000 for 1234 Oak Street."* The buyer_b can still use MCP pricing tools for general market data.

3. Wrap both in a `ParallelAgent`:
   ```python
   parallel_negotiations = ParallelAgent(
       name="parallel_negotiations",
       sub_agents=[negotiation_a, negotiation_b],
   )
   ```

4. Build the `deal_picker`:
   ```python
   deal_picker = LlmAgent(
       name="deal_picker",
       model=MODEL,
       instruction=(
           "Two negotiations just completed.\n\n"
           "Deal A (742 Evergreen Terrace): {deal_a_result}\n"
           "Deal B (1234 Oak Street): {deal_b_result}\n\n"
           "Compare both deals. Recommend which one the buyer should take, "
           "or advise walking away if neither is compelling. "
           "Consider: price, location, market heat, negotiation efficiency."
       ),
   )
   ```

5. Wrap everything:
   ```python
   root_agent = SequentialAgent(
       name="multi_seller_negotiation",
       description="Negotiate with two sellers in parallel, then pick the best deal.",
       sub_agents=[parallel_negotiations, deal_picker],
   )
   ```

6. Run and observe:
   ```bash
   adk web m3_adk_multiagents/solution/ex07_parallel_negotiation/
   ```
   Ask: *"Find me the best deal."*
   Watch the events panel — you should see tool calls from **both** negotiations interleaved.

## Verify

- **Both negotiations run**: events panel shows tool calls for both 742 Evergreen and 1234 Oak Street
- **State isolation**: `deal_a_result` and `deal_b_result` contain different outcomes (different prices, different properties)
- **Deal picker runs last**: only after both negotiations complete, the picker produces a recommendation
- **Picker references both deals**: the final output mentions both properties and gives a reasoned comparison
- **Each negotiation has proper termination**: either `ACCEPT` or `max_iterations` — no hangs

## Reflection

You've composed **three ADK agent types** in one system: `LoopAgent` (negotiation rounds), `ParallelAgent` (concurrent branches), `SequentialAgent` (pipeline). This is the full toolkit.

- **What happens if negotiation_a finishes in 2 rounds but negotiation_b takes all 5?** Does the ParallelAgent wait for both, or does the faster one's result go stale? What are the implications for API cost?
- **Could you make the deal_picker smarter by giving it `AgentTool` wrappers** around the two negotiators — so it could *restart* a negotiation with different parameters if neither deal is good enough? How would that change the architecture?
- **State key collisions**: Both negotiations use MCP pricing tools internally. Could their internal state keys (`buyer_offer`, `seller_response`) collide? How does ADK scope state to prevent this?

---

> **Solution:** see `solution/ex07_parallel_negotiation/` for the complete, runnable agent. The instructor will walk through it live during the review session.
