# Exercise 9 — Adaptive Strategy via Offer Memory `[Stretch]`

## Goal

Build a buyer agent that maintains **structured episodic memory** of the seller's negotiation patterns and uses a **strategy advisor sub-agent** (wrapped as `AgentTool`) to analyze that memory and recommend tactics before each offer.

## Context

In Exercise 02, agents accumulated state (offer history). But they only used it passively — the LLM saw the data and did whatever it wanted with it. No *analysis* layer existed between raw memory and decision-making.

In production negotiation systems, raw memory is an input to a reasoning step:
- "The seller conceded 3% last round → push harder"
- "The seller hasn't moved in 2 rounds → split the difference"
- "The seller's concessions are decelerating → they're near their floor"

Your job: build a two-layer system where raw offer memory feeds a strategy advisor, and the strategy advisor's recommendation feeds the buyer's next offer.

## What you're building

A modified negotiation orchestrator with a strategy advisor:

```
solution/ex09_adaptive_strategy/
└── negotiation/
    ├── __init__.py
    └── agent.py
```

Requirements:

1. **Structured offer memory** — after each seller response, record a structured entry in `state["negotiation_memory"]`:
   ```python
   {
       "round": 2,
       "buyer_offer": 435000,
       "seller_counter": 468000,
       "seller_concession": 9000,        # how much seller dropped from previous counter
       "concession_rate": 0.019,          # seller_concession / previous_counter
       "gap": 33000,                      # seller_counter - buyer_offer
   }
   ```

2. **Strategy advisor sub-agent** — an `LlmAgent` wrapped as `AgentTool` on the buyer. Its instruction analyzes the memory and recommends one of:
   - `PUSH_HARDER` — seller is conceding significantly, press the advantage
   - `SPLIT_DIFFERENCE` — seller movement is slowing, propose a midpoint
   - `HOLD_FIRM` — seller isn't moving, repeat your last offer
   - `WALK_AWAY` — gap is too large and seller isn't conceding

   The advisor receives `{negotiation_memory}` and returns a structured recommendation.

3. **Buyer uses advisor** — the buyer's instruction tells it to call `strategy_advisor` before making each offer and follow the recommendation:
   ```
   Before each offer:
   1. Call `strategy_advisor` to analyze the seller's pattern
   2. Follow the recommended tactic (PUSH_HARDER, SPLIT_DIFFERENCE, HOLD_FIRM, or WALK_AWAY)
   3. Use MCP pricing tools to determine the specific dollar amount
   ```

4. **Memory accumulation callback** — an `after_tool_callback` or `after_agent_callback` on the seller that extracts prices and computes concession metrics.

## Steps

1. Copy the canonical orchestrator from `negotiation_agents/negotiation/agent.py`.
2. Write the memory accumulation logic. After each seller round:
   - Extract buyer's offer price from `state["buyer_offer"]` (regex or structured)
   - Extract seller's counter from `state["seller_decision"]["price"]`
   - Compute concession from the previous round's seller counter
   - Append to `state["negotiation_memory"]`
3. Build the `strategy_advisor` LlmAgent:
   - Give it an instruction that analyzes `{negotiation_memory}` for patterns
   - Have it output a recommendation with reasoning
   - No tools needed — pure reasoning agent
4. Wrap it as `AgentTool(agent=strategy_advisor)` in the buyer's tools list.
5. Update the buyer's instruction to call the advisor before each offer.
6. Run:
   ```bash
   adk web m2_adk_multiagents/solution/ex09_adaptive_strategy/
   ```
7. Pick **`negotiation`** and send: *"Start the negotiation for 742 Evergreen Terrace."*
8. Watch the **events panel** — you should see `strategy_advisor` tool calls appearing inside the buyer's turn, with recommendations like "SPLIT_DIFFERENCE: seller concessions decelerating."

## Verify

- `negotiation_memory` in State tab grows with structured entries after each round
- Each entry has `round`, `buyer_offer`, `seller_counter`, `seller_concession`, `concession_rate`, `gap`
- The buyer calls `strategy_advisor` before each offer (visible in events panel)
- The advisor's recommendation visibly influences the buyer's strategy
- Terminal shows memory analysis logs

### Verify via the session DB

`adk web` persists all state in a SQLite database at `negotiation/.adk/session.db` (created the first time you chat with the agent in `adk web`; the folder is git-ignored). Query it to confirm the episodic memory was stored (the command has no `$` or escaped quotes, so it can be pasted unchanged into bash or PowerShell):

```bash
python -c "
import sqlite3, json
conn = sqlite3.connect('m2_adk_multiagents/solution/ex09_adaptive_strategy/negotiation/.adk/session.db')
cur = conn.cursor()
cur.execute('SELECT id, state FROM sessions ORDER BY create_time DESC LIMIT 1')
sid, raw = cur.fetchone()
state = json.loads(raw)
memory = state.get('negotiation_memory', [])
print(f'Session {sid[:8]}... - {len(memory)} rounds in memory')
for e in memory:
    print('  Round {round}: buyer={buyer_offer:,}  seller={seller_counter:,}  concession={seller_concession:,}  rate={concession_rate}  gap={gap:,}'.format(**e))
print('Final decision:', state.get('seller_decision'))
conn.close()
"
```

Example output (gpt-4o — prices vary run to run):
```
Session 843802b8... - 4 rounds in memory
  Round 1: buyer=425,000  seller=477,000  concession=0  rate=0.0  gap=52,000
  Round 2: buyer=433,500  seller=470,000  concession=7,000  rate=0.0147  gap=36,500
  Round 3: buyer=442,000  seller=465,000  concession=5,000  rate=0.0106  gap=23,000
  Round 4: buyer=453,500  seller=453,500  concession=11,500  rate=0.0247  gap=0
Final decision: {'action': 'ACCEPT', 'price': 453500}
```

Expected observations:
- **`negotiation_memory`**: list of structured entries, one per round, with concession metrics
- **Buyer opens at ~$425K** (12% below asking) — low anchor enforced by instruction
- **`seller_concession`**: seller drops roughly $5K–$8K per counter as they approach their floor
- **`concession_rate`**: around 1–1.5% per counter — the strategy advisor uses this trend to recommend tactics
- **`gap`**: narrows round by round until it reaches 0 in the round the seller accepts (that round is recorded too)
- **`seller_decision`**: final ACCEPT — any offer at or above the seller's floor is accepted (`submit_decision` enforces it), so deals usually close in the high $440Ks–mid $450Ks

## Reflection

This exercise demonstrates **memory-augmented decision making** — the agent doesn't just remember, it *reasons over its memories*.

The pattern is: **Raw Memory → Analysis Agent → Strategy → Action Agent → Action**

Compare the three memory patterns across exercises:
| Exercise | Memory type | How memory is used |
|----------|------------|-------------------|
| Ex02 | Offer history (list) | Stall detection (threshold check) |
| **Ex09** | **Episodic negotiation memory** | **Active analysis via sub-agent** |

**Design question:** Why use a separate `AgentTool` for strategy analysis instead of putting the analysis logic directly in the buyer's instruction?

Answer: Separation of concerns. The buyer's instruction is already complex (pricing tools, budget constraints, offer formatting). Adding strategy analysis to the same instruction would make it fragile and hard to test. The `AgentTool` boundary gives you a clean interface: memory in → recommendation out.

---

> **Solution:** see `solution/ex09_adaptive_strategy/` for the complete, runnable orchestrator. The instructor will walk through it live during the review session.
