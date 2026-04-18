"""
A2A Demo 04 — Streaming negotiation via `message/stream`
==========================================================
Uses the A2A `message/stream` JSON-RPC method to receive incremental
TaskStatusUpdate / TaskArtifactUpdate events from the seller server.

Requires the seller server to advertise `capabilities.streaming = true`
(set in Phase 2 of `a2a_protocol_seller_server.py`).

Prereq:
    python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102

Run:
    python m3_adk_multiagents/demos/04_streaming_negotiation.py --seller-url http://127.0.0.1:9102
"""

import argparse
import asyncio
import json
import uuid

import httpx
from a2a.client import A2AClient, A2ACardResolver
from a2a.types import Message, MessageSendParams, Role, SendStreamingMessageRequest, TextPart


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seller-url", default="http://127.0.0.1:9102")
    args = parser.parse_args()

    buyer_envelope = {
        "session_id": f"stream-{uuid.uuid4().hex[:6]}",
        "round": 1,
        "from_agent": "buyer",
        "to_agent": "seller",
        "message_type": "OFFER",
        "price": 442_000,
        "message": "Streaming demo: opening offer at $442k.",
    }

    async with httpx.AsyncClient(timeout=120.0) as http:
        resolver = A2ACardResolver(httpx_client=http, base_url=args.seller_url)
        card = await resolver.get_agent_card()
        if not (card.capabilities and card.capabilities.streaming):
            print("WARN: server does not advertise streaming. Demo will likely error.")

        client = A2AClient(httpx_client=http, agent_card=card)

        request = SendStreamingMessageRequest(
            id=f"req_{uuid.uuid4().hex[:8]}",
            params=MessageSendParams(
                message=Message(
                    messageId=f"msg_{uuid.uuid4().hex[:8]}",
                    role=Role.user,
                    parts=[TextPart(text=json.dumps(buyer_envelope))],
                )
            ),
        )

        print("--- streaming events ---")
        async for event in client.send_message_streaming(request):
            dumped = event.model_dump(mode="json")
            kind = (dumped.get("result") or {}).get("kind") or dumped.get("result", {}).get("type") or "?"
            state = ((dumped.get("result") or {}).get("status") or {}).get("state")
            print(f"event kind={kind}  state={state}")
            print(json.dumps(dumped, indent=2)[:600])
            print("---")


if __name__ == "__main__":
    asyncio.run(main())
