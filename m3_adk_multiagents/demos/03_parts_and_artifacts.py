"""
A2A Demo 03 — Parts and Artifacts
==================================
A2A `Message`s carry one or more `Parts` (text / file / data). Long-lived
outputs of a Task can be attached as `Artifact`s. This demo:

  - Sends a Message with multiple parts (text + structured data part)
  - Prints how the receiving server reflects them
  - Inspects any artifacts on the response Task

The seller server in Phase 2 attaches a final "negotiation-summary" data
artifact when the negotiation completes — so you can see it here.

Prereq:
    python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102

Run:
    python m3_adk_multiagents/demos/03_parts_and_artifacts.py --seller-url http://127.0.0.1:9102
"""

import argparse
import asyncio
import json
import uuid

import httpx
from a2a.client import A2AClient, A2ACardResolver
from a2a.types import (
    DataPart,
    Message,
    MessageSendParams,
    Role,
    SendMessageRequest,
    TextPart,
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seller-url", default="http://127.0.0.1:9102")
    args = parser.parse_args()

    buyer_envelope = {
        "session_id": f"demo-{uuid.uuid4().hex[:6]}",
        "round": 1,
        "from_agent": "buyer",
        "to_agent": "seller",
        "message_type": "OFFER",
        "price": 445_000,
        "message": "Final-and-best at $445k.",
    }

    # Two parts in one message: a human-readable text part PLUS a structured
    # data part that carries the same offer in machine form.
    parts = [
        TextPart(text=json.dumps(buyer_envelope)),
        DataPart(data={"hint": "machine-readable copy of the offer", "offer": buyer_envelope}),
    ]

    async with httpx.AsyncClient(timeout=60.0) as http:
        resolver = A2ACardResolver(httpx_client=http, base_url=args.seller_url)
        card = await resolver.get_agent_card()
        client = A2AClient(httpx_client=http, agent_card=card)

        request = SendMessageRequest(
            id=f"req_{uuid.uuid4().hex[:8]}",
            params=MessageSendParams(
                message=Message(
                    messageId=f"msg_{uuid.uuid4().hex[:8]}",
                    role=Role.user,
                    parts=parts,
                )
            ),
        )
        response = await client.send_message(request)

    dumped = response.model_dump(mode="json")
    result = dumped.get("result", dumped)
    print("=== response status ===")
    print((result.get("status") or {}).get("state"))

    print("\n=== response artifacts ===")
    for a in result.get("artifacts") or []:
        print(json.dumps(a, indent=2))

    print("\n=== full response (truncated) ===")
    print(json.dumps(dumped, indent=2)[:2000])


if __name__ == "__main__":
    asyncio.run(main())
