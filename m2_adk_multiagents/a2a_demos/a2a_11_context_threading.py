"""
Demo 11 — A2A Context Threading (and Task vs Context)
=======================================================
A2A uses `contextId` to thread multiple messages into one conversation.
This script sends 3 negotiation rounds to the seller, reusing the
contextId from round 1 so all rounds are recognized as one negotiation.
Then it sends a BONUS round 4 WITHOUT contextId to prove what happens
when the seller has no memory of prior rounds.

TASK vs CONTEXT:
  Every message/send creates a NEW Task (new taskId) — one unit of work.
  The contextId is the conversation those tasks belong to.

    round 1  taskId=A  contextId=X   ← server assigns X
    round 2  taskId=B  contextId=X   ← we pass X back
    round 3  taskId=C  contextId=X
    round 4  taskId=D  contextId=Y   ← no contextId sent → new conversation

  After round 3 the script calls tasks/get on round 1's taskId: that task
  is still there, finished, with its own artifact. Tasks are records; the
  context is the thread that links them.

WHY CONTEXT THREADING MATTERS:
  Without contextId, each POST to the seller starts a BRAND NEW conversation
  and the seller forgets all prior offers.

  With contextId, the seller remembers (prices vary run to run):
    Round 1: $432K → below the $445K floor → COUNTER (e.g. $477K)
    Round 2: $440K → still below → COUNTER
    Round 3: $446K → above the floor → ACCEPT

  Bonus round (no contextId):
    Round 4: $440K → COUNTER as if it were round 1.
    Same price as round 2, but no memory — seller treats it as brand new.

  contextId is A2A's equivalent of ADK's session_id — same concept
  (conversation continuity), different level (HTTP vs in-process).

Prereq:
    adk web --a2a m2_adk_multiagents/negotiation_agents/

Run:
    python m2_adk_multiagents/a2a_demos/a2a_11_context_threading.py \\
        --seller-url http://127.0.0.1:8000/a2a/seller_agent
"""

import argparse
import asyncio
import sys
import uuid

import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, ClientFactory
from a2a.client.errors import A2AClientHTTPError
from a2a.types import DataPart, Message, Role, Task, TaskQueryParams, TextPart


def buyer_offer_parts(round_num: int, price: int) -> list:
    """[TextPart, DataPart] — text for the LLM plus the same offer as structured data."""
    return [
        TextPart(text=f"Round {round_num} offer at ${price:,}."),
        DataPart(data={
            "round": round_num,
            "from_agent": "buyer",
            "to_agent": "seller",
            "message_type": "OFFER",
            "price": price,
        }),
    ]


def artifact_text(task: Task) -> str:
    """The seller's reply, read from the task's artifact (its durable output)."""
    for artifact in task.artifacts or []:
        for part in artifact.parts:
            if isinstance(part.root, TextPart):
                return part.root.text
    return "(no artifact)"


async def send(client: Client, parts: list, context_id: str | None) -> Task:
    message = Message(
        message_id=f"msg_{uuid.uuid4().hex[:8]}",
        role=Role.user,
        parts=parts,
        context_id=context_id,      # None → the server starts a new conversation
    )
    task = None
    async for event in client.send_message(message):
        task = event[0] if isinstance(event, tuple) else event
    if not isinstance(task, Task):
        raise RuntimeError(f"expected a Task, got {task!r}")
    return task


def tools_called(task: Task) -> list[str]:
    """MCP/function tools the agent called in THIS task — ADK puts them in history as DataParts."""
    return [
        p.root.data.get("name", "?")
        for m in task.history or [] for p in m.parts
        if isinstance(p.root, DataPart) and "args" in p.root.data
    ]


def show(label: str, task: Task) -> None:
    print(f"\n=== {label} ===")
    print(f"  taskId    {task.id}")
    print(f"  contextId {task.context_id}")
    print(f"  state     {task.status.state.value}")
    print(f"  tools     {', '.join(tools_called(task)) or '(none)'}")
    print(f"  seller    {artifact_text(task)[:300]}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="A2A context threading across multiple turns")
    parser.add_argument("--seller-url", default="http://127.0.0.1:8000/a2a/seller_agent")
    args = parser.parse_args()

    # contextId starts as None. Round 1 gets it from the server response.
    # Rounds 2-3 reuse it so the seller sees the full conversation history.
    context_id: str | None = None
    task_ids: list[str] = []

    async with httpx.AsyncClient(timeout=90.0) as http:

        # ── Step 1: Discover the seller agent via Agent Card ──────────
        card = await A2ACardResolver(httpx_client=http, base_url=args.seller_url).get_agent_card()
        client = ClientFactory(ClientConfig(httpx_client=http, streaming=False)).create(card)

        # ── Step 2: Send 3 rounds with increasing prices ──────────────
        # $432K → $440K → $446K
        # The $446K offer is above the seller's $445K floor, so it should
        # be accepted — but ONLY if the seller remembers the floor from
        # the MCP tool call in round 1.
        for round_num, price in enumerate([432_000, 440_000, 446_000], start=1):
            task = await send(client, buyer_offer_parts(round_num, price), context_id)
            # The server assigns a contextId when it sees None. We save it
            # and pass it on rounds 2-3 so they join the same conversation.
            if context_id is None:
                context_id = task.context_id
            task_ids.append(task.id)
            show(f"round {round_num} — ${price:,} (sent contextId={'none' if round_num == 1 else 'X'})", task)

        # ── Step 3: Tasks are separate records — fetch round 1's task ─
        #
        # tasks/get returns a task by id at any time. Round 1's task is
        # finished: same state and artifact as when it completed, even
        # though the conversation has moved on.
        #
        round1 = await client.get_task(TaskQueryParams(id=task_ids[0]))
        show("tasks/get on round 1's taskId", round1)
        print(f"\n  3 rounds → 3 different taskIds, 1 contextId:")
        for i, task_id in enumerate(task_ids, start=1):
            print(f"    round {i}: taskId={task_id}")

        # ── Step 4: Bonus round — same price, NO contextId ────────────
        #
        # Send $440K again — the same price as round 2. But this time,
        # do NOT include contextId. The server treats this as a brand-new
        # conversation with zero history: the seller calls its MCP tools
        # fresh and counters as if this were round 1.
        #
        bonus = await send(client, buyer_offer_parts(4, 440_000), context_id=None)
        show("round 4 — $440,000, NO contextId", bonus)
        print(f"\n  contextId {context_id} → {bonus.context_id}: a new conversation.")
        print("  Same $440K as round 2, but the seller has no memory of rounds 1-3.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # so the output can be piped/redirected on Windows
    try:
        asyncio.run(main())
    except A2AClientHTTPError as e:
        if e.status_code != 503:   # 503 = the SDK's code for "nothing answered" (network error)
            raise
        sys.exit(f"Can't reach the agent: {e.message}\n"
                 "Start the agents first:  adk web --a2a m2_adk_multiagents/negotiation_agents/")
