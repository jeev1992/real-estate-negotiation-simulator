# Exercise 8 — Cross-Session Negotiation Memory `[Core]`

## Goal

Build a buyer agent that **remembers outcomes from previous negotiation sessions** using ADK's `user:`-scoped state, so it can anchor future offers with data from past deals. This is the production pattern for *agents with persistent memory across conversations*.

## Context

Demo d03 introduced `user:` state — data that persists across sessions for the same `user_id`. The `record_offer` tool wrote `state["user:total_offers"]`, and it survived clicking "New Session."

But no exercise actually *uses* cross-session memory to change agent behavior. In production, this is critical: a buyer agent that remembers "I got 742 Evergreen for $445K last time" negotiates differently from one starting cold.

Your job: build a buyer agent that accumulates a deal journal across sessions and uses it as strategic context.

## What you're building

A new `buyer_agent` package:

```
solution/ex08_cross_session_memory/
└── buyer_agent/
    ├── __init__.py
    └── agent.py
```

The agent has two custom tools:

1. **`record_deal`** — called at the end of a negotiation to save the outcome:
   ```python
   def record_deal(property_name: str, final_price: int, rounds: int, 
                   outcome: str, tool_context: ToolContext) -> dict:
       """Save a completed deal to persistent memory.
       
       Args:
           property_name: The property address (e.g. "742 Evergreen Terrace").
           final_price: The agreed price in dollars, or last offer if no deal.
           rounds: How many rounds the negotiation took.
           outcome: "ACCEPTED", "REJECTED", or "STALLED".
       """
   ```
   This writes to `state["user:deal_journal"]` — a list of deal dicts that persists across sessions.

2. **`recall_deals`** — retrieves past deals for strategic context:
   ```python
   def recall_deals(tool_context: ToolContext) -> dict:
       """Retrieve all past negotiation outcomes from memory."""
   ```

The agent's instruction references `{user:deal_journal}` so the LLM sees past deals in its context automatically.

## Steps

1. Write the two tools. `record_deal` should:
   - Read the existing journal: `tool_context.state.get("user:deal_journal", [])`
   - Append the new entry with a timestamp
   - Write back: `tool_context.state["user:deal_journal"] = journal`
   - Also update `tool_context.state["user:total_deals"]` (count)

2. Write the agent instruction. It should tell the LLM:
   - Review past deals from `{user:deal_journal}` before making offers
   - Use historical prices as anchoring data ("I got a similar property for $X last time")
   - Call `recall_deals` if the user asks about past negotiations
   - Call `record_deal` when a negotiation concludes
   - Still use MCP pricing tools for current market data

3. **Add a `before_agent_callback`** that initializes `user:deal_journal` and `user:total_deals` if they don't exist yet. Without this, the `{user:deal_journal}` placeholder in the instruction will throw a "Context variable not found" error on the very first run:
   ```python
   def _init_memory(callback_context):
       if "user:deal_journal" not in callback_context.state:
           callback_context.state["user:deal_journal"] = []
       if "user:total_deals" not in callback_context.state:
           callback_context.state["user:total_deals"] = 0
       return None
   ```

4. Include the MCP pricing toolset (same as the canonical buyer).

5. Run the first session:
   ```bash
   adk web m3_adk_multiagents/solution/ex08_cross_session_memory/
   ```
   Pick `buyer_agent`, send: *"I just closed a deal on 742 Evergreen Terrace for $448,000 after 3 rounds. Record it."*

6. Click **New Session** (top of the UI).

7. In the new session, send: *"I'm looking at 1234 Oak Street, listed at $510,000. What should I offer?"*
   - The agent should reference the Evergreen deal as anchoring data
   - Check the **State tab** — `user:deal_journal` should show the previous deal

8. Record this deal too, then start a third session. The journal should now have two entries.

## Verify

- After recording a deal, `user:deal_journal` appears in the State tab
- After clicking **New Session**, the journal persists (check State tab)
- The agent's responses reference past deals when making strategy recommendations
- `user:total_deals` increments across sessions
- If you change `user_id` (restart `adk web`), the journal is empty — it's per-user

## Reflection

Session state (`state["key"]`) vs. user state (`state["user:key"]`) is the difference between short-term and long-term memory:

- **Session state** = working memory (this conversation's offers, current negotiation round)
- **User state** = episodic memory (past deals, learned preferences, track record)

In production, what would you store in `user:` state vs. `app:` state?

Hint: `user:` = "this agent's experience with this client." `app:` = "market intelligence shared across all agents and clients." Exercise 9 explores the `app:` tier.

**What happens when the deal journal grows to 50+ entries?** The `{user:deal_journal}` placeholder injects the full list into the instruction — eventually exceeding the context window. Exercise 11 addresses this with summarization.

---

> **Solution:** see `solution/ex08_cross_session_memory/` for the complete, runnable agent. The instructor will walk through it live during the review session.
