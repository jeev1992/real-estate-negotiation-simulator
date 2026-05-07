"""
Demo 11 — A2A Context Threading
==================================
A2A uses `contextId` to thread multiple messages into one conversation.
This script sends 3 negotiation rounds to the seller, reusing the
contextId from round 1 so all rounds are recognized as one negotiation.

WHY CONTEXT THREADING MATTERS:
  Without contextId, each POST to the seller starts a BRAND NEW conversation.
  The seller would forget all prior offers and counter at $477K every time.

  With contextId, the seller remembers:
    Round 1: $432K → "Below $445K floor. Counter at $477K."
    Round 2: $440K → "STILL below. Counter at $477K."
    Round 3: $446K → "Above $445K! ACCEPT!"

  contextId is A2A's equivalent of ADK's session_id — same concept
  (conversation continuity), different level (HTTP vs in-process).

HOW IT WORKS:
  1. Round 1: client sends message WITHOUT contextId
  2. Server assigns a contextId and returns it in the response
  3. Rounds 2-3: client includes the SAME contextId in requests
  4. Server loads conversation history for that contextId each time

THIS SCRIPT USES THE A2A SDK (unlike demo 10 which was raw HTTP):
  - A2ACardResolver: fetches Agent Card for discovery
  - A2AClient: handles JSON-RPC formatting + HTTP transport
  - SendMessageRequest/Message/TextPart: typed A2A protocol objects

Prereq:
    adk web --a2a m3_adk_multiagents/negotiation_agents/ --port 8000

Run:
    python m3_adk_multiagents/adk_demos/a2a_11_context_threading.py \\
        --seller-url http://127.0.0.1:8000/a2a/seller_agent
"""

import argparse
import asyncio
import json
import uuid

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    Message,
    MessageSendParams,
    Role,
    SendMessageRequest,
    TextPart,
)


def buyer_round(session_id: str, round_num: int, price: int) -> str:
    """Create a buyer offer envelope for a given round.

    The offer is a JSON string inside a TextPart. The A2A protocol
    just ferries the text — the seller agent parses the JSON and
    reasons about the price, conditions, and round number.

    Example output:
      {"session_id": "thread-a1b2c3", "round": 2, "from_agent": "buyer",
       "to_agent": "seller", "message_type": "OFFER", "price": 440000,
       "message": "Round 2 offer at $440,000."}
    """
    return json.dumps({
        "session_id": session_id,
        "round": round_num,
        "from_agent": "buyer",
        "to_agent": "seller",
        "message_type": "OFFER",
        "price": price,
        "message": f"Round {round_num} offer at ${price:,}.",
    })


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="A2A context threading across multiple turns"
    )
    parser.add_argument(
        "--seller-url",
        default="http://127.0.0.1:8000/a2a/seller_agent",
    )
    args = parser.parse_args()

    session_id = f"thread-{uuid.uuid4().hex[:6]}"

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
            params = MessageSendParams(
                message=Message(
                    messageId=f"msg_{uuid.uuid4().hex[:8]}",
                    role=Role.user,
                    parts=[
                        TextPart(
                            text=buyer_round(session_id, round_num, price)
                        )
                    ],
                    contextId=context_id,
                )
            )
            request = SendMessageRequest(
                id=f"req_{uuid.uuid4().hex[:8]}", params=params
            )
            response = await client.send_message(request)
            result = response.model_dump(mode="json").get("result", {})

            # ── Capture contextId from round 1 ────────────────────────
            # The server assigns a unique contextId when it sees None.
            # We save it and pass it on rounds 2-3 so the server knows
            # these messages belong to the same conversation.
            if context_id is None:
                context_id = result.get("contextId") or (
                    result.get("status") or {}
                ).get("contextId")

            print(f"\n=== round {round_num} (contextId={context_id}) ===")
            # Truncated to 1200 chars — remove [:1200] to see full response
            print(json.dumps(result, indent=2)[:1200])


if __name__ == "__main__":
    asyncio.run(main())
