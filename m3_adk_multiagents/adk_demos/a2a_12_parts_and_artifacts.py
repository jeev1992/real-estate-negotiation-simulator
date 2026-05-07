"""
Demo 12 — A2A Parts and Artifacts
====================================
Sends a Message with multiple parts (TextPart + DataPart) and inspects
any artifacts the server attaches to the Task response.

WHY MULTI-PART MESSAGES?
  Demo 10 sent a single TextPart — just a JSON string. But A2A Messages
  can carry MULTIPLE Parts of different types:

  - TextPart: plain text (what the LLM reads)
  - DataPart: structured JSON (what code parses)
  - FilePart: binary data with MIME type (PDFs, images)

  This demo sends BOTH a TextPart and a DataPart in the same Message —
  the offer in human-readable AND machine-readable form. The agent can
  use whichever format is more convenient.

WHAT ARE ARTIFACTS?
  Artifacts are DURABLE OUTPUTS attached to a completed Task.
  They're separate from the Message history.

  Think of it this way:
    Messages = the email thread (conversational, ordered)
    Artifacts = the attached report (the deliverable)

  In this demo, the seller's acceptance text appears in BOTH
  the history (as a Message) and as an Artifact. You'd use
  Artifacts when a downstream system needs to fetch the result
  without replaying the entire conversation.

Prereq:
    adk web --a2a m3_adk_multiagents/negotiation_agents/ --port 8000

Run:
    python m3_adk_multiagents/adk_demos/a2a_12_parts_and_artifacts.py \\
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
    TextPart,
)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="A2A parts and artifacts demo"
    )
    parser.add_argument(
        "--seller-url",
        default="http://127.0.0.1:8000/a2a/seller_agent",
    )
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

    # ── Two parts in one message ──────────────────────────────────────
    #
    # This is the key concept: we send the SAME offer in TWO formats
    # inside a single Message. The agent can use whichever is easier:
    #
    #   parts[0] = TextPart  → JSON string (the LLM reads this)
    #   parts[1] = DataPart  → structured dict (code can parse this directly)
    #
    # In production, you'd use DataPart for machine-to-machine fields
    # (prices, IDs, timestamps) and TextPart for human context.
    #
    parts = [
        TextPart(text=json.dumps(buyer_envelope)),
        DataPart(
            data={
                "hint": "machine-readable copy of the offer",
                "offer": buyer_envelope,
            }
        ),
    ]

    async with httpx.AsyncClient(timeout=60.0) as http:
        # ── Discover the agent and create client ──────────────────────
        resolver = A2ACardResolver(
            httpx_client=http, base_url=args.seller_url
        )
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

    # ── Inspect response status ───────────────────────────────────────
    print("=== response status ===")
    status = (result.get("status") or {}).get("state", "?")
    print(f"state: {status}")

    # ── Inspect response message parts ────────────────────────────────
    print("\n=== response message parts ===")
    history = result.get("history", [])
    for msg in history:
        role = msg.get("role", "?")
        msg_parts = msg.get("parts", [])
        print(f"  role={role}, {len(msg_parts)} part(s):")
        for i, part in enumerate(msg_parts):
            kind = part.get("kind", part.get("type", "?"))
            print(f"    [{i}] kind={kind}")
            if "text" in part:
                print(f"        text={part['text'][:200]}...")
            if "data" in part:
                print(f"        data keys={list(part['data'].keys())}")

    # ── Inspect artifacts ─────────────────────────────────────────────
    print("\n=== response artifacts ===")
    artifacts = result.get("artifacts") or []
    if not artifacts:
        print("  (no artifacts attached — this is normal for simple responses)")
        print("  Artifacts are for durable outputs: reports, summaries, files.")
    for artifact in artifacts:
        print(json.dumps(artifact, indent=2))

    # ── Key takeaways ─────────────────────────────────────────────────
    print("\n=== key takeaways ===")
    print("• Messages carry Parts: TextPart (text), DataPart (structured), FilePart (binary)")
    print("• Parts are conversational — they flow in the message history")
    print("• Artifacts are durable outputs — attached to the Task, not the Message")
    print("• Use DataPart when you need both human + machine representations")

    print(f"\n=== full response (truncated) ===")
    print(json.dumps(dumped, indent=2)[:2000])


if __name__ == "__main__":
    asyncio.run(main())
