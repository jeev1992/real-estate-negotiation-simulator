"""
Demo 14 — Three ways to get results: polling, streaming, push
===============================================================
Each negotiation agent advertises ONE way to receive its results in its
Agent Card, and this script uses the matching A2A mechanism:

  Agent          Card capabilities              How the client gets results
  ─────────────  ─────────────────────────────  ─────────────────────────────────────────
  buyer_agent    streaming: false, push: false  POLLING  — message/send (blocking=false),
                                                            then tasks/get until the task ends
  seller_agent   streaming: true                STREAMING — message/stream: events arrive live
                                                            as the seller calls its tools
  negotiation    pushNotifications: true        PUSH     — message/send with a webhook; the
                                                            server POSTs task updates to us

The ClientConfig decides which one the a2a-sdk Client uses:
  polling   ClientConfig(streaming=False, polling=True)
  streaming ClientConfig(streaming=True)       — used only if the card says streaming: true
  push      ClientConfig(streaming=False, polling=True,
                         push_notification_configs=[PushNotificationConfig(url, token)])

Asking an agent for something its card doesn't offer is an error — see
demo 15 (error handling).

Prereqs (two terminals):
    adk web --a2a m2_adk_multiagents/negotiation_agents/              # buyer + seller on :8000
    python m2_adk_multiagents/a2a_demos/negotiation_a2a_server.py     # negotiation on :8003

Run:
    python m2_adk_multiagents/a2a_demos/a2a_14_result_delivery.py --mode polling
    python m2_adk_multiagents/a2a_demos/a2a_14_result_delivery.py --mode streaming
    python m2_adk_multiagents/a2a_demos/a2a_14_result_delivery.py --mode push        # ~30-60 s
"""

import argparse
import asyncio
import secrets
import time
import uuid

import httpx
import uvicorn
from a2a.client import A2ACardResolver, Client, ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    DataPart,
    Message,
    PushNotificationConfig,
    Role,
    Task,
    TaskArtifactUpdateEvent,
    TaskQueryParams,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

TERMINAL = {TaskState.completed, TaskState.failed, TaskState.canceled, TaskState.rejected}
_t0 = time.monotonic()


def ts() -> str:
    return f"t+{time.monotonic() - _t0:5.1f}s"


def user_message(text: str) -> Message:
    return Message(message_id=f"msg_{uuid.uuid4().hex[:8]}", role=Role.user, parts=[TextPart(text=text)])


def describe_parts(parts) -> str:
    """One-line summary: text, tool calls and tool results (ADK sends the last two as DataParts)."""
    out = []
    for part in parts or []:
        inner = part.root
        if isinstance(inner, TextPart) and inner.text.strip():
            out.append(f'text "{inner.text.strip()[:110]}"')
        elif isinstance(inner, DataPart):
            data = inner.data
            if "args" in data:
                out.append(f"tool_call {data.get('name')}")
            elif "response" in data:
                out.append(f"tool_result {data.get('name')}")
            else:
                out.append("data")
    return ", ".join(out) or "-"


def final_text(task: Task) -> str:
    for artifact in task.artifacts or []:
        for part in artifact.parts:
            if isinstance(part.root, TextPart):
                return part.root.text
    if task.status.message:
        return describe_parts(task.status.message.parts)
    return "(no text)"


async def discover(http: httpx.AsyncClient, base_url: str) -> AgentCard:
    card = await A2ACardResolver(httpx_client=http, base_url=base_url).get_agent_card()
    caps = card.capabilities
    print(f"Agent Card: {card.name} @ {card.url}")
    print(f"  capabilities: streaming={caps.streaming}, pushNotifications={caps.push_notifications}\n")
    return card


async def send_once(client: Client, message: Message) -> Task:
    """Non-streaming send: the Client yields exactly one (Task, None)."""
    async for event in client.send_message(message):
        if isinstance(event, Message):
            raise RuntimeError(f"expected a Task, got a Message: {event!r}")
        return event[0]
    raise RuntimeError("no response")


# ── 1. POLLING (buyer) ────────────────────────────────────────────────────────

async def polling(http: httpx.AsyncClient, buyer_url: str) -> None:
    print("=" * 72, "\nPOLLING — buyer_agent\n" + "=" * 72)
    card = await discover(http, buyer_url)
    # polling=True → message/send with blocking=false: return immediately, don't wait
    client = ClientFactory(ClientConfig(httpx_client=http, streaming=False, polling=True)).create(card)
    task = await send_once(client, user_message(
        "Make your opening offer for 742 Evergreen Terrace, Austin TX 78701 (listed at $485,000)."))
    print(f"{ts()}  message/send (blocking=false) → task {task.id[:8]}  state={task.status.state.value}")
    print(f"           taskId={task.id}\n           contextId={task.context_id}  (the conversation; a new message gets a new taskId)")

    last, polls = task.status.state, 0
    while task.status.state not in TERMINAL:
        await asyncio.sleep(1.0)
        polls += 1
        task = await client.get_task(TaskQueryParams(id=task.id))
        if task.status.state != last:
            print(f"{ts()}  tasks/get #{polls} → state={task.status.state.value}")
            last = task.status.state
    print(f"{ts()}  done after {polls} polls\n  result: {final_text(task)[:300]}\n")


