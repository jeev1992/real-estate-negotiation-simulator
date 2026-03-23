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

    # Step 1: Create a buyer offer locally via ADK + MCP tool calls.
    # The buyer agent connects to the pricing MCP server, calls get_market_price
    # and calculate_discount, then GPT-4o decides the offer price.
    # All of this happens in-process — no network calls yet.
    async with BuyerAgentADK(session_id=f"buyer_a2a_{uuid.uuid4().hex[:8]}") as buyer:
        offer = await buyer.make_initial_offer_envelope()

    # The offer envelope is a dict with session_id, round, price, message, etc.
    # We serialize it to JSON text for transport over the A2A protocol.
    offer_text = json.dumps(offer)

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        # Step 2: Discover seller capabilities from the Agent Card URL.
        # A2ACardResolver issues GET /.well-known/agent-card.json and returns
        # the AgentCard object with endpoint URL, skills, and capabilities.
        resolver = A2ACardResolver(httpx_client=http_client, base_url=args.seller_url)
        card = await resolver.get_agent_card()
        # A2AClient wraps the HTTP transport — it knows the seller's endpoint
        # from the card, so we never hardcode URLs.
        client = A2AClient(httpx_client=http_client, agent_card=card)

        # Step 3: Send a typed A2A message to the seller endpoint.
        # The protocol framing is: SendMessageRequest → MessageSendParams → Message → TextPart.
        # - id: unique JSON-RPC request ID (for correlation)
        # - messageId: unique message ID (for threading)
        # - role: Role.user means "this is input from the requesting agent"
        # - parts: the actual content — our offer JSON wrapped in a TextPart
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
    # Helpful view for workshop demos: show only human-readable text snippets.
    if texts:
        print("\nExtracted text parts:")
        for text in texts:
            print(f"- {text}")


if __name__ == "__main__":
    asyncio.run(main())
