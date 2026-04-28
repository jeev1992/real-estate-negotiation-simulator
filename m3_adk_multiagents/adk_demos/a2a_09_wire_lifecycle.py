"""
Demo 09 — A2A Wire Format and Task Lifecycle
================================================
Peek under the hood of the A2A protocol.  This script:
  1. Fetches the Agent Card (discovery)
  2. Hand-crafts a JSON-RPC `message/send` request (valid envelope)
  3. Prints the Task object and its state  (submitted → working → completed)
  4. Sends a broken envelope and shows the failure path

No SDK helpers for step 2 — you see the exact wire shape.

Prereq:
    adk web --a2a m3_adk_multiagents/negotiation_agents/ --port 8000

Run:
    python m3_adk_multiagents/adk_demos/a2a_09_wire_lifecycle.py \\
        --seller-url http://127.0.0.1:8000/seller_agent
"""

import argparse
import asyncio
import json
import uuid

import httpx


def make_jsonrpc_envelope(text: str) -> dict:
    """Build a raw JSON-RPC 2.0 envelope for message/send."""
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
    parser = argparse.ArgumentParser(
        description="A2A wire format + task lifecycle demo"
    )
    parser.add_argument(
        "--seller-url",
        default="http://127.0.0.1:8000/seller_agent",
    )
    args = parser.parse_args()
    base = args.seller_url.rstrip("/")

    async with httpx.AsyncClient(timeout=60.0) as http:
        # ── Step 1: Discovery — fetch the Agent Card ──────────────────
        print("=== 1. AGENT CARD (discovery) ===")
        card_resp = await http.get(f"{base}/.well-known/agent-card.json")
        card = card_resp.json()
        print(json.dumps(card, indent=2))
        print()

        # ── Step 2: Valid envelope — see task lifecycle ────────────────
        print("=== 2. VALID ENVELOPE ===")
        valid_text = json.dumps({
            "session_id": f"demo-{uuid.uuid4().hex[:6]}",
            "round": 1,
            "from_agent": "buyer",
            "to_agent": "seller",
            "message_type": "OFFER",
            "price": 440_000,
            "message": "Opening offer at $440k, 30-day close, pre-approved.",
            "conditions": ["inspection contingency"],
            "closing_timeline_days": 30,
        })
        body = make_jsonrpc_envelope(valid_text)
        print("REQUEST:")
        print(json.dumps(body, indent=2))

        resp = await http.post(base, json=body)
        result = resp.json()
        status = (
            (result.get("result") or {})
            .get("status", {})
            .get("state", "?")
        )
        print(f"\nRESPONSE (status={status}):")
        print(json.dumps(result, indent=2)[:1500])
        print()

        # ── Step 3: Broken envelope — see failure path ────────────────
        print("=== 3. BROKEN ENVELOPE (expect failure) ===")
        broken_text = json.dumps({"from_agent": "buyer", "message": "broken"})
        body = make_jsonrpc_envelope(broken_text)

        resp = await http.post(base, json=body)
        result = resp.json()
        status = (
            (result.get("result") or {})
            .get("status", {})
            .get("state", "?")
        )
        print(f"RESPONSE (status={status}):")
        print(json.dumps(result, indent=2)[:1500])


if __name__ == "__main__":
    asyncio.run(main())
