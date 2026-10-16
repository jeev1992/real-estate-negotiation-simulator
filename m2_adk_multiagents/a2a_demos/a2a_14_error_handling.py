"""
Demo 14 — A2A Error Handling
===============================
Things go wrong at four different layers in A2A, and each one shows up
differently in your client code. This script triggers each one against the
real agents and shows how to detect and handle it.

  Layer            How it shows up                         Example here
  ───────────────  ──────────────────────────────────────  ─────────────────────────────────
  1. Transport     an exception: A2AClientHTTPError,       agent not running, wrong path,
                   A2AClientTimeoutError                   request timed out
  2. Protocol      an exception: A2AClientJSONRPCError     task not found, can't cancel,
                   carrying a JSON-RPC error code           capability not offered, bad request
  3. Task          NO exception — the Task comes back       a file type the model can't read
                   with state "failed" and the reason
                   in status.message
  4. Application   NO exception, state "completed" — but    an "offer" with no price in it
                   the agent couldn't do what you asked

Layers 3 and 4 are the ones people miss: the call "succeeds", so you have
to look at task.status.state — and then at the content.

Prereq:
    adk web --a2a m2_adk_multiagents/negotiation_agents/

Run:
    python m2_adk_multiagents/a2a_demos/a2a_14_error_handling.py
"""

import argparse
import asyncio
import base64
import sys
import uuid
from collections.abc import Awaitable, Callable

import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, ClientFactory
from a2a.client.errors import (
    A2AClientHTTPError,
    A2AClientJSONRPCError,
    A2AClientTimeoutError,
)
from a2a.types import (
    AgentCard,
    DataPart,
    FilePart,
    FileWithBytes,
    Message,
    PushNotificationConfig,
    Role,
    Task,
    TaskIdParams,
    TaskPushNotificationConfig,
    TaskQueryParams,
    TaskState,
    TextPart,
)

TERMINAL = {TaskState.completed, TaskState.failed, TaskState.canceled, TaskState.rejected}


