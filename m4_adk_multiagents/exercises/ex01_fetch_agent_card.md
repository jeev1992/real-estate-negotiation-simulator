# Exercise 1 — Fetch and Inspect the A2A Agent Card `[Core]`

## Goal
Write a small standalone script that discovers the seller agent by fetching its Agent Card from `/.well-known/agent-card.json`. This teaches you **A2A agent discovery** — how clients find and understand remote agents before communicating with them.

## What to look for
In `m4_adk_multiagents/a2a_protocol_seller_server.py`, find the `_build_agent_card()` function. Notice:
- The `AgentCard` contains metadata: name, description, version, capabilities, skills
- Each `AgentSkill` describes what the agent can do, with tags and examples
- The card is served at `/.well-known/agent-card.json` (standard A2A discovery endpoint)

This is the A2A equivalent of MCP's tool discovery — but for entire agents, not individual tools.

## Steps

### Step 1 — Start the seller server
In a terminal:
```bash
python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102
```

### Step 2 — Create the discovery script
Create a new file `m4_adk_multiagents/fetch_agent_card.py`:

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

### Step 3 — Run the discovery script
In a second terminal (while the seller server is running):
```bash
python m4_adk_multiagents/fetch_agent_card.py
```

## Verify
- The script prints the agent's name, description, skills, and capabilities
- The raw JSON matches what `_build_agent_card()` constructs in the server
- The skill "Real Estate Seller Negotiation" appears with its tags

## Reflection question
> How is the Agent Card different from MCP tool discovery? Think about:
> - **Scope**: An MCP tool is a single function; an Agent Card describes an entire agent with multiple skills
> - **Discovery**: MCP uses `list_tools()` over an active session; A2A uses a static HTTP endpoint
> - **When**: A2A discovery happens before any connection; MCP discovery requires an active session
