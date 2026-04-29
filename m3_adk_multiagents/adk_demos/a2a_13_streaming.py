"""
Demo 13 — A2A Streaming via `message/stream`
===============================================
Uses the A2A `message/stream` JSON-RPC method to receive incremental
SSE (Server-Sent Events) from the seller agent in real time.

WHY STREAMING?
  Demo 10 used `message/send` — you POST a request, wait for the full
  response, and get everything at once. Fine for simple cases.

  `message/stream` opens an SSE connection instead. The server pushes
  events as the task progresses:

    Event 1: status-update → state: "submitted"   (task created)
    Event 2: status-update → state: "working"     (agent started)
    Event 3: status-update → state: "working"     (tool call completed)
    Event 4: status-update → state: "working"     (tool result returned)
    Event 5: status-update → state: "working"     (LLM reasoning)
    Event 6: artifact-update                      (counter-offer text)
    Event 7: status-update → state: "completed"   (final: true)

  This lets the client show progress ("seller is thinking...") and
  deliver artifacts before the task officially completes.

STREAMING vs SEND — SAME RESULT, DIFFERENT DELIVERY:
  message/send:    POST → wait → one JSON response with everything
  message/stream:  POST → SSE connection → events arrive incrementally

  The seller's Agent Card must declare `capabilities.streaming: true`
  in agent.json for this to work. If false, the server returns JSON
  instead of SSE and the client errors.

TWO EVENT TYPES:
  - status-update:   Task state transitions (submitted/working/completed)
                     Metadata includes token usage, session IDs, state deltas
  - artifact-update: Durable output delivered mid-stream
                     Contains the counter-offer text as an Artifact

  The last event always has `final: true` — the client stops listening.

Prereq:
    adk web --a2a m3_adk_multiagents/negotiation_agents/ --port 8000

Run:
    python m3_adk_multiagents/adk_demos/a2a_13_streaming.py \\
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
    SendStreamingMessageRequest,
    TextPart,
)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="A2A streaming demo (message/stream)"
    )
    parser.add_argument(
        "--seller-url",
        default="http://127.0.0.1:8000/a2a/seller_agent",
    )
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
        resolver = A2ACardResolver(
            httpx_client=http, base_url=args.seller_url
        )
        card = await resolver.get_agent_card()

        # ── Step 1: Check streaming capability ────────────────────────
        # The Agent Card declares whether the agent supports streaming.
        # Good clients check this BEFORE attempting message/stream.
        # If false and you try anyway → server returns JSON (not SSE)
        # → client gets a 400 error.
        streaming_supported = (
            card.capabilities and card.capabilities.streaming
        )
        print(f"Server streaming capability: {streaming_supported}")
        if not streaming_supported:
            print(
                "WARN: Server does not advertise streaming. "
                "Demo may fall back to non-streaming behavior."
            )

        client = A2AClient(httpx_client=http, agent_card=card)

        # ── Step 2: Build a streaming request ─────────────────────────
        # SendStreamingMessageRequest (not SendMessageRequest) tells
        # the SDK to use message/stream instead of message/send.
        # Same message format — different delivery method.
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

        # ── Step 3: Stream events ─────────────────────────────────────
        # client.send_message_streaming() returns an async iterator.
        # Each iteration yields one SSE event — either a status-update
        # (task state change) or an artifact-update (durable output).
        #
        # Expected sequence:
        #   submitted → working (×N) → artifact-update → completed (final=True)
        #
        print("\n--- streaming events ---")
        event_count = 0
        async for event in client.send_message_streaming(request):
            event_count += 1
            dumped = event.model_dump(mode="json")
            result = dumped.get("result", {})

            # Classify the event
            kind = (
                result.get("kind")
                or result.get("type")
                or "unknown"
            )
            state = (result.get("status") or {}).get("state")
            is_final = result.get("final", False)

            print(f"\n[event {event_count}]")
            print(f"  kind:  {kind}")
            print(f"  state: {state}")
            print(f"  final: {is_final}")

            # Show artifact events separately
            if "artifact" in kind.lower() if isinstance(kind, str) else False:
                print(f"  artifact: {json.dumps(result.get('artifact', {}), indent=2)[:500]}")
            else:
                # Show truncated payload for status events
                print(f"  payload: {json.dumps(result, indent=2)[:600]}")

            print("  ---")

        # ── Summary ───────────────────────────────────────────────────
        print(f"\n=== summary ===")
        print(f"Total events received: {event_count}")
        print()
        print("Key takeaways:")
        print("• message/stream returns an async iterator of SSE events")
        print("• Each event is a TaskStatusUpdate or TaskArtifactUpdate")
        print("• The client sees state transitions in real time (working → completed)")
        print("• The last event has `final: true`")
        print("• Use message/send for simple request/response")
        print("• Use message/stream for UX that shows progress")


if __name__ == "__main__":
    asyncio.run(main())