def header(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def message(*parts) -> Message:
    return Message(message_id=f"msg_{uuid.uuid4().hex[:8]}", role=Role.user, parts=list(parts))


def first_text(parts) -> str:
    for part in parts or []:
        if isinstance(part.root, TextPart):
            return part.root.text
    return ""


async def send_once(client: Client, msg: Message) -> Task:
    async for event in client.send_message(msg):
        if isinstance(event, Message):
            raise RuntimeError(f"expected a Task, got a Message: {event!r}")
        return event[0]
    raise RuntimeError("no response")


async def poll(client: Client, task: Task) -> Task:
    while task.status.state not in TERMINAL:
        await asyncio.sleep(1.0)
        task = await client.get_task(TaskQueryParams(id=task.id))
    return task


async def expect_error(label: str, call: Callable[[], Awaitable[object]]) -> None:
    """Run one call that should fail, and show how the failure arrives."""
    print(f"\n▶ {label}")
    try:
        result = await call()
        print(f"  no exception — got {result!r}"[:300])
    except A2AClientJSONRPCError as e:
        print(f"  A2AClientJSONRPCError  code={e.error.code}  message={e.error.message!r}")
    except A2AClientTimeoutError as e:
        print(f"  A2AClientTimeoutError  {e.message}")
    except A2AClientHTTPError as e:
        print(f"  A2AClientHTTPError  status={e.status_code}  {e.message[:140]}")


# ── Layer 1: transport ───────────────────────────────────────────────────────

async def get_card_with_retry(http: httpx.AsyncClient, url: str, attempts: int = 3) -> AgentCard:
    """Retry transient failures (connection refused, 5xx) with backoff; fail fast on 4xx."""
    for attempt in range(1, attempts + 1):
        try:
            return await A2ACardResolver(httpx_client=http, base_url=url).get_agent_card()
        except A2AClientHTTPError as e:
            if e.status_code < 500 or attempt == attempts:
                raise
            delay = 0.5 * 2 ** (attempt - 1)
            print(f"  attempt {attempt}: HTTP {e.status_code} (transient) — retrying in {delay}s")
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


async def layer1_transport(http: httpx.AsyncClient, base_url: str, seller: AgentCard) -> Task:
    header("LAYER 1 — TRANSPORT (exceptions: A2AClientHTTPError, A2AClientTimeoutError)")

    # Nothing listening on that port. The resolver reports it as HTTP 503.
    # Transient → retry with backoff, then give up.
    await expect_error("Agent Card from a port with nothing running (retry 3x, then give up)",
                       lambda: get_card_with_retry(http, "http://127.0.0.1:8099/a2a/seller_agent"))

    # Server is up but there is no such agent → 404. Retrying won't help.
    await expect_error("Agent Card for an agent that doesn't exist (404 — fail fast)",
                       lambda: get_card_with_retry(http, f"{base_url}/a2a/no_such_agent"))

    # A blocking message/send has to wait for the whole LLM + MCP run.
    # With a 2-second read timeout the client gives up first.
    offer = message(TextPart(text="The buyer offers $440,000 for 742 Evergreen Terrace. ACCEPT or COUNTER?"))

    async def blocking_send_2s() -> Task:
        async with httpx.AsyncClient(timeout=2.0) as short:
            client = ClientFactory(ClientConfig(httpx_client=short, streaming=False)).create(seller)
            return await send_once(client, offer)

    await expect_error("Blocking message/send with a 2s timeout", blocking_send_2s)
    print("  ⚠ The server never heard that we gave up — the seller may still be working on it.")
    print("    We have no taskId, so we can't check. Resending could repeat the work.")

    # Recovery: send non-blocking. We get the taskId back at once, then poll —
    # each tasks/get is a short request, so the 2s timeout no longer matters.
    print("\n▶ Recovery: message/send with blocking=false, then poll tasks/get")
    async with httpx.AsyncClient(timeout=2.0) as short:
        client = ClientFactory(ClientConfig(httpx_client=short, streaming=False, polling=True)).create(seller)
        task = await send_once(client, message(TextPart(text="The buyer offers $440,000 for 742 Evergreen Terrace. ACCEPT or COUNTER?")))
        print(f"  task {task.id[:8]} {task.status.state.value} — returned immediately")
        task = await poll(client, task)
    print(f"  task {task.id[:8]} {task.status.state.value}: {first_text(task.artifacts[0].parts if task.artifacts else [])[:120]}")
    return task


# ── Layer 2: protocol (JSON-RPC errors) ──────────────────────────────────────

async def layer2_protocol(http: httpx.AsyncClient, buyer: AgentCard, seller: AgentCard, done_task: Task) -> None:
    header("LAYER 2 — PROTOCOL (exception: A2AClientJSONRPCError with a JSON-RPC error code)")
    seller_client = ClientFactory(ClientConfig(httpx_client=http, streaming=False)).create(seller)
    buyer_client = ClientFactory(ClientConfig(httpx_client=http, streaming=False, polling=True)).create(buyer)

    await expect_error("tasks/get with a taskId the server doesn't know",
                       lambda: seller_client.get_task(TaskQueryParams(id="no-such-task")))

    await expect_error(f"tasks/cancel on task {done_task.id[:8]}, which already completed",
                       lambda: seller_client.cancel_task(TaskIdParams(id=done_task.id)))

    # A task that is still running. ADK's A2A executor doesn't implement cancel.
    running = await send_once(buyer_client, message(TextPart(text="Make your opening offer for 742 Evergreen Terrace.")))
    await expect_error(f"tasks/cancel on task {running.id[:8]}, still {running.status.state.value}",
                       lambda: buyer_client.cancel_task(TaskIdParams(id=running.id)))
    await poll(buyer_client, running)       # let it finish

    # Capabilities the card doesn't offer. The buyer's card says
    # pushNotifications: false — the server refuses to store a webhook.
    # (The spec has dedicated codes for this: -32003 PushNotificationNotSupported,
    # -32004 UnsupportedOperation. a2a-sdk 0.3.26's server sends -32603.)
    await expect_error("tasks/pushNotificationConfig/set on buyer_agent (pushNotifications: false)",
                       lambda: buyer_client.set_task_callback(TaskPushNotificationConfig(
                           task_id=running.id,
                           push_notification_config=PushNotificationConfig(url="http://127.0.0.1:9/hook"),
                       )))

    # The Client won't send message/stream to an agent whose card says
    # streaming: false (it falls back to message/send), and won't build a
    # malformed request. So for these we POST raw JSON-RPC — what a buggy or
    # non-SDK client might send.
    async def raw(body: dict) -> str:
        response = await http.post(buyer.url, json=body)
        return f"HTTP {response.status_code}  {response.text[:240]}"

    for label, body in [
        ("raw message/stream to buyer_agent (streaming: false)",
         {"jsonrpc": "2.0", "id": "1", "method": "message/stream",
          "params": {"message": {"messageId": "m1", "role": "user", "parts": [{"kind": "text", "text": "hi"}]}}}),
        ("raw request with an unknown method",
         {"jsonrpc": "2.0", "id": "2", "method": "tasks/explode", "params": {}}),
        ("raw message/send missing messageId and parts",
         {"jsonrpc": "2.0", "id": "3", "method": "message/send", "params": {"message": {"role": "user"}}}),
    ]:
        print(f"\n▶ {label}")
        print(f"  {await raw(body)}")


# ── Layer 3: task failed ─────────────────────────────────────────────────────

async def layer3_task_failed(http: httpx.AsyncClient, buyer: AgentCard) -> None:
    header("LAYER 3 — TASK FAILED (no exception: check task.status.state)")
    client = ClientFactory(ClientConfig(httpx_client=http, streaming=False)).create(buyer)
    # A FilePart is valid A2A — but this agent's model can't read a zip file.
    attachment = FilePart(file=FileWithBytes(
        bytes=base64.b64encode(b"PK\x03\x04 not really a zip").decode(),
        mime_type="application/zip",
        name="offer_documents.zip",
    ))
    print("\n▶ message/send with a TextPart + a FilePart (application/zip)")
    task = await send_once(client, message(TextPart(text="Offer documents attached."), attachment))
    print(f"  no exception. task {task.id[:8]} state={task.status.state.value}")
    if task.status.state == TaskState.failed:
        reason = first_text(task.status.message.parts if task.status.message else [])
        print(f"  reason (status.message): {reason}")
        print("  → don't retry as-is: the same input will fail the same way.")


# ── Layer 4: application ─────────────────────────────────────────────────────

async def layer4_application(http: httpx.AsyncClient, seller: AgentCard) -> None:
    header("LAYER 4 — APPLICATION (no exception, state=completed — check the content)")
    client = ClientFactory(ClientConfig(httpx_client=http, streaming=False)).create(seller)
    print("\n▶ message/send with no price in it")
    task = await send_once(client, message(TextPart(text="broken message with no real offer")))
    print(f"  no exception. task {task.id[:8]} state={task.status.state.value}")
    print(f"  seller: {first_text(task.artifacts[0].parts if task.artifacts else [])[:200]}")
    # The seller records every real decision with its submit_decision tool,
    # and ADK puts tool calls in history as DataParts — so code can check.
    decisions = [
        p.root.data["args"] for m in task.history or [] for p in m.parts
        if isinstance(p.root, DataPart) and p.root.data.get("name") == "submit_decision" and "args" in p.root.data
    ]
    if decisions:
        print(f"  submit_decision was called: {decisions[-1]}")
    else:
        print("  submit_decision was NOT called → completed, but no decision. Treat as 'ask again'.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="A2A error handling at four layers")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="adk web --a2a")
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=120.0) as http:
        buyer = await get_card_with_retry(http, f"{args.base_url}/a2a/buyer_agent")
        seller = await get_card_with_retry(http, f"{args.base_url}/a2a/seller_agent")

        done_task = await layer1_transport(http, args.base_url, seller)
        await layer2_protocol(http, buyer, seller, done_task)
        await layer3_task_failed(http, buyer)
        await layer4_application(http, seller)

    header("SUMMARY")
    print("  Layer        Detect with                        Retry?")
    print("  Transport    A2AClientHTTPError / TimeoutError   connection, 5xx: yes, with backoff")
    print("                                                   timeout: the work may still run — prefer")
    print("                                                   blocking=false + tasks/get over resending")
    print("                                                   4xx: no — fix the URL or request")
    print("  Protocol     A2AClientJSONRPCError .error.code   no — fix the request, or use what the card offers")
    print("  Task         task.status.state == failed         not with the same input; read status.message")
    print("  Application  completed, but check the content    ask again / escalate")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # so the output can be piped/redirected on Windows
    try:
        asyncio.run(main())
    except A2AClientHTTPError as e:
        if e.status_code != 503:   # 503 = the SDK's code for "nothing answered" (network error)
            raise
        sys.exit(f"Can't reach the agent: {e.message}\n"
                 "Start the agents first:  adk web --a2a m2_adk_multiagents/negotiation_agents/")
