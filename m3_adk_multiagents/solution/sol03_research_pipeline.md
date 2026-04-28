# Solution 3 — Build a Research Pipeline

## Complete `agent.py`

```python
"""Exercise 03 — Three-stage research pipeline with SequentialAgent."""

from google.adk.agents import LlmAgent, SequentialAgent

MODEL = "openai/gpt-4o"

researcher = LlmAgent(
    name="researcher",
    model=MODEL,
    instruction=(
        "Research 742 Evergreen Terrace in Austin TX 78701. Report:\n"
        "- Median home price in ZIP 78701\n"
        "- Average days on market\n"
        "- Current inventory level (low/medium/high)\n"
        "- School district rating\n"
        "Two sentences max. Be specific with numbers."
    ),
    output_key="research_brief",
)

offer_strategist = LlmAgent(
    name="offer_strategist",
    model=MODEL,
    instruction=(
        "Read {research_brief}. The property at 742 Evergreen Terrace is "
        "listed at $485,000.\n\n"
        "Draft a specific offer strategy:\n"
        "- Recommended offer price (with justification from the research)\n"
        "- Key contingencies to include\n"
        "- Proposed closing timeline\n"
        "One paragraph."
    ),
    output_key="offer_strategy",
)

risk_assessor = LlmAgent(
    name="risk_assessor",
    model=MODEL,
    instruction=(
        "Read {offer_strategy} and {research_brief}.\n\n"
        "Identify the top 3 risks with this offer. For each:\n"
        "- Risk name\n"
        "- Severity: HIGH / MEDIUM / LOW\n"
        "- One specific mitigation action\n\n"
        "Format as a numbered list."
    ),
    output_key="risk_assessment",
)

root_agent = SequentialAgent(
    name="research_pipeline",
    description="Three-stage property research: research → strategy → risk assessment.",
    sub_agents=[researcher, offer_strategist, risk_assessor],
)
```

## Stretch goal: Parallel researcher

```python
from google.adk.agents import ParallelAgent

schools_agent = LlmAgent(
    name="schools", model=MODEL,
    instruction="One sentence on Austin ISD school quality near 78701.",
    output_key="schools_data",
)
comps_agent = LlmAgent(
    name="comps", model=MODEL,
    instruction="One sentence on recent comparable home sales near 78701.",
    output_key="comps_data",
)
inventory_agent = LlmAgent(
    name="inventory", model=MODEL,
    instruction="One sentence on current housing inventory pressure in 78701.",
    output_key="inventory_data",
)

parallel_researcher = ParallelAgent(
    name="parallel_researcher",
    sub_agents=[schools_agent, comps_agent, inventory_agent],
)

# Update offer_strategist to read from parallel outputs
offer_strategist_v2 = LlmAgent(
    name="offer_strategist",
    model=MODEL,
    instruction=(
        "Read the research data:\n"
        "- Schools: {schools_data}\n"
        "- Comps: {comps_data}\n"
        "- Inventory: {inventory_data}\n\n"
        "The property is listed at $485,000. Draft a specific offer strategy."
    ),
    output_key="offer_strategy",
)

root_agent = SequentialAgent(
    name="research_pipeline",
    description="Parallel research → sequential strategy + risk.",
    sub_agents=[parallel_researcher, offer_strategist_v2, risk_assessor],
)
```

## Key takeaways

- `output_key` is the bridge between agents — each agent writes, the next reads via `{placeholder}`
- SequentialAgent guarantees order; ParallelAgent guarantees concurrency
- You can nest them: SequentialAgent containing a ParallelAgent as one of its sub-agents

## Reflection answer
> If two agents write to the same `output_key`, the second one overwrites the first. ADK does NOT merge — it's a simple dict assignment. This is why each agent needs a unique `output_key`.
