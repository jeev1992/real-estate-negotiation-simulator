"""
Demo 13 — A2A Orchestrated Negotiation
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
    adk web --a2a m2_adk_multiagents/negotiation_agents/ --port 8000

Run:
    python m2_adk_multiagents/a2a_13_orchestrated_negotiation.py
"""

import argparse
import asyncio
import re
import uuid

import warnings

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    Message,
    MessageSendParams,
    Role,
    SendMessageRequest,
    SendMessageSuccessResponse,
    Task,
    TextPart,
)

# Classic A2AClient is used intentionally for parity with the other demos.
warnings.filterwarnings(
    "ignore", message=".*A2AClient is deprecated.*", category=DeprecationWarning
)

BASE_URL = "http://127.0.0.1:8000"
MAX_ROUNDS = 5


def extract_agent_text(task: Task) -> str:
    """Extract the agent's text response from an A2A Task."""
    # Try artifacts first (durable output)
    for artifact in task.artifacts or []:
        for part in artifact.parts:
            if isinstance(part.root, TextPart):
                return part.root.text
    # The final agent turn often lands in status.message, not history/artifacts
    status_message = task.status.message if task.status else None
    if status_message and status_message.role == Role.agent:
        for part in status_message.parts:
            if isinstance(part.root, TextPart):
                return part.root.text
    # Fall back to last agent message in history
    for msg in reversed(task.history or []):
        if msg.role == Role.agent:
            for part in msg.parts:
                if isinstance(part.root, TextPart):
                    return part.root.text
    return "(no response)"


def extract_price(text: str) -> str | None:
    """Best-effort extraction of a dollar amount from an agent message."""
    match = re.search(r"\$\s?([\d,]{4,})", text)
    return f"${match.group(1)}" if match else None


async def send_a2a_message(
    client: A2AClient,
    text: str,
    context_id: str | None = None,
) -> tuple[Task, str | None]:
    """Send a message to an A2A agent and return (Task, contextId)."""
    request = SendMessageRequest(
        id=f"req_{uuid.uuid4().hex[:8]}",
        params=MessageSendParams(
            message=Message(
                messageId=f"msg_{uuid.uuid4().hex[:8]}",
                role=Role.user,
                parts=[TextPart(text=text)],
                contextId=context_id,
            )
        ),
    )
    response = await client.send_message(request)
    result = response.root
    if isinstance(result, SendMessageSuccessResponse) and isinstance(result.result, Task):
        task = result.result
        return task, task.context_id
    raise RuntimeError(f"Unexpected response: {response.model_dump(mode='json')}")


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
        buyer_client = A2AClient(httpx_client=http, agent_card=buyer_card)
        print(f"\nBuyer Agent Card:")
        print(f"  Name:   {buyer_card.name}")
        print(f"  URL:    {buyer_card.url}")
        print(f"  Skills: {[s.name for s in buyer_card.skills]}")

        seller_resolver = A2ACardResolver(httpx_client=http, base_url=seller_url)
        seller_card = await seller_resolver.get_agent_card()
        seller_client = A2AClient(httpx_client=http, agent_card=seller_card)
        print(f"\nSeller Agent Card:")
        print(f"  Name:   {seller_card.name}")
        print(f"  URL:    {seller_card.url}")
        print(f"  Skills: {[s.name for s in seller_card.skills]}")

        # ── Step 2: Multi-round negotiation ───────────────────────────
        print("\n" + "=" * 60)
        print("STEP 2: Multi-Round Negotiation via A2A")
        print("=" * 60)

        buyer_context_id = None
        seller_context_id = None
        seller_response_text = None  # No seller response for round 1
        messages_sent = 0
        outcome = None

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

            print(f"\n→ Sending to BUYER:\n{buyer_prompt}")
            buyer_task, buyer_context_id = await send_a2a_message(
                buyer_client, buyer_prompt, buyer_context_id
            )
            messages_sent += 1
            buyer_offer_text = extract_agent_text(buyer_task)
            print(f"← Buyer says:\n{buyer_offer_text}")
            print(f"  (contextId: {buyer_context_id})")

            # ── Buyer walked away? End the negotiation ────────────────
            if re.search(r"\bWALK[\s_-]?AWAY\b", buyer_offer_text, re.IGNORECASE):
                print(f"\n{'=' * 60}")
                print(f"BUYER WALKED AWAY in round {round_num} — no deal.")
                print(f"{'=' * 60}")
                outcome = "buyer_walked_away"
                break

            # ── Forward buyer's offer to seller ───────────────────────
            seller_prompt = (
                f"The buyer makes this offer:\n\n{buyer_offer_text}\n\n"
                f"This is round {round_num}. Respond with ACCEPT or COUNTER."
            )

            print(f"\n→ Sending to SELLER:\n{seller_prompt}")
            seller_task, seller_context_id = await send_a2a_message(
                seller_client, seller_prompt, seller_context_id
            )
            messages_sent += 1
            seller_response_text = extract_agent_text(seller_task)
            print(f"← Seller says:\n{seller_response_text}")
            print(f"  (contextId: {seller_context_id})")

            # ── Check for acceptance (exactly one keyword expected) ───
            has_counter = bool(re.search(r"\bCOUNTER\b", seller_response_text, re.IGNORECASE))
            has_accept = bool(re.search(r"\bACCEPT\b", seller_response_text, re.IGNORECASE))
            if has_accept and not has_counter:
                agreed_price = extract_price(seller_response_text)
                print(f"\n{'=' * 60}")
                print(f"DEAL REACHED in round {round_num}!")
                print(f"{'=' * 60}")
                deal_msg = "Buyer's final offer was accepted by the seller."
                if agreed_price:
                    deal_msg += f" Agreed price: {agreed_price}."
                print(deal_msg)
                outcome = "deal"
                break
        else:
            print(f"\n{'=' * 60}")
            print(f"MAX ROUNDS ({args.max_rounds}) reached — no agreement.")
            print(f"{'=' * 60}")
            outcome = "max_rounds"

        # ── Summary ──────────────────────────────────────────────────
        print(f"\nA2A Protocol Summary:")
        print(f"  Outcome:          {outcome}")
        print(f"  Buyer  contextId: {buyer_context_id}")
        print(f"  Seller contextId: {seller_context_id}")
        print(f"  Total A2A messages sent: {messages_sent}")
        print(f"  Each agent maintained its own conversation thread.")


if __name__ == "__main__":
    asyncio.run(main())
