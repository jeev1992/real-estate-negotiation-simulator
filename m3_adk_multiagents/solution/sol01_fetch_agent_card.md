# Solution 1: Fetch and Inspect the A2A Agent Card

## Complete script

> **Runnable version:** `m3_adk_multiagents/solution/sol01_fetch_agent_card.py`

Create `m3_adk_multiagents/fetch_agent_card.py`:

```python
"""Fetch and display an A2A Agent Card."""
import asyncio
import json
import httpx


async def main():
    url = "http://127.0.0.1:9102/.well-known/agent-card.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        card = response.json()

    print("=== A2A AGENT CARD ===")
    print(f"Name:        {card['name']}")
    print(f"Description: {card['description']}")
    print(f"Version:     {card['version']}")
    print(f"Protocol:    {card.get('protocolVersion', 'unknown')}")
    print(f"Transport:   {card.get('preferredTransport', 'unknown')}")

    caps = card.get("capabilities", {})
    print(f"\nCapabilities:")
    print(f"  Streaming:          {caps.get('streaming', False)}")
    print(f"  Push notifications: {caps.get('pushNotifications', False)}")

    skills = card.get("skills", [])
    print(f"\nSkills ({len(skills)}):")
    for skill in skills:
        print(f"  - {skill['name']}")
        print(f"    ID:   {skill['id']}")
        print(f"    Desc: {skill['description']}")
        print(f"    Tags: {', '.join(skill.get('tags', []))}")
        examples = skill.get("examples", [])
        if examples:
            print(f"    Example: {examples[0]}")

    provider = card.get("provider", {})
    print(f"\nProvider: {provider.get('organization', 'unknown')}")

    print(f"\n--- Raw JSON ---")
    print(json.dumps(card, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
```

## Expected output

```
=== A2A AGENT CARD ===
Name:        adk_seller_a2a_server
Description: ADK-backed seller agent exposed via A2A protocol
Version:     1.0.0
Protocol:    0.3.0
Transport:   JSONRPC

Capabilities:
  Streaming:          False
  Push notifications: False

Skills (1):
  - Real Estate Seller Negotiation
    ID:   real_estate_seller_negotiation
    Desc: Responds to buyer offers with ADK-generated counter-offers or acceptance
    Tags: real_estate, negotiation, seller, adk, a2a
    Example: Buyer offers $438,000 with 45-day close

Provider: Negotiation Workshop
```

## Key A2A vs MCP discovery differences

| Aspect | MCP Tool Discovery | A2A Agent Card |
|---|---|---|
| **Scope** | Individual functions | Entire agent with skills |
| **Protocol** | `list_tools()` over active session | HTTP GET to static endpoint |
| **Timing** | After connection established | Before any connection |
| **Schema** | JSON Schema per tool parameter | Skill descriptions + examples |
| **Transport** | Same channel (stdio/SSE) | Standard HTTP |

## Verify
```bash
# Terminal 1:
python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102

# Terminal 2:
python m3_adk_multiagents/fetch_agent_card.py
```
