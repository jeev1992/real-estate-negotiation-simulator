# Exercise 3 — Build a Research Pipeline `[Core]`

## Goal
Create a SequentialAgent pipeline that researches a property, drafts an offer, and then runs a risk assessment — three stages, each reading the previous stage's output from session state. This reinforces Demo 04 (sequential) and Demo 05 (parallel).

## Context
Demo 04 has three stages: market brief → offer drafter → polisher. That's a good pattern but the polisher is cosmetic. Replace it with something useful: a risk assessor that reads the drafted offer and flags potential problems.

## Steps

### Step 1 — Create the package
Create `adk_demos/ex03_research_pipeline/` with `__init__.py` and `agent.py`.

### Step 2 — Define three sub-agents

**Agent 1: `researcher`**
- Instruction: "Research 742 Evergreen Terrace in Austin TX 78701. Report: median price in ZIP, days on market, inventory level, school rating. Two sentences max."
- `output_key="research_brief"`

**Agent 2: `offer_strategist`**
- Instruction: "Read {research_brief}. The property is listed at $485,000. Draft a specific offer strategy: recommended price, contingencies, closing timeline. One paragraph."
- `output_key="offer_strategy"`

**Agent 3: `risk_assessor`**
- Instruction: "Read {offer_strategy} and {research_brief}. Identify the top 3 risks with this offer (e.g., overpaying, inspection issues, market timing). For each risk, rate it HIGH/MEDIUM/LOW and give one mitigation action."
- `output_key="risk_assessment"`

### Step 3 — Wire them into a SequentialAgent

```python
root_agent = SequentialAgent(
    name="research_pipeline",
    description="Three-stage property research pipeline.",
    sub_agents=[researcher, offer_strategist, risk_assessor],
)
```

### Step 4 — Test

```bash
adk web m3_adk_multiagents/adk_demos/ex03_research_pipeline/
```

Send any message (e.g., "Research this property") and watch all three stages fire in order.

## Verify
- Three agents run in sequence (visible in the ADK web UI events)
- The risk assessor references specific details from the research brief AND the offer strategy
- Each stage's output is stored in session state under its `output_key`

## Stretch goal
Replace the `researcher` with a **ParallelAgent** that runs three concurrent sub-agents (schools, comps, inventory — like Demo 05), then feeds their merged outputs into the offer strategist. This combines sequential + parallel patterns.

## Reflection question
> SequentialAgent passes data via session state keys. What happens if two agents write to the same `output_key`? Does ADK overwrite or merge? Test it.