# ── 2. STREAMING (seller) ─────────────────────────────────────────────────────

async def streaming(http: httpx.AsyncClient, seller_url: str) -> None:
    print("=" * 72, "\nSTREAMING — seller_agent\n" + "=" * 72)
    card = await discover(http, seller_url)
    client = ClientFactory(ClientConfig(httpx_client=http, streaming=True)).create(card)
    message = user_message(
        "The buyer offers $440,000 for 742 Evergreen Terrace with a 30-day close. Respond with ACCEPT or COUNTER.")
    # The Client yields (task, update): `task` is the task so far (the SDK
    # merges each update into it); `update` is the event that just arrived.
    async for task, update in client.send_message(message):
        if update is None:
            print(f"{ts()}  task        {task.id[:8]} state={task.status.state.value}")
        elif isinstance(update, TaskStatusUpdateEvent):
            content = describe_parts(update.status.message.parts) if update.status.message else "-"
            print(f"{ts()}  status      state={update.status.state.value:<9} final={update.final!s:<5} {content}")
        elif isinstance(update, TaskArtifactUpdateEvent):
            print(f"{ts()}  artifact    {describe_parts(update.artifact.parts)}")
    print(f"\n  final task: state={task.status.state.value}, artifacts={len(task.artifacts or [])}\n")


# ── 3. PUSH (negotiation) ─────────────────────────────────────────────────────

async def push(http: httpx.AsyncClient, negotiation_url: str, webhook_port: int) -> None:
    print("=" * 72, "\nPUSH — negotiation\n" + "=" * 72)
    token = secrets.token_urlsafe(16)        # shared with the server so we can trust its POSTs
    done = asyncio.Event()
    count = 0

    async def webhook(request: Request) -> JSONResponse:
        nonlocal count
        count += 1
        if request.headers.get("X-A2A-Notification-Token") != token:
            print(f"{ts()}  webhook #{count}: REJECTED (bad notification token)")
            return JSONResponse({"ok": False}, status_code=401)
        task = Task.model_validate(await request.json())
        content = describe_parts(task.status.message.parts) if task.status.message else ""
        print(f"{ts()}  webhook #{count}: state={task.status.state.value:<9} {content[:120]}")
        if task.status.state in TERMINAL:
            print(f"\n  final result: {final_text(task)[:300]}")
            done.set()
        return JSONResponse({"ok": True})

    server = uvicorn.Server(uvicorn.Config(
        Starlette(routes=[Route("/webhook", webhook, methods=["POST"])]),
        host="127.0.0.1", port=webhook_port, log_level="warning",
    ))
    server_task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    webhook_url = f"http://127.0.0.1:{webhook_port}/webhook"
    print(f"Webhook listening on {webhook_url}\n")

    try:
        card = await discover(http, negotiation_url)
        client = ClientFactory(ClientConfig(
            httpx_client=http,
            streaming=False,
            polling=True,                                   # blocking=false
            push_notification_configs=[PushNotificationConfig(url=webhook_url, token=token)],
        )).create(card)
        task = await send_once(client, user_message("Start the negotiation."))
        print(f"{ts()}  message/send (blocking=false, webhook registered) → task {task.id[:8]} "
              f"state={task.status.state.value}")
        print(f"{ts()}  the client is free now — no open connection, no polling. Waiting for POSTs...\n")
        await asyncio.wait_for(done.wait(), timeout=600)
    finally:
        server.should_exit = True
        await server_task
    print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="A2A result delivery: polling, streaming, push.")
    parser.add_argument("--mode", choices=["polling", "streaming", "push", "all"], default="all")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="adk web --a2a (buyer, seller)")
    parser.add_argument("--negotiation-url", default="http://127.0.0.1:8003", help="negotiation_a2a_server.py")
    parser.add_argument("--webhook-port", type=int, default=9010)
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=180.0) as http:
        if args.mode in ("polling", "all"):
            await polling(http, f"{args.base_url}/a2a/buyer_agent")
        if args.mode in ("streaming", "all"):
            await streaming(http, f"{args.base_url}/a2a/seller_agent")
        if args.mode in ("push", "all"):
            await push(http, args.negotiation_url, args.webhook_port)


if __name__ == "__main__":
    asyncio.run(main())
