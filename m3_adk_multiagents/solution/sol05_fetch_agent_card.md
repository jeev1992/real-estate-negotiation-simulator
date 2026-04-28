# Solution 5 — Fetch the Agent Card via A2A

## Complete script

```python
"""Fetch and display all A2A Agent Cards from adk web --a2a."""
import asyncio
import json

import httpx

BASE_URL = "http://127.0.0.1:8000"
AGENTS = ["buyer_agent", "seller_agent", "negotiation"]


async def fetch_card(client: httpx.AsyncClient, agent_name: str) -> dict | None:
    """Fetch one Agent Card, return parsed JSON or None on error."""
    url = f"{BASE_URL}/{agent_name}/.well-known/agent-card.json"
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        print(f"  Error fetching {agent_name}: {e}")
        return None


def print_card(name: str, card: dict) -> None:
    """Pretty-print the key fields of an Agent Card."""
    print(f"\n{'=' * 60}")
    print(f"AGENT: {name}")
    print(f"{'=' * 60}")
    print(f"  Name:        {card.get('name', '?')}")
    print(f"  Description: {card.get('description', '?')}")
    print(f"  URL:         {card.get('url', '?')}")

    caps = card.get("capabilities", {})
    print(f"  Capabilities:")
    print(f"    Streaming:          {caps.get('streaming', False)}")
    print(f"    Push notifications: {caps.get('pushNotifications', False)}")

    skills = card.get("skills", [])
    print(f"  Skills ({len(skills)}):")
    for skill in skills:
        print(f"    - {skill.get('name', '?')}: {skill.get('description', '?')}")


async def main():
    async with httpx.AsyncClient(timeout=10.0) as client:
        cards = {}
        for agent_name in AGENTS:
            card = await fetch_card(client, agent_name)
            if card:
                cards[agent_name] = card
                print_card(agent_name, card)

        # Comparison
        if "buyer_agent" in cards and "seller_agent" in cards:
            print(f"\n{'=' * 60}")
            print("COMPARISON: buyer_agent vs seller_agent")
            print(f"{'=' * 60}")
            b, s = cards["buyer_agent"], cards["seller_agent"]
            print(f"  Same name?        {b.get('name') == s.get('name')}")
            print(f"  Same capabilities? {b.get('capabilities') == s.get('capabilities')}")
            buyer_skills = {sk.get("name") for sk in b.get("skills", [])}
            seller_skills = {sk.get("name") for sk in s.get("skills", [])}
            print(f"  Buyer skills:  {buyer_skills}")
            print(f"  Seller skills: {seller_skills}")
            print(f"  Shared skills: {buyer_skills & seller_skills}")
            print(f"  Unique to buyer:  {buyer_skills - seller_skills}")
            print(f"  Unique to seller: {seller_skills - buyer_skills}")


if __name__ == "__main__":
    asyncio.run(main())
```

## Stretch goal: using the A2A SDK

```python
from a2a.client import A2ACardResolver

async with httpx.AsyncClient(timeout=10.0) as http:
    for agent_name in AGENTS:
        resolver = A2ACardResolver(
            httpx_client=http,
            base_url=f"{BASE_URL}/{agent_name}",
        )
        card = await resolver.get_agent_card()
        # card is now a typed AgentCard object, not a dict
        print(f"{agent_name}: {card.name} — {card.description}")
        print(f"  Streaming: {card.capabilities.streaming}")
```

The SDK gives you a typed `AgentCard` object with proper field access, validation, and error handling — vs raw JSON that could have missing fields.

## Key takeaways

- Agent Cards are served at `/.well-known/agent-card.json` — a standardized discovery endpoint
- ADK auto-generates cards from your `LlmAgent` definition (name, description, tools → skills)
- Cards let clients discover agents without importing their code
- The `a2a-sdk` `A2ACardResolver` adds validation and type safety on top of raw HTTP

## Reflection answer
> Useful additions to Agent Cards for large organizations:
> - **Authentication requirements** (what credentials does this agent need?)
> - **Rate limits** (how many requests/second can it handle?)
> - **SLA information** (expected latency, uptime guarantees)
> - **Input/output schemas** (JSON Schema for what the agent expects and returns)
> - **Versioning** (semantic version + deprecation notices)
> - **Cost** (per-request pricing if applicable)
> - **Data classification** (does this agent handle PII? PHI? financial data?)
