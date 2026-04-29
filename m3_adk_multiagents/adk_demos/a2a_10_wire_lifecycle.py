"""
Demo 10 — A2A Wire Format and Task Lifecycle
================================================
Peek under the hood of the A2A protocol. This script:
  1. Fetches the Agent Card (discovery)
  2. Hand-crafts a JSON-RPC `message/send` request (valid envelope)
  3. Sends a broken envelope to show graceful error handling

NO A2A SDK used for the HTTP calls — just raw httpx so you see the
exact wire format. This is what happens at the HTTP level when one
agent talks to another over A2A.

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
    adk web --a2a m3_adk_multiagents/negotiation_agents/ --port 8000

Run:
    python m3_adk_multiagents/adk_demos/a2a_10_wire_lifecycle.py \\
        --seller-url http://127.0.0.1:8000/a2a/seller_agent
"""

import argparse
import asyncio
import json
import uuid

import httpx


def make_jsonrpc_envelope(text: str) -> dict:
    """Build a raw JSON-RPC 2.0 envelope for A2A message/send.

    This is the exact wire format the A2A protocol uses. Every A2A
    request is a JSON-RPC 2.0 call with method "message/send" and
    a Message object in the params.

    The Message contains:
      - messageId: unique ID for deduplication
      - role: "user" (we're the client sending to the agent)
      - parts: array of content chunks (TextPart here)

    Example output:
    {
      "jsonrpc": "2.0",
      "id": "req_5e8c7b2a",
      "method": "message/send",
      "params": {
        "message": {
          "messageId": "msg_7a4516a2",
          "role": "user",
          "parts": [{"kind": "text", "text": "...your offer JSON..."}]
        }
      }
    }
    """
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
        default="http://127.0.0.1:8000/a2a/seller_agent",
    )
    args = parser.parse_args()
    base = args.seller_url.rstrip("/")

    async with httpx.AsyncClient(timeout=60.0) as http:

        # ── Step 1: Discovery — fetch the Agent Card ──────────────────
        #
        # Before sending any messages, a client fetches the Agent Card.
        # This is the A2A equivalent of MCP's tools/list — it tells you:
        #   - What the agent does (name, description, skills)
        #   - Where to send messages (url)
        #   - What features are supported (streaming, push notifications)
        #
        # The card lives at a well-known URL:
        #   GET /<agent>/.well-known/agent-card.json
        #
        # In our workshop, agent.json in the agent folder defines this card.
        # adk web --a2a serves it automatically.
        #
        print("=== 1. AGENT CARD (discovery) ===")
        card_resp = await http.get(f"{base}/.well-known/agent-card.json")
        card = card_resp.json()
        print(json.dumps(card, indent=2))
        print()

        # ── Step 2: Valid envelope — see task lifecycle ────────────────
        #
        # Now we send a real offer to the seller agent.
        #
        # The offer is a JSON string inside a TextPart. The A2A protocol
        # doesn't care about the offer format — it just ferries the text.
        # The AGENT parses the JSON and reasons about it.
        #
        # What happens server-side:
        #   1. adk web receives the JSON-RPC request
        #   2. Creates a Task (status: submitted)
        #   3. Runs the seller LlmAgent (status: working)
        #      - LlmAgent calls MCP tools (get_market_price, get_minimum_acceptable_price)
        #      - LLM produces counter-offer based on tool results
        #   4. Task completes (status: completed)
        #   5. Response includes:
        #      - contextId: reuse this for round 2 (demo 11)
        #      - history: the full message exchange
        #      - artifacts: the counter-offer as a durable output
        #
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

        # Extract the task status from the response.
        # A2A response structure:
        #   {"jsonrpc": "2.0", "result": {"status": {"state": "completed"}, ...}}
        status = (
            (result.get("result") or {})
            .get("status", {})
            .get("state", "?")
        )
        print(f"\nRESPONSE (status={status}):")
        # Truncated to 1500 chars for readability — full response is much longer.
        # Remove [:1500] to see the complete JSON (counter-offer, history, artifacts).
        print(json.dumps(result, indent=2)[:1500])
        print()

        # ── Step 3: Broken envelope — graceful error handling ─────────
        #
        # Send garbage data — no session_id, no price, no real structure.
        # This tests how the agent handles bad input.
        #
        # KEY INSIGHT: The task will still show status "completed" (not "failed")
        # because the A2A PROTOCOL worked correctly — valid JSON-RPC, valid Message.
        # The CONTENT was bad, but the LLM handled it gracefully:
        #   "Could you please resend your offer?"
        #
        # "completed" means the agent processed the request.
        # It does NOT mean the negotiation succeeded.
        # A task only "fails" on protocol errors or server crashes.
        #
        print("=== 3. BROKEN ENVELOPE (expect graceful handling) ===")
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
