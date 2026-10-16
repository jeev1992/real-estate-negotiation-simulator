"""
Demo 12 — A2A Parts and Artifacts
====================================
Sends a Message with multiple parts (TextPart + DataPart), then looks at
the three places content lives in the Task that comes back: the history,
the status message, and the artifacts.

WHY MULTI-PART MESSAGES?
  A2A Messages can carry MULTIPLE Parts of different types:

  - TextPart: plain text (what the LLM reads)
  - DataPart: structured JSON (what code parses)
  - FilePart: a file — inline bytes or a URI — with a MIME type

  This demo sends BOTH a TextPart and a DataPart in the same Message —
  the offer in human-readable AND machine-readable form.

WHERE THE ANSWER LIVES IN A TASK:
  history        the conversation: our message, then the agent's turns —
                 including its MCP tool calls and results as DataParts
  status.message the latest status update's message (if any)
  artifacts      DURABLE OUTPUTS — the deliverable, each with an artifactId

  Think of it this way:
    history   = the email thread (conversational, ordered)
    artifacts = the attached report (the deliverable)

  A downstream system reads the artifact; it doesn't have to replay the
  history to find the answer. ADK's A2A server turns the agent's final
  reply into one artifact.

Prereq:
    adk web --a2a m2_adk_multiagents/negotiation_agents/

Run:
    python m2_adk_multiagents/a2a_demos/a2a_12_parts_and_artifacts.py \\
        --seller-url http://127.0.0.1:8000/a2a/seller_agent
"""

import argparse
import asyncio
import json
import uuid

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import DataPart, Message, Part, Role, Task, TextPart


def show_part(index: int, part: Part, indent: str = "    ") -> None:
    inner = part.root
    if isinstance(inner, TextPart):
        print(f"{indent}[{index}] TextPart  {inner.text.strip()[:160]}")
    elif isinstance(inner, DataPart):
        print(f"{indent}[{index}] DataPart  {json.dumps(inner.data)[:160]}")
    else:
        print(f"{indent}[{index}] {inner.kind}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="A2A parts and artifacts demo")
    parser.add_argument("--seller-url", default="http://127.0.0.1:8000/a2a/seller_agent")
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
    #   parts[0] = TextPart  → human-readable text (the LLM reads this)
    #   parts[1] = DataPart  → structured dict (code can parse this directly)
    parts = [
        TextPart(text="Final-and-best offer at $445k for 742 Evergreen Terrace."),
        DataPart(data={"hint": "machine-readable copy of the offer", "offer": buyer_envelope}),
    ]

    async with httpx.AsyncClient(timeout=60.0) as http:
        card = await A2ACardResolver(httpx_client=http, base_url=args.seller_url).get_agent_card()
        client = ClientFactory(ClientConfig(httpx_client=http, streaming=False)).create(card)

        message = Message(message_id=f"msg_{uuid.uuid4().hex[:8]}", role=Role.user, parts=parts)
        task = None
        async for event in client.send_message(message):
            task = event[0] if isinstance(event, tuple) else event

    if not isinstance(task, Task):
        print(f"Expected a Task, got: {task!r}")
        return

    print(f"=== task {task.id}  state={task.status.state.value} ===")

    # ── 1. history — the conversation ─────────────────────────────────
    print(f"\n=== 1. history ({len(task.history or [])} messages) ===")
    for i, msg in enumerate(task.history or []):
        print(f"  ({i}) role={msg.role.value}, {len(msg.parts)} part(s):")
        for j, part in enumerate(msg.parts):
            show_part(j, part)

    # ── 2. status.message ─────────────────────────────────────────────
    print("\n=== 2. status.message ===")
    if task.status.message:
        for j, part in enumerate(task.status.message.parts):
            show_part(j, part, indent="  ")
    else:
        print("  (none — the final 'completed' update carries no message; the reply is in the artifact)")

    # ── 3. artifacts — the deliverable ────────────────────────────────
    print(f"\n=== 3. artifacts ({len(task.artifacts or [])}) ===")
    for artifact in task.artifacts or []:
        print(f"  artifactId={artifact.artifact_id}  name={artifact.name}")
        for j, part in enumerate(artifact.parts):
            show_part(j, part)

    # ── Structured observability: read tool calls from DataParts ──────
    #
    # ADK records each MCP tool call/result as a DataPart in history, so
    # code can see exactly which tools ran — no text parsing needed.
    print("\n=== tools the seller called (from history DataParts) ===")
    for msg in task.history or []:
        for part in msg.parts:
            data = part.root.data if isinstance(part.root, DataPart) else {}
            if "args" in data:
                print(f"  call   {data['name']}({json.dumps(data['args'])[:100]})")
            elif "response" in data:
                print(f"  result {data['name']} → {json.dumps(data['response'])[:100]}")

    print("\n=== key takeaways ===")
    print("• Messages carry Parts: TextPart (text), DataPart (structured), FilePart (files)")
    print("• history = the conversation (incl. tool calls as DataParts); artifacts = the deliverable")
    print("• Read the answer from the artifact; read the audit trail from history")


if __name__ == "__main__":
    asyncio.run(main())
