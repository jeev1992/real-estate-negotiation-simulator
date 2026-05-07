# Exercise 8 — Shared Market Intelligence via App State `[Core]`

## Goal

Use ADK's `app:`-scoped state as a **shared memory layer** that both buyer and seller agents can read — simulating a shared market knowledge base. Every `get_market_price` call gets cached in `app:` state, building a growing pool of comparable sale data that any agent, in any session, for any user, can reference.

## Context

Demo 03 showed three state scopes:
- **Session state** (`state["key"]`) — cleared on "New Session"
- **User state** (`state["user:key"]`) — persists per user across sessions
- **App state** (`state["app:key"]`) — global, shared across ALL users and sessions

Some knowledge should be shared across *all* agents — market comps, neighborhood trends, price benchmarks. That's what `app:` state is for.

Your job: build a negotiation orchestrator where every MCP pricing tool call gets cached into `app:` state, building shared market intelligence that both buyer and seller can reference.

## What you're building

A modified negotiation orchestrator:

```
solution/ex08_shared_market_intel/
└── negotiation/
    ├── __init__.py
    └── agent.py
```

Requirements:

1. **Cache tool results in app state** — write an `after_tool_callback` that fires after any pricing tool call (`get_market_price`, `calculate_discount`, `get_property_tax_estimate`) and caches the result:
   ```python
   state["app:price_cache"] = {
       "742-evergreen-austin-78701": {
           "market_price": 465000,
           "last_lookup": "2025-01-15T10:30:00Z",
           "lookup_count": 3,
       },
       ...
   }
   ```

2. **Seed initial comps** — in the LoopAgent's `before_agent_callback`, seed `state["app:recent_comps"]` with 2-3 comparable sales if it doesn't already exist:
   ```python
   state["app:recent_comps"] = [
       {"address": "800 Maple Dr", "sold_price": 452000, "date": "2024-11"},
       {"address": "315 Cedar Ln", "sold_price": 471000, "date": "2024-12"},
   ]
   ```

3. **Inject comps into both agents** — both the buyer and seller instructions should reference `{app:recent_comps}` so both sides argue from the same data:
   ```
   COMPARABLE SALES (shared market data):
   {app:recent_comps}
   ```

4. **Track lookup frequency** — maintain `state["app:total_price_lookups"]` as a global counter. This demonstrates that app state accumulates across all agents, sessions, and users.

## Steps

1. Copy the canonical orchestrator from `negotiation_agents/negotiation/agent.py`.
2. Write a `_cache_price_lookup` function as an `after_tool_callback` for both buyer and seller. It should:
   - Check if `tool.name` is a pricing tool
   - Extract the result and cache it in `state["app:price_cache"]`
   - Increment `state["app:total_price_lookups"]`
   - Print a log line: `[cache] Cached market_price for 742-evergreen: $465,000 (lookup #3)`
3. Write a `_seed_comps` function as `before_agent_callback` on the LoopAgent that initializes `app:recent_comps` if not yet set.
4. Add `{app:recent_comps}` references to both buyer and seller instructions.
5. Run:
   ```bash
   adk web m3_adk_multiagents/solution/ex08_shared_market_intel/
   ```
6. Pick **`negotiation`** from the dropdown. Send: **"Start the negotiation for 742 Evergreen Terrace."**
   - Watch the **terminal** for `[cache]` log lines:
     - `Seeded app:recent_comps with 3 comparable sales` (first run only)
     - `Cached get_market_price:... (lookup #1)` after each pricing tool call
   - Open the **State tab** and check for:
     - `app:recent_comps` — 3 comparable sales
     - `app:price_cache` — growing with each pricing tool call
     - `app:total_price_lookups` — counter of all pricing lookups
   - In the **chat**, both buyer and seller should reference the comparable sales data

7. Click **"New Session"**. Send the same query: **"Start the negotiation for 742 Evergreen Terrace."**
   - **Terminal**: `Seeded app:recent_comps` should **NOT** appear (already seeded from session 1)
   - **State tab**: `app:price_cache` should still have entries from session 1, and `app:total_price_lookups` keeps incrementing from where it left off
   - This proves `app:` state persists across sessions — unlike `buyer_offer` and `seller_response` which reset

## Verify

- `app:recent_comps` appears in State tab and is visible in both buyer and seller instructions (check **Info tab**)
- `app:price_cache` grows as tool calls happen
- `app:total_price_lookups` increments across sessions and agents
- Both agents reference the comparable sales in their reasoning
- Session state (`buyer_offer`, `seller_response`) resets on New Session; app state does not

### Verify via the session DB

ADK persists all state in a SQLite database at `negotiation/.adk/session.db`. You can query it directly to confirm `app:` state survives across sessions:

```bash
python -c "
import sqlite3, json
conn = sqlite3.connect('m3_adk_multiagents/solution/ex08_shared_market_intel/negotiation/.adk/session.db')
cur = conn.cursor()
cur.execute('SELECT state FROM app_states')
state = json.loads(cur.fetchone()[0])
print('recent_comps:', json.dumps(state.get('recent_comps', []), indent=2))
print('total_price_lookups:', state.get('total_price_lookups', 0))
print('price_cache keys:', list(state.get('price_cache', {}).keys()))
cur.execute('SELECT COUNT(*) FROM sessions')
print('total sessions:', cur.fetchone()[0])
conn.close()
"
```

Expected observations:
- **`app_states` table**: exactly 1 row — shared across all sessions and users
- **`sessions` table**: one row per "New Session" click — session state resets but app state doesn't
- **`events` table**: full audit trail of every agent turn, tool call, and state delta
- **`total_price_lookups`**: keeps incrementing across sessions (e.g., 4 after two full negotiations)
- **`price_cache`**: contains cached results from `get_market_price` and `calculate_discount` calls across all sessions

## Reflection

The three state tiers map to different memory scopes:

| Scope | Real-world analogy | Example |
|-------|-------------------|---------|
| `session` | Working memory | Current negotiation's offers |
| `user:` | Personal journal | "My past 5 deals" |
| `app:` | Market database | "All comps in Austin 78701" |

In production, `app:` state raises questions:
- **Staleness**: cached prices from 6 months ago may be misleading. How would you add TTL (time-to-live) to cached entries?
- **Conflicts**: if two agents write to the same `app:` key simultaneously, who wins? ADK uses last-write-wins. Is that acceptable?
- **Scale**: a SQLite backend works for demos. What would you use for 1000 concurrent agents?

---

> **Solution:** see `solution/ex08_shared_market_intel/` for the complete, runnable orchestrator. The instructor will walk through it live during the review session.
