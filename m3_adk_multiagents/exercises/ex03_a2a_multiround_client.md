# Exercise 3 — A2A Multi-Round Client `[Core]`

## Goal

Write a Python script that orchestrates a buyer ↔ seller negotiation **over the A2A wire protocol** — discovering both agents via their Agent Cards, threading conversations with `contextId`, and breaking the loop on `ACCEPT`.

This is the production pattern: **a script that doesn't know how either agent is implemented, only that they speak A2A**.

## Context

In Module 3 you ran `a2a_14_orchestrated_negotiation.py` — a script that does exactly this. Today you'll write your own version from scratch. The point isn't to invent something new; it's to **internalize the wire-level pattern** so you'd recognize and write it again at work.

## What you're building

A standalone script `multi_round_client.py` that:

1. **Discovers** both agents via `A2ACardResolver` against `http://127.0.0.1:8000`.
2. **Drives** a multi-round negotiation:
   - Round 1: ask the buyer for an opening offer.
   - Round k+1: forward the buyer's offer to the seller, get the seller's response, forward the response back to the buyer for the next offer.
3. **Threads** conversations with `contextId` — buyer has its own contextId, seller has its own. *They never share context — your script is the matchmaker.*
4. **Terminates** on `ACCEPT` (regex match in seller's reply) or after `--max-rounds` (default 5).
5. **Logs** clearly: discovery info, each round's offer + response, final outcome.

## Steps

1. Write the helper `send_a2a_message(http, agent_url, text, context_id)` that:
   - POSTs a JSON-RPC `message/send` request to `agent_url`.
   - Returns `(result_dict, new_context_id)`.
2. Write `extract_agent_text(result)` that pulls the agent's text response from `artifacts` first, falling back to the last agent message in `history`.
3. Use `A2ACardResolver` to fetch both Agent Cards.
4. Write the round loop. Maintain `buyer_context_id` and `seller_context_id` separately; pass each one back to its own agent on subsequent calls.
5. Detect `\bACCEPT\b` in the seller's reply (regex, word-boundary). Break on match.

## Prerequisites

You need both agents running first. In a separate terminal:

```bash
adk web --a2a m3_adk_multiagents/negotiation_agents/
```

Then run your script:

```bash
python m3_adk_multiagents/solution/ex03_a2a_multiround_client/multi_round_client.py
```

## Verify

- Two Agent Cards fetched and printed (name, URL, skills)
- Each round prints: round number, buyer's text (truncated), seller's text (truncated), both contextIds
- Buyer's contextId stays constant across rounds. Seller's contextId stays constant across rounds. They are *different* from each other.
- Loop terminates on `ACCEPT` or after max rounds — clean exit either way.

## Reflection

Your script is the **matchmaker** — neither buyer nor seller knows about the other. They just see messages from "a user" (your script).

**How would you turn this matchmaker into another A2A agent itself?** What would the matchmaker's Agent Card look like? What skill would it advertise? What would change in *its* `agent.py`?

This is how A2A networks scale to 5+ agents in production — every coordinator is itself an A2A-discoverable agent.

---

> **Solution:** see `solution/ex03_a2a_multiround_client/` for the complete, runnable script. The instructor will walk through it live during the review session.
