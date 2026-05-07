"""
Stretch Solution: A2A streaming client
========================================

Sends a single offer to the seller agent via `message/stream` (SSE)
and renders task lifecycle events as they arrive — instead of waiting
for a single final response like `message/send` would.

Key differences from `multi_round_client.py`:
  • Uses `client.stream(...)` instead of `client.post(...)`
  • Reads SSE lines incrementally
  • Prints each event with a relative timestamp
  • Bails early if the agent doesn't declare capabilities.streaming

Prereq:
    adk web --a2a m3_adk_multiagents/negotiation_agents/

Then run:
    python m3_adk_multiagents/solution/stretch_streaming_client/streaming_client.py
"""

import argparse
import asyncio
import json
import sys
import time
import uuid

import httpx
from a2a.client import A2ACardResolver


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


# ─── SSE parsing ──────────────────────────────────────────────────────────────

async def stream_a2a_message(
    http: httpx.AsyncClient,
    agent_url: str,
    text: str,
):
    """POST a `message/stream` request and yield each SSE event as a dict.

    Each yielded value is the parsed `result` field of one SSE data frame.
    Raises if the response isn't text/event-stream.
    """
    request_body = {
        "jsonrpc": "2.0",
        "id": f"req_{uuid.uuid4().hex[:8]}",
        "method": "message/stream",   # ← the only line that differs from send
        "params": {
            "message": {
                "messageId": f"msg_{uuid.uuid4().hex[:8]}",
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
            }
        },
    }

    async with http.stream("POST", agent_url, json=request_body) as resp:
        resp.raise_for_status()
        if "text/event-stream" not in resp.headers.get("content-type", ""):
            raise RuntimeError(
                f"Expected SSE response (text/event-stream), got "
                f"{resp.headers.get('content-type')}"
            )

        # SSE format: zero or more `field: value` lines per event,
        # separated by blank lines. We only care about the `data:` lines.
        async for line in resp.aiter_lines():
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if not payload:
                continue
            try:
                frame = json.loads(payload)
            except json.JSONDecodeError:
                continue
            yield frame.get("result", {})


# ─── Event rendering ──────────────────────────────────────────────────────────

def render_event(event: dict, t0: float) -> None:
    """Print one A2A event with a relative timestamp."""
    elapsed = time.monotonic() - t0
    kind = event.get("kind", "unknown")

    if kind == "status-update":
        state = event.get("status", {}).get("state", "?")
        # Optional: pull token usage or tool-call hints from metadata if present.
        meta = event.get("status", {}).get("message", {}) or {}
        meta_parts = meta.get("parts") or []
        text_hint = ""
        for part in meta_parts:
            if part.get("kind") == "text":
                snippet = part.get("text", "").strip()
                if snippet:
                    text_hint = f" — {snippet[:60]}..."
                    break
        is_final = " [FINAL]" if event.get("final") else ""
        print(f"[+{elapsed:5.2f}s] status: {state}{text_hint}{is_final}")

    elif kind == "artifact-update":
        artifact = event.get("artifact", {})
        artifact_id = artifact.get("artifactId", "?")[:8]
        parts = artifact.get("parts", [])
        text = ""
        for part in parts:
            if part.get("kind") == "text":
                text = part.get("text", "")[:80]
                break
        print(f"[+{elapsed:5.2f}s] artifact: id={artifact_id}... text={text!r}")

    else:
        print(f"[+{elapsed:5.2f}s] {kind}: {event}")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def run_streaming_demo(base_url: str) -> None:
    seller_url = f"{base_url}/a2a/seller_agent"

    async with httpx.AsyncClient(timeout=120.0) as http:

        # ─ Step 1: capability check ──────────────────────────────────────
        print("=" * 60)
        print("STEP 1 — Capability check via Agent Card")
        print("=" * 60)

        card = (await A2ACardResolver(httpx_client=http, base_url=seller_url)
                .get_agent_card()).model_dump(mode="json")
        streaming_supported = card.get("capabilities", {}).get("streaming", False)
        print(f"Seller name:      {card['name']}")
        print(f"Streaming:        {streaming_supported}")

        if not streaming_supported:
            print("\nERROR: seller agent does not declare capabilities.streaming. "
                  "Cannot use message/stream. Either enable streaming on the agent "
                  "or use multi_round_client.py (which uses message/send).")
            sys.exit(1)

        # ─ Step 2: stream a single offer ─────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 2 — Streaming offer to seller")
        print("=" * 60)
        print("(events arrive as the agent processes — watch the timestamps)\n")

        offer_text = (
            "Final-and-best offer: $445,000 for 742 Evergreen Terrace, "
            "Austin TX 78701. 30-day close, conventional financing pre-approved."
        )

        t0 = time.monotonic()
        event_count = 0
        async for event in stream_a2a_message(http, seller_url, offer_text):
            event_count += 1
            render_event(event, t0)

        total = time.monotonic() - t0
        print(f"\n{'-' * 50}")
        print(f"Total events: {event_count}")
        print(f"Wall-clock:   {total:.2f}s")
        print(f"{'-' * 50}")
        print(
            "\nWith message/send you'd see only the FINAL response after waiting "
            f"~{total:.0f}s. Streaming let you observe every state transition."
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="A2A streaming demo client.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()
    await run_streaming_demo(args.base_url)


if __name__ == "__main__":
    asyncio.run(main())
