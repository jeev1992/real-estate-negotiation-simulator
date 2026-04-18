"""
A2A Demo 01 — Hand-craft an A2A `message/send` request
=======================================================
No A2A SDK helpers, no ADK. Builds the JSON-RPC body for `message/send`
by hand and POSTs it to the running seller server. Useful for seeing the
exact wire shape A2A produces.

Prereq (Terminal A):
    python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102

Run (Terminal B):
    python m3_adk_multiagents/demos/01_handcraft_message_send.py --seller-url http://127.0.0.1:9102
"""

import argparse
import asyncio
import json
import uuid

import httpx


def make_jsonrpc_envelope(text: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": f"req_{uuid.uuid4().hex[:8]}",
        "method": "message/send",
        "params": {
            "message": {
                "messageId": f"msg_{uuid.uuid4().hex[:8]}",
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
            }
        },
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seller-url", default="http://127.0.0.1:9102")
    args = parser.parse_args()

    # Buyer envelope is the application-level payload the seller agent
    # parses out of the A2A message text. The A2A protocol itself doesn't
    # care about the schema — it only ferries the bytes.
    buyer_envelope = {
        "session_id": f"demo-{uuid.uuid4().hex[:6]}",
        "round": 1,
        "from_agent": "buyer",
        "to_agent": "seller",
        "message_type": "OFFER",
        "price": 432_000,
        "message": "Opening offer at $432k, 30-day close, pre-approved.",
        "conditions": ["inspection contingency"],
        "closing_timeline_days": 30,
    }
    body = make_jsonrpc_envelope(json.dumps(buyer_envelope))

    print("POST URL :", args.seller_url)
    print("REQUEST  :"); print(json.dumps(body, indent=2))

    async with httpx.AsyncClient(timeout=60.0) as http:
        # 1. Discovery (optional but illustrative): fetch Agent Card.
        card_resp = await http.get(args.seller_url.rstrip("/") + "/.well-known/agent-card.json")
        print("\nAGENT CARD:")
        print(json.dumps(card_resp.json(), indent=2))

        # 2. Send the JSON-RPC message. The seller's A2A endpoint is the
        # base URL itself per the AgentCard.url field.
        rpc_resp = await http.post(args.seller_url, json=body)
        print("\nRESPONSE :", rpc_resp.status_code)
        print(json.dumps(rpc_resp.json(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
