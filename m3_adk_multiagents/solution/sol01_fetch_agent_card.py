"""
Solution 1: Fetch and display an A2A Agent Card.

Usage:
  1. Start the seller server in another terminal:
       python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102

  2. Run this script:
       python m3_adk_multiagents/solution/sol01_fetch_agent_card.py
"""

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
