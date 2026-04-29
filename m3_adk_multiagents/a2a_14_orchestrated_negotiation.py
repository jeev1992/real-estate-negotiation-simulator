"""
Demo 14 — A2A Orchestrated Negotiation
=========================================
Full multi-round buyer ↔ seller negotiation where BOTH agents are
discovered via Agent Cards and communicate through A2A messages.

THIS IS THE PAYOFF DEMO. It shows:
  1. Agent Card discovery for BOTH buyer and seller
  2. Multi-round negotiation orchestrated by a Python script
  3. Buyer sends offer → script relays to seller → seller responds
  4. contextId threads each side's conversation independently
  5. The script acts as a "matchmaker" — neither agent knows about the other

HOW IT WORKS:
  The script is NOT an agent itself — it's a simple orchestrator that:
  - Discovers buyer_agent and seller_agent via their Agent Cards
  - Asks the buyer to make an offer (via A2A message/send)
  - Forwards the buyer's offer to the seller (via A2A message/send)
  - Reads the seller's response (ACCEPT or COUNTER)
  - If COUNTER: sends the counter back to the buyer for next round
  - Repeats until ACCEPT or max rounds

  Each agent has its own contextId — the buyer's conversation thread
  and the seller's conversation thread are separate. The script bridges
  them by extracting text from one response and sending it to the other.

WHAT LEARNERS SEE:
  - Two Agent Card fetches (buyer + seller capabilities)
  - Alternating A2A messages to each agent
  - Each agent calling its own MCP tools (visible in the server terminal)
  - Agreement or max rounds reached

Prereq:
    adk web --a2a m3_adk_multiagents/negotiation_agents/ --port 8000

Run:
    python m3_adk_multiagents/adk_demos/a2a_14_orchestrated_negotiation.py
"""

import argparse
import asyncio
import json
import uuid

import httpx
from a2a.client import A2ACardResolver
from a2a.types import (
    Message,
    MessageSendParams,
    Role,
    SendMessageRequest,
    TextPart,
)

BASE_URL = "http://127.0.0.1:8000"
MAX_ROUNDS = 5


def extract_agent_text(result: dict) -> str:
    """Extract the agent's text response from an A2A result."""
    # Try artifacts first (durable output)
    for artifact in result.get("artifacts") or []:
        for part in artifact.get("parts") or []:
            if part.get("kind") == "text":
                return part["text"]
    # Fall back to last agent message in history
    for msg in reversed(result.get("history") or []):
        if msg.get("role") == "agent":
            for part in msg.get("parts") or []:
                if part.get("kind") == "text":
                    return part["text"]
    return "(no response)"


