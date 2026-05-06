# Exercise 4 — Mediator Agent with `AgentTool` `[Core]`

## Goal

Build a **mediator agent** that wraps a buyer-side specialist and a seller-side specialist as `AgentTool`s, then proposes a fair midpoint price. This teaches **hierarchical delegation** — the alternative to A2A's peer-to-peer pattern from Exercise 3.

## Context

So far we've seen two ways for agents to interact:

1. **`SequentialAgent` / `LoopAgent`** — workflow agents that run children in declared patterns. *Coordinator is structural, not intelligent.*
2. **A2A `message/send` (Exercise 3)** — peer agents talking over the network. *Coordinator is an external script.*

`AgentTool` is the third way: **wrap an agent as a callable tool inside another agent**. The parent agent's LLM decides *when* to call the child — and stays in control of the overall flow. The child returns text; the parent reasons over it.

This is how you build *intelligent* coordinators — agents whose decision logic is itself an LLM.

## What you're building

A new package:

```
solution/ex04_mediator_agent/
└── mediator/
    ├── __init__.py
    └── agent.py
```

In `agent.py`:

1. Define a `buyer_specialist` LlmAgent — has a description like *"reports the buyer's budget ceiling"* and an instruction that produces a one-line answer with the buyer's max ($460,000).
2. Define a `seller_specialist` LlmAgent — has access to the **inventory MCP server** so it can call `get_minimum_acceptable_price`. Returns a one-line answer with the floor price.
3. Define a `mediator` `LlmAgent` whose `tools=[...]` contains both specialists wrapped in `AgentTool(agent=specialist)`.
4. Mediator's instruction tells it to call **both** specialists, then propose a **midpoint** between budget and floor with a brief justification.

## Steps

1. Build the two specialist agents first. Keep them small — they're tools, not products.
2. Wrap each in `AgentTool(agent=...)` from `google.adk.tools.agent_tool`.
3. Define the mediator with a clear instruction: *"For any pricing question, call buyer_specialist for the buyer's max, call seller_specialist for the seller's floor, then propose a midpoint."*
4. Run via `adk web` and ask: *"What's a fair price for 742 Evergreen?"*

## Verify

- `adk web` shows three agents in the Info tab's "tools" list (or the mediator is selectable and its info shows two AgentTool entries).
- Asking the mediator for a fair price triggers **two tool calls** in the events panel — one to each specialist.
- The mediator's final response references *both* the budget AND the floor in its justification.

## Reflection

You now know **three ways** to compose multiple agents:

| Pattern | When the parent runs LLM logic | When children run LLM logic |
|---|---|---|
| `SequentialAgent` | No — structural only | Yes |
| **`AgentTool`** | Yes — decides which child to call | Yes |
| A2A `message/send` (Exercise 3) | The "parent" is an external script | Yes |

For each of these scenarios, which pattern fits best, and why?

- **Stage A → Stage B → Stage C, fixed order, no decisions** → ?
- **Specialist sub-agents that the parent picks among at runtime** → ?
- **Cross-vendor agent collaboration where the agents are separate services** → ?

---

> **Solution:** see `solution/ex04_mediator_agent/` for the complete, runnable agent. The instructor will walk through it live during the review session.
