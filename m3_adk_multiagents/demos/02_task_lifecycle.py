"""
A2A Demo 02 — Task lifecycle (submitted -> working -> completed/failed)
========================================================================
Sends the same `message/send` request twice: once with a valid envelope
(succeeds) and once with a deliberately broken envelope (fails). For each,
prints the Task object so you can see status transitions.

Prereq:
    python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102

Run:
    python m3_adk_multiagents/demos/02_task_lifecycle.py --seller-url http://127.0.0.1:9102
"""

import argparse
import asyncio
import json
import uuid

import httpx
from a2a.client import A2AClient, A2ACardResolver
from a2a.types import Message, MessageSendParams, Role, SendMessageRequest, TextPart


def envelope_text(valid: bool) -> str:
    if valid:
        payload = {
            "session_id": f"demo-{uuid.uuid4().hex[:6]}",
            "round": 1,
            "from_agent": "buyer",
            "to_agent": "seller",
            "message_type": "OFFER",
            "price": 440_000,
            "message": "Round-1 offer at $440k.",
        }
    else:
        # Missing required field `session_id` — server should fail the task.
        payload = {"from_agent": "buyer", "message": "broken"}
    return json.dumps(payload)


async def send_once(client: A2AClient, label: str, text: str) -> None:
    request = SendMessageRequest(
        id=f"req_{uuid.uuid4().hex[:8]}",
        params=MessageSendParams(
            message=Message(
                messageId=f"msg_{uuid.uuid4().hex[:8]}",
                role=Role.user,
                parts=[TextPart(text=text)],
            )
        ),
    )
    print(f"\n=== {label} ===")
    response = await client.send_message(request)
    dumped = response.model_dump(mode="json")

    # The A2A response is either {"result": Message-or-Task} or {"error": ...}.
    result = dumped.get("result", dumped)
    status = (result.get("status") or {}).get("state") if isinstance(result, dict) else None
    print(f"task status: {status}")
    print(json.dumps(dumped, indent=2)[:1500])


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seller-url", default="http://127.0.0.1:9102")
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=60.0) as http:
        resolver = A2ACardResolver(httpx_client=http, base_url=args.seller_url)
        card = await resolver.get_agent_card()
        client = A2AClient(httpx_client=http, agent_card=card)

        await send_once(client, "valid envelope", envelope_text(valid=True))
        await send_once(client, "invalid envelope", envelope_text(valid=False))


if __name__ == "__main__":
    asyncio.run(main())
