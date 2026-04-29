"""
Demo 10 — A2A Context Threading
==================================
A2A uses `contextId` to thread multiple messages into one conversation.
This script sends 3 negotiation rounds to the seller, reusing the
contextId from round 1 so all rounds are recognized as one negotiation.

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
    """Create a buyer offer envelope for a given round."""
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
    context_id: str | None = None

    async with httpx.AsyncClient(timeout=90.0) as http:
        resolver = A2ACardResolver(httpx_client=http, base_url=args.seller_url)
        card = await resolver.get_agent_card()
        client = A2AClient(httpx_client=http, agent_card=card)

        for round_num, price in enumerate(
            [432_000, 440_000, 446_000], start=1
        ):
            params = MessageSendParams(
                message=Message(
                    messageId=f"msg_{uuid.uuid4().hex[:8]}",
                    role=Role.user,
                    parts=[
                        TextPart(
                            text=buyer_round(session_id, round_num, price)
                        )
                    ],
                    contextId=context_id,  # None on round 1, threaded after
                )
            )
            request = SendMessageRequest(
                id=f"req_{uuid.uuid4().hex[:8]}", params=params
            )
            response = await client.send_message(request)
            result = response.model_dump(mode="json").get("result", {})

            # Capture contextId from round 1 and reuse on later rounds
            if context_id is None:
                context_id = result.get("contextId") or (
                    result.get("status") or {}
                ).get("contextId")

            print(f"\n=== round {round_num} (contextId={context_id}) ===")
            print(json.dumps(result, indent=2)[:1200])


if __name__ == "__main__":
    asyncio.run(main())
