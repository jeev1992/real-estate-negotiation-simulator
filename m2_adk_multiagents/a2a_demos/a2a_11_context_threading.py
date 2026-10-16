"""
Demo 11 — A2A Context Threading
==================================
A2A uses `contextId` to thread multiple messages into one conversation.
This script sends 3 negotiation rounds to the seller, reusing the
contextId from round 1 so all rounds are recognized as one negotiation.
Then it sends a BONUS round 4 WITHOUT contextId to prove what happens
when the seller has no memory of prior rounds.

WHY CONTEXT THREADING MATTERS:
  Without contextId, each POST to the seller starts a BRAND NEW conversation.
  The seller would forget all prior offers and counter at $477K every time.

  With contextId, the seller remembers:
    Round 1: $432K → "Below $445K floor. Counter at $477K."
    Round 2: $440K → "STILL below. Counter at $477K."
    Round 3: $446K → "Above $445K! ACCEPT!"

  Bonus round (no contextId):
    Round 4: $440K → "Below $445K. Counter at $477K."
    Same price as round 2, but no memory — seller treats it as brand new.

  contextId is A2A's equivalent of ADK's session_id — same concept
  (conversation continuity), different level (HTTP vs in-process).

HOW IT WORKS:
  1. Round 1: client sends message WITHOUT contextId
  2. Server assigns a contextId and returns it in the response
  3. Rounds 2-3: client includes the SAME contextId in requests
  4. Server loads conversation history for that contextId each time
  5. Round 4: client sends WITHOUT contextId again — fresh conversation

BOTH THIS SCRIPT AND DEMO 10 USE THE A2A SDK:
  - A2ACardResolver: fetches Agent Card for discovery
  - A2AClient: handles JSON-RPC formatting + HTTP transport
  - SendMessageRequest/Message/DataPart: typed A2A protocol objects

Prereq:
    adk web --a2a m2_adk_multiagents/negotiation_agents/ --port 8000

Run:
    python m2_adk_multiagents/a2a_demos/a2a_11_context_threading.py \\
        --seller-url http://127.0.0.1:8000/a2a/seller_agent
"""

import argparse
import asyncio
import json
import uuid

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    DataPart,
    Message,
    MessageSendParams,
    Role,
    SendMessageRequest,
    SendMessageSuccessResponse,
    Task,
    TextPart,
)


def buyer_offer_parts(round_num: int, price: int) -> list:
    """Create typed A2A parts for a buyer offer.

    Returns [TextPart, DataPart] — human-readable text for the LLM
    plus structured data for machine parsing. No json.dumps needed;
    DataPart carries the dict natively.
    """
    return [
        TextPart(text=f"Round {round_num} offer at ${price:,}."),
        DataPart(data={
            "round": round_num,
            "from_agent": "buyer",
            "to_agent": "seller",
            "message_type": "OFFER",
            "price": price,
        }),
    ]


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="A2A context threading across multiple turns"
    )
    parser.add_argument(
        "--seller-url",
        default="http://127.0.0.1:8000/a2a/seller_agent",
    )
    args = parser.parse_args()

    # contextId starts as None. Round 1 gets it from the server response.
    # Rounds 2-3 reuse it so the seller sees the full conversation history.
    context_id: str | None = None

    async with httpx.AsyncClient(timeout=90.0) as http:

        # ── Step 1: Discover the seller agent via Agent Card ──────────
        # Same as demo 10 step 1, but using the A2A SDK helper.
        resolver = A2ACardResolver(httpx_client=http, base_url=args.seller_url)
        card = await resolver.get_agent_card()
        client = A2AClient(httpx_client=http, agent_card=card)

        # ── Step 2: Send 3 rounds with increasing prices ──────────────
        # $432K → $440K → $446K
        # The $446K offer is above the seller's $445K floor, so it should
        # be accepted — but ONLY if the seller remembers the floor from
        # the MCP tool call in round 1.
        for round_num, price in enumerate(
            [432_000, 440_000, 446_000], start=1
        ):
            # Build the A2A Message with typed SDK objects.
            # contextId=None on round 1 (server assigns it).
            # contextId=<round 1's value> on rounds 2-3 (threading).
            request = SendMessageRequest(
                id=f"req_{uuid.uuid4().hex[:8]}",
                params=MessageSendParams(
                    message=Message(
                        messageId=f"msg_{uuid.uuid4().hex[:8]}",
                        role=Role.user,
                        parts=buyer_offer_parts(round_num, price),
                        contextId=context_id,
                    )
                ),
            )
            response = await client.send_message(request)
            result = response.root

            # ── Capture contextId from round 1 ────────────────────────
            # The server assigns a unique contextId when it sees None.
            # We save it and pass it on rounds 2-3 so the server knows
            # these messages belong to the same conversation.
            if isinstance(result, SendMessageSuccessResponse) and isinstance(result.result, Task):
                task = result.result
                if context_id is None:
                    context_id = task.context_id
                print(f"\n=== round {round_num} (contextId={context_id}) ===")
                print(f"  status: {task.status.state.value}")
                print(json.dumps(result.model_dump(mode="json"), indent=2)[:3000])

        # ── Step 3: Bonus round — same price, NO contextId ────────────
        #
        # Send $440K again — the same price as round 2. But this time,
        # do NOT include contextId. The server treats this as a brand-new
        # conversation with zero history.
        #
        # Expected behavior: the seller has no memory of rounds 1-3.
        # It calls MCP tools fresh, discovers the $445K floor again,
        # and counters at $477K — exactly like round 1.
        #
        # This proves that contextId is the ONLY thing threading the
        # conversation. Without it, every request is a clean slate.
        #
        bonus_price = 440_000
        request = SendMessageRequest(
            id=f"req_{uuid.uuid4().hex[:8]}",
            params=MessageSendParams(
                message=Message(
                    messageId=f"msg_{uuid.uuid4().hex[:8]}",
                    role=Role.user,
                    parts=buyer_offer_parts(4, bonus_price),
                    contextId=None,  # ← deliberately no contextId
                )
            ),
        )
        response = await client.send_message(request)
        result = response.root

        new_context = None
        if isinstance(result, SendMessageSuccessResponse) and isinstance(result.result, Task):
            new_context = result.result.context_id

        print(f"\n=== round 4 — NO contextId (new contextId={new_context}) ===")
        print("Same $440K as round 2, but seller has NO memory of prior rounds.")
        print(json.dumps(result.model_dump(mode='json'), indent=2)[:3000])


if __name__ == "__main__":
    asyncio.run(main())
