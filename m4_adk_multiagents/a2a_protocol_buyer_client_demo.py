"""
True A2A Protocol Buyer Client Demo (ADK + OpenAI + A2A SDK)
=============================================================
Uses an ADK buyer agent to create an offer, then sends that offer to
an A2A protocol seller server over `a2a-sdk`.

Run (terminal 1):
  python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102

Run (terminal 2):
  python m4_adk_multiagents/a2a_protocol_buyer_client_demo.py --seller-url http://127.0.0.1:9102
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

import httpx
from a2a.client import A2AClient, A2ACardResolver
from a2a.types import Message, MessageSendParams, Role, SendMessageRequest, TextPart

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load OPENAI_API_KEY and other local vars from repo-root .env.
load_dotenv(REPO_ROOT / ".env")

from m4_adk_multiagents.buyer_adk import BuyerAgentADK


def _extract_texts(obj):
    """Walk nested response JSON and collect any text fields for easy demo output."""
    texts = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "text" and isinstance(v, str):
                texts.append(v)
            else:
                texts.extend(_extract_texts(v))
    elif isinstance(obj, list):
        for item in obj:
            texts.extend(_extract_texts(item))
    return texts


async def main() -> None:
    parser = argparse.ArgumentParser(description="True A2A buyer client demo")
    parser.add_argument("--seller-url", default="http://127.0.0.1:9102")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. Set it before running this demo.")
        raise SystemExit(1)

    # Step 1: create a buyer offer locally via ADK + MCP tool calls.
    async with BuyerAgentADK(session_id=f"buyer_a2a_{uuid.uuid4().hex[:8]}") as buyer:
        offer = await buyer.make_initial_offer_envelope()

    offer_text = json.dumps(offer)

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        # Step 2: discover seller capabilities from the Agent Card URL.
        resolver = A2ACardResolver(httpx_client=http_client, base_url=args.seller_url)
        card = await resolver.get_agent_card()
        client = A2AClient(httpx_client=http_client, agent_card=card)

        # Step 3: send a typed A2A user message to the seller endpoint.
        request = SendMessageRequest(
            id=f"req_{uuid.uuid4().hex[:8]}",
            params=MessageSendParams(
                message=Message(
                    messageId=f"msg_{uuid.uuid4().hex[:8]}",
                    role=Role.user,
                    parts=[TextPart(text=offer_text)],
                )
            ),
        )

        response = await client.send_message(request)

    # Keep full structured payload for teaching/debugging.
    dumped = response.model_dump(mode="json")
    # Also extract plain text snippets so the negotiation content is easy to read.
    texts = _extract_texts(dumped)

    print("\n=== TRUE A2A DEMO RESULT ===")
    print(f"Seller URL: {args.seller_url}")
    print(f"Buyer offer sent: {json.dumps(offer, indent=2)}")
    print("Response payload:")
    print(json.dumps(dumped, indent=2))
    if texts:
        print("\nExtracted text parts:")
        for text in texts:
            print(f"- {text}")


if __name__ == "__main__":
    asyncio.run(main())
