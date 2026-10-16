"""
Demo 10 — A2A Wire Format and Task Lifecycle
================================================
Peek under the hood of the A2A protocol. This script:
  1. Fetches the Agent Card (discovery) via A2ACardResolver
  2. Sends a valid offer using typed SDK objects (DataPart)
  3. Sends a broken envelope to show graceful error handling

Uses the A2A SDK for type-safe message construction and transport.
We print the serialized wire format so you can see exactly what
JSON-RPC frames go over the wire.

WHAT IS A2A?
  A2A (Agent-to-Agent) is an open protocol for agents to discover and
  communicate with each other over HTTP. Think of it as MCP but for
  agents instead of tools:
    - MCP:  agent discovers TOOLS  → tools/list, tools/call
    - A2A:  agent discovers AGENTS → Agent Card, message/send

KEY A2A OBJECTS:
  Task     — unit of work (like a support ticket)
               Has a lifecycle: submitted → working → completed/failed
  Message  — one turn in the conversation (has role: user or agent)
  Part     — atomic content: TextPart, DataPart, or FilePart
  Artifact — durable output attached to a completed Task
  contextId — ties multiple Tasks into one conversation thread

Prereq:
    adk web --a2a m2_adk_multiagents/negotiation_agents/ --port 8000

Run:
    python m2_adk_multiagents/a2a_demos/a2a_10_wire_lifecycle.py \\
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
    SendMessageSuccessResponse,
    Task,
    TextPart,
)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="A2A wire format + task lifecycle demo"
    )
    parser.add_argument(
        "--seller-url",
        default="http://127.0.0.1:8000/a2a/seller_agent",
    )
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=60.0) as http:

        # ── Step 1: Discovery — fetch the Agent Card ──────────────────
        #
        # Before sending any messages, a client fetches the Agent Card.
        # This is the A2A equivalent of MCP's tools/list — it tells you:
        #   - What the agent does (name, description, skills)
        #   - Where to send messages (url)
        #   - What features are supported (streaming, push notifications)
        #
        # A2ACardResolver fetches from the well-known URL:
        #   GET /<agent>/.well-known/agent-card.json
        #
        # Where does --seller-url come from? Here it's direct configuration.
        # In production you'd often look the agent up in a registry first
        # (Google Cloud Agent Registry, AGNTCY Agent Directory, ...) by skill,
        # tag or keyword, and get its Agent Card back. A2A doesn't standardize
        # the registry API — see a2a_protocols.md §13.1.
        #
        print("=== 1. AGENT CARD (discovery) ===")
        resolver = A2ACardResolver(httpx_client=http, base_url=args.seller_url)
        card = await resolver.get_agent_card()
        print(json.dumps(card.model_dump(mode="json"), indent=2))
        print()

        client = A2AClient(httpx_client=http, agent_card=card)

        # ── Step 2: Valid offer — see task lifecycle ───────────────────
        #
        # Build a typed offer using DataPart (structured dict) instead
        # of stuffing JSON into a TextPart string. The SDK handles all
        # JSON-RPC framing — no manual envelope construction needed.
        #
        # What happens server-side:
        #   1. adk web receives the JSON-RPC request
        #   2. Creates a Task (status: submitted)
        #   3. Runs the seller LlmAgent (status: working)
        #      - LlmAgent calls MCP tools (get_market_price, etc.)
        #      - LLM produces counter-offer based on tool results
        #   4. Task completes (status: completed)
        #   5. Response includes contextId, history, and artifacts
        #
        print("=== 2. VALID OFFER ===")
        offer = {
            "round": 1,
            "from_agent": "buyer",
            "to_agent": "seller",
            "message_type": "OFFER",
            "price": 440_000,
            "conditions": ["inspection contingency"],
            "closing_timeline_days": 30,
        }
        request = SendMessageRequest(
            id=f"req_{uuid.uuid4().hex[:8]}",
            params=MessageSendParams(
                message=Message(
                    messageId=f"msg_{uuid.uuid4().hex[:8]}",
                    role=Role.user,
                    parts=[
                        TextPart(text="Opening offer at $440k, 30-day close, pre-approved."),
                        DataPart(data=offer),
                    ],
                )
            ),
        )

        # Print the wire format — this is what the SDK sends over HTTP
        print("WIRE FORMAT (what the SDK sends):")
        print(json.dumps(request.model_dump(mode="json", exclude_none=True), indent=2))

        response = await client.send_message(request)
        result = response.root

        if isinstance(result, SendMessageSuccessResponse):
            task_or_msg = result.result
            if isinstance(task_or_msg, Task):
                print(f"\nRESPONSE (status={task_or_msg.status.state.value}):")
                print(f"  contextId: {task_or_msg.context_id}")
                print(f"  artifacts: {len(task_or_msg.artifacts or [])}")
            print(json.dumps(result.model_dump(mode="json"), indent=2)[:1500])
        else:
            print(f"ERROR: {json.dumps(result.model_dump(mode='json'), indent=2)}")
        print()

        # ── Step 3: Broken envelope — graceful error handling ─────────
        #
        # Send garbage data — no price, no real structure.
        # The A2A protocol still works (valid JSON-RPC, valid Message)
        # so the task shows "completed" not "failed". The LLM handles
        # bad content gracefully: "Could you please resend your offer?"
        #
        # "completed" = the agent processed the request.
        # "failed" = protocol error or server crash.
        #
        print("=== 3. BROKEN ENVELOPE (expect graceful handling) ===")
        request = SendMessageRequest(
            id=f"req_{uuid.uuid4().hex[:8]}",
            params=MessageSendParams(
                message=Message(
                    messageId=f"msg_{uuid.uuid4().hex[:8]}",
                    role=Role.user,
                    parts=[TextPart(text="broken message with no real offer")],
                )
            ),
        )
        response = await client.send_message(request)
        result = response.root

        if isinstance(result, SendMessageSuccessResponse):
            task_or_msg = result.result
            if isinstance(task_or_msg, Task):
                print(f"RESPONSE (status={task_or_msg.status.state.value}):")
            print(json.dumps(result.model_dump(mode="json"), indent=2)[:1500])
        else:
            print(f"ERROR: {json.dumps(result.model_dump(mode='json'), indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