async def send_a2a_message(
    http: httpx.AsyncClient,
    agent_card: dict,
    text: str,
    context_id: str | None = None,
) -> tuple[dict, str | None]:
    """Send a message to an A2A agent and return (result, contextId)."""
    url = agent_card["url"]
    request_body = {
        "jsonrpc": "2.0",
        "id": f"req_{uuid.uuid4().hex[:8]}",
        "method": "message/send",
        "params": {
            "message": {
                "messageId": f"msg_{uuid.uuid4().hex[:8]}",
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
                **({"contextId": context_id} if context_id else {}),
            }
        },
    }
    resp = await http.post(url, json=request_body)
    resp.raise_for_status()
    data = resp.json()
    result = data.get("result", {})
    new_context_id = result.get("contextId")
    return result, new_context_id


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="A2A orchestrated multi-round negotiation"
    )
    parser.add_argument(
        "--base-url", default=BASE_URL, help="Base URL of adk web --a2a"
    )
    parser.add_argument(
        "--max-rounds", type=int, default=MAX_ROUNDS, help="Max negotiation rounds"
    )
    args = parser.parse_args()

    buyer_url = f"{args.base_url}/a2a/buyer_agent"
    seller_url = f"{args.base_url}/a2a/seller_agent"

    async with httpx.AsyncClient(timeout=120.0) as http:

        # ── Step 1: Discover both agents via Agent Cards ──────────────
        print("=" * 60)
        print("STEP 1: Agent Card Discovery")
        print("=" * 60)

        buyer_resolver = A2ACardResolver(httpx_client=http, base_url=buyer_url)
        buyer_card = await buyer_resolver.get_agent_card()
        buyer_card_dict = buyer_card.model_dump(mode="json")
        print(f"\nBuyer Agent Card:")
        print(f"  Name:   {buyer_card_dict['name']}")
        print(f"  URL:    {buyer_card_dict['url']}")
        print(f"  Skills: {[s['name'] for s in buyer_card_dict.get('skills', [])]}")

        seller_resolver = A2ACardResolver(httpx_client=http, base_url=seller_url)
        seller_card = await seller_resolver.get_agent_card()
        seller_card_dict = seller_card.model_dump(mode="json")
        print(f"\nSeller Agent Card:")
        print(f"  Name:   {seller_card_dict['name']}")
        print(f"  URL:    {seller_card_dict['url']}")
        print(f"  Skills: {[s['name'] for s in seller_card_dict.get('skills', [])]}")

        # ── Step 2: Multi-round negotiation ───────────────────────────
        print("\n" + "=" * 60)
        print("STEP 2: Multi-Round Negotiation via A2A")
        print("=" * 60)

        buyer_context_id = None
        seller_context_id = None
        seller_response_text = None  # No seller response for round 1

        for round_num in range(1, args.max_rounds + 1):
            print(f"\n{'─' * 50}")
            print(f"ROUND {round_num}")
            print(f"{'─' * 50}")

            # ── Ask buyer for an offer ────────────────────────────────
            if seller_response_text:
                buyer_prompt = (
                    f"The seller responded: {seller_response_text}\n\n"
                    f"This is round {round_num}. Make your next offer."
                )
            else:
                buyer_prompt = (
                    "Make your opening offer for 742 Evergreen Terrace, "
                    "Austin TX 78701 (listed at $485,000). "
                    "Use your pricing tools first."
                )

            print(f"\n→ Sending to BUYER: {buyer_prompt[:80]}...")
            buyer_result, buyer_context_id = await send_a2a_message(
                http, buyer_card_dict, buyer_prompt, buyer_context_id
            )
            buyer_offer_text = extract_agent_text(buyer_result)
            print(f"← Buyer says: {buyer_offer_text[:200]}...")
            print(f"  (contextId: {buyer_context_id})")

            # ── Forward buyer's offer to seller ───────────────────────
            seller_prompt = (
                f"The buyer makes this offer:\n\n{buyer_offer_text}\n\n"
                f"This is round {round_num}. Respond with ACCEPT or COUNTER."
            )

            print(f"\n→ Sending to SELLER: {seller_prompt[:80]}...")
            seller_result, seller_context_id = await send_a2a_message(
                http, seller_card_dict, seller_prompt, seller_context_id
            )
            seller_response_text = extract_agent_text(seller_result)
            print(f"← Seller says: {seller_response_text[:200]}...")
            print(f"  (contextId: {seller_context_id})")

            # ── Check for acceptance ──────────────────────────────────
            # The seller's standalone agent uses the same instruction as
            # the orchestrator: "respond with ACCEPT or COUNTER."
            # We check for COUNTER first — if present, it's definitely
            # not an acceptance (even if "acceptable" appears elsewhere).
            import re
            has_counter = bool(re.search(r'\bCOUNTER\b', seller_response_text, re.IGNORECASE))
            has_accept = bool(re.search(r'\bACCEPT\b', seller_response_text, re.IGNORECASE))
            if has_accept and not has_counter:
                print(f"\n{'=' * 60}")
                print(f"DEAL REACHED in round {round_num}!")
                print(f"{'=' * 60}")
                print(f"Buyer's final offer was accepted by the seller.")
                break
        else:
            print(f"\n{'=' * 60}")
            print(f"MAX ROUNDS ({args.max_rounds}) reached — no agreement.")
            print(f"{'=' * 60}")

        # ── Summary ──────────────────────────────────────────────────
        print(f"\nA2A Protocol Summary:")
        print(f"  Buyer  contextId: {buyer_context_id}")
        print(f"  Seller contextId: {seller_context_id}")
        print(f"  Total A2A messages sent: {round_num * 2}")
        print(f"  Each agent maintained its own conversation thread.")


if __name__ == "__main__":
    asyncio.run(main())
