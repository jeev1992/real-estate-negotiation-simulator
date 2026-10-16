"""
Demo 10 — A2A Wire Format and the Task
=========================================
Peek under the hood of the A2A protocol. This script:
  1. Fetches the seller's Agent Card (discovery)
  2. Sends one offer with message/send and prints the ACTUAL HTTP bytes
     going out and coming back (via httpx event hooks — nothing re-built)
  3. Takes the returned Task apart: id, contextId, status, history, artifacts

WHAT IS A2A?
  A2A (Agent-to-Agent) is an open protocol for agents to discover and
  communicate with each other over HTTP. Think of it as MCP but for
  agents instead of tools:
    - MCP:  agent discovers TOOLS  → tools/list, tools/call
    - A2A:  agent discovers AGENTS → Agent Card, message/send

KEY A2A OBJECTS:
  Task     — unit of work (like a support ticket). Has an id and a lifecycle:
               submitted → working → completed / failed / canceled / rejected
  Message  — one turn in the conversation (role: user or agent)
  Part     — atomic content: TextPart, DataPart, or FilePart
  Artifact — the task's durable output (the deliverable)
  contextId — ties multiple Tasks into one conversation thread

CLIENT API:
  ClientFactory + ClientConfig → Client (a2a-sdk's current client; the older
  A2AClient class is deprecated). The factory reads the Agent Card and picks
  the transport the agent declares (JSON-RPC here).

Prereq:
    adk web --a2a m2_adk_multiagents/negotiation_agents/

Run:
    python m2_adk_multiagents/a2a_demos/a2a_10_wire_lifecycle.py \\
        --seller-url http://127.0.0.1:8000/a2a/seller_agent
"""

import argparse
import asyncio
import json
import sys
import uuid

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.client.errors import A2AClientHTTPError
from a2a.types import DataPart, Message, Role, Task, TextPart

MAX_BODY_CHARS = 2500


def pretty(body: str) -> str:
    try:
        text = json.dumps(json.loads(body), indent=2)
    except ValueError:
        text = body
    if len(text) > MAX_BODY_CHARS:
        text = text[:MAX_BODY_CHARS] + f"\n... ({len(text) - MAX_BODY_CHARS} more chars)"
    return text


# ── httpx event hooks: print every request/response exactly as sent ──────────

async def log_request(request: httpx.Request) -> None:
    print(f"──► {request.method} {request.url}")
    if request.content:
        print(pretty(request.content.decode()))


async def log_response(response: httpx.Response) -> None:
    await response.aread()
    print(f"◄── HTTP {response.status_code}  {response.headers.get('content-type')}")
    print(pretty(response.text))
    print()


def describe_part(part) -> str:
    inner = part.root
    if isinstance(inner, TextPart):
        return f'text "{inner.text.strip()[:90]}"'
    if isinstance(inner, DataPart):
        data = inner.data
        if "args" in data:                     # ADK sends tool calls as DataParts
            return f"data (tool_call {data.get('name')})"
        if "response" in data:
            return f"data (tool_result {data.get('name')})"
        return f"data keys={list(data)}"
    return inner.kind


def print_task_anatomy(task: Task) -> None:
    print("=== 3. THE TASK, TAKEN APART ===")
    print(f"  id          {task.id}        ← this unit of work (tasks/get uses it)")
    print(f"  contextId   {task.context_id}        ← the conversation it belongs to")
    print(f"  status      {task.status.state.value}  at {task.status.timestamp}")
    print(f"  history     {len(task.history or [])} message(s) — the conversation so far:")
    for i, message in enumerate(task.history or []):
        parts = ", ".join(describe_part(p) for p in message.parts)
        print(f"    [{i}] {message.role.value:<5} {parts}")
    print(f"  artifacts   {len(task.artifacts or [])} — the deliverable:")
    for artifact in task.artifacts or []:
        parts = ", ".join(describe_part(p) for p in artifact.parts)
        print(f"    artifactId={artifact.artifact_id}  {parts}")
    print()
    print("  Note: message/send blocked until the task finished, so we only see the")
    print("  final state. Demo 13 polls and streams, so you see submitted → working → completed.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="A2A wire format + the Task object")
    parser.add_argument("--seller-url", default="http://127.0.0.1:8000/a2a/seller_agent")
    args = parser.parse_args()

    async with httpx.AsyncClient(
        timeout=60.0,
        event_hooks={"request": [log_request], "response": [log_response]},
    ) as http:

        # ── Step 1: Discovery — fetch the Agent Card ──────────────────
        #
        # Before sending any messages, a client fetches the Agent Card.
        # This is the A2A equivalent of MCP's tools/list — it tells you:
        #   - What the agent does (name, description, skills)
        #   - Where to send messages (url) and over which transport
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
        card = await A2ACardResolver(httpx_client=http, base_url=args.seller_url).get_agent_card()

        # streaming=False: ask for plain message/send so the whole answer comes
        # back as ONE JSON body you can read. (The seller's card does allow
        # streaming — demo 13 uses it.)
        client = ClientFactory(ClientConfig(httpx_client=http, streaming=False)).create(card)

        # ── Step 2: message/send — the JSON-RPC frames on the wire ────
        #
        # A TextPart for the LLM plus a DataPart with the same offer as
        # structured data. The SDK wraps it in a JSON-RPC 2.0 envelope.
        #
        # What happens server-side:
        #   1. adk web receives the JSON-RPC request and creates a Task
        #   2. Runs the seller LlmAgent (task is "working")
        #      - LlmAgent calls MCP tools (get_market_price, etc.)
        #      - LLM produces a counter-offer based on tool results
        #   3. Task completes; the reply is attached as an Artifact
        #
        print("=== 2. message/send ON THE WIRE ===")
        offer = {
            "round": 1,
            "from_agent": "buyer",
            "to_agent": "seller",
            "message_type": "OFFER",
            "price": 440_000,
            "conditions": ["inspection contingency"],
            "closing_timeline_days": 30,
        }
        message = Message(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            role=Role.user,
            parts=[
                TextPart(text="Opening offer at $440k, 30-day close, pre-approved."),
                DataPart(data=offer),
            ],
        )

        task = None
        async for event in client.send_message(message):
            # Non-streaming: exactly one event — (Task, None), or a Message
            # if the agent answered without creating a task.
            task = event[0] if isinstance(event, tuple) else event

    if isinstance(task, Task):
        print_task_anatomy(task)
    else:
        print(f"Agent replied with a Message, not a Task: {task}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # so the output can be piped/redirected on Windows
    try:
        asyncio.run(main())
    except A2AClientHTTPError as e:
        if e.status_code != 503:   # 503 = the SDK's code for "nothing answered" (network error)
            raise
        sys.exit(f"Can't reach the agent: {e.message}\n"
                 "Start the agents first:  adk web --a2a m2_adk_multiagents/negotiation_agents/")
