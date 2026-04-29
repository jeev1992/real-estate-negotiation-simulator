# Exercise 5 — Fetch the Agent Card via A2A `[Core]`

## Goal
Write a standalone script that discovers the seller agent by fetching its A2A Agent Card from the `adk web --a2a` server. This teaches **A2A agent discovery** — how clients programmatically find and understand remote agents.

## Context
When you run `adk web --a2a m3_adk_multiagents/negotiation_agents/`, ADK automatically generates and serves Agent Cards for each agent. This exercise has you fetch and inspect one.

## Steps

### Step 1 — Start the agents with A2A endpoints
```bash
adk web --a2a m3_adk_multiagents/negotiation_agents/ --port 8000
```

### Step 2 — Browse the Agent Card
Open in your browser:
```
http://127.0.0.1:8000/a2a/seller_agent/.well-known/agent-card.json
```
Study the JSON. Note the structure: `name`, `description`, `url`, `capabilities`, `skills`.

### Step 3 — Write a discovery script
Create `m3_adk_multiagents/exercises/fetch_agent_card.py`:

```python
"""Fetch and display all A2A Agent Cards from the server."""
import asyncio
import json
import httpx

BASE_URL = "http://127.0.0.1:8000"
AGENTS = ["buyer_agent", "seller_agent", "negotiation"]


async def main():
    async with httpx.AsyncClient(timeout=10.0) as client:
        for agent_name in AGENTS:
            url = f"{BASE_URL}/{agent_name}/.well-known/agent-card.json"
            print(f"\n=== {agent_name} ===")
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                card = resp.json()

                # TODO: Print these fields from the card:
                # - name
                # - description
                # - capabilities (streaming? push notifications?)
                # - skills (how many? what are they?)
                # - url (the endpoint to send messages to)

                # TODO: Compare buyer_agent vs seller_agent cards.
                # What's different? What's the same?

                print(json.dumps(card, indent=2))

            except httpx.HTTPError as e:
                print(f"  Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Step 4 — Complete the TODOs
Replace the `json.dumps` with structured output that prints each field clearly. Then answer: what differences do you see between the buyer and seller Agent Cards?

### Step 5 — Run it
```bash
python m3_adk_multiagents/exercises/fetch_agent_card.py
```

## Verify
- Script fetches all 3 Agent Cards successfully
- Each card has `name`, `description`, and a `url` field
- You can explain what each field in the card is for

## Stretch goal
Modify the script to use the `a2a-sdk` client instead of raw `httpx`:
```python
from a2a.client import A2ACardResolver
resolver = A2ACardResolver(httpx_client=http, base_url=f"{BASE_URL}/seller_agent")
card = await resolver.get_agent_card()
```

Compare: what does the SDK give you that raw HTTP doesn't?

## Reflection question
> Agent Cards are like OpenAPI specs but for AI agents. What information would you add to an Agent Card to make it more useful for automated agent-to-agent discovery in a large organization with hundreds of agents?
