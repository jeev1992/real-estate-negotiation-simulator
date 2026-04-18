"""
A2A Demo 05 — Context threading across multiple turns
=======================================================
A2A `contextId` + `taskId` are how a client correlates follow-up messages
with prior interactions. Here we run rounds 1, 2, 3 of a negotiation and
reuse the `contextId` returned in round 1's task across the later rounds —
so the seller server's session registry recognizes them as the same
negotiation thread.

Prereq:
    python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102

Run:
    python m3_adk_multiagents/demos/05_context_threading.py --seller-url http://127.0.0.1:9102
"""

import argparse
import asyncio
import json
import uuid

import httpx
from a2a.client import A2AClient, A2ACardResolver
from a2a.types import Message, MessageSendParams, Role, SendMessageRequest, TextPart


def buyer_round(session_id: str, round_num: int, price: int) -> str:
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--seller-url", default="http://127.0.0.1:9102")
    args = parser.parse_args()

    session_id = f"thread-{uuid.uuid4().hex[:6]}"
    context_id: str | None = None

    async with httpx.AsyncClient(timeout=90.0) as http:
        resolver = A2ACardResolver(httpx_client=http, base_url=args.seller_url)
        card = await resolver.get_agent_card()
        client = A2AClient(httpx_client=http, agent_card=card)

        for round_num, price in enumerate([432_000, 440_000, 446_000], start=1):
            params = MessageSendParams(
                message=Message(
                    messageId=f"msg_{uuid.uuid4().hex[:8]}",
                    role=Role.user,
                    parts=[TextPart(text=buyer_round(session_id, round_num, price))],
                    contextId=context_id,  # None on round 1, threaded after.
                )
            )
            request = SendMessageRequest(id=f"req_{uuid.uuid4().hex[:8]}", params=params)
            response = await client.send_message(request)
            result = response.model_dump(mode="json").get("result", {})

            # Capture the contextId the server assigned on round 1 and reuse
            # it on rounds 2 and 3 so they thread together.
            if context_id is None:
                context_id = result.get("contextId") or (result.get("status") or {}).get("contextId")

            print(f"\n=== round {round_num} (contextId={context_id}) ===")
            print(json.dumps(result, indent=2)[:1200])


if __name__ == "__main__":
    asyncio.run(main())
