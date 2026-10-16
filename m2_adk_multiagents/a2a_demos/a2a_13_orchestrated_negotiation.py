"""
Demo 13 — A2A Orchestrated Negotiation
=========================================
Full multi-round buyer ↔ seller negotiation where BOTH agents are
discovered via Agent Cards and communicate through A2A messages.

THIS IS THE PAYOFF DEMO. It shows:
  1. Agent Card discovery for buyer, seller and the negotiation agent
  2. The client reading each card's capabilities and getting results the
     way that agent supports — one of A2A's three mechanisms each:
       buyer_agent   streaming: false        → POLLING: message/send (non-blocking) + tasks/get
       seller_agent  streaming: true         → STREAMING: message/stream (live events)
       negotiation   pushNotifications: true → PUSH: the server POSTs updates to our webhook
  3. Multi-round negotiation: buyer offers → script relays to seller → seller responds
  4. contextId threads each side's conversation independently; every
     round is a new Task, and the agent's reply is read from its Artifact
  5. The script acts as a "matchmaker" — neither agent knows about the other
  6. Then the same negotiation run by ONE agent (negotiation: LoopAgent over
     buyer + seller) — a long job, so we don't wait on it: we register a
     webhook and get every task update pushed to us

HOW IT WORKS:
  The script is NOT an agent itself — it's a simple orchestrator that:
  - Discovers buyer_agent and seller_agent via their Agent Cards
  - Asks the buyer to make an offer (polling: send, then tasks/get until done)
  - Forwards the buyer's offer to the seller (streaming: tool calls arrive live)
  - Reads the seller's response (ACCEPT or COUNTER)
  - If COUNTER: sends the counter back to the buyer for next round
  - Repeats until ACCEPT, WALK AWAY, a failed task, or max rounds

  Each agent has its own contextId — the buyer's conversation thread
  and the seller's conversation thread are separate. The script bridges
  them by extracting text from one response and sending it to the other.

WHAT LEARNERS SEE:
  - Agent Card fetches, with the capability each one advertises
  - Buyer turns: task submitted → polled → completed
  - Seller turns: the seller's MCP tool calls streamed as they happen
  - Agreement, walk-away, or max rounds reached
  - Step 3: one message/send that returns at once, then webhook POSTs —
    one per task update — until the negotiation agent finishes

Prereqs (two terminals):
    adk web --a2a m2_adk_multiagents/negotiation_agents/              # buyer + seller on :8000
    python m2_adk_multiagents/a2a_demos/negotiation_a2a_server.py     # negotiation on :8003
  (ADK's built-in A2A server stores push settings but never sends them, so
  the negotiation agent runs on its own server that does. Without it, step 3
  is skipped.)

Run:
    python m2_adk_multiagents/a2a_demos/a2a_13_orchestrated_negotiation.py
"""

import argparse
import asyncio
import re
import secrets
import uuid

import httpx
import uvicorn
from a2a.client import A2ACardResolver, Client, ClientConfig, ClientFactory
from a2a.client.errors import A2AClientHTTPError
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

BASE_URL = "http://127.0.0.1:8000"
NEGOTIATION_URL = "http://127.0.0.1:8003"
WEBHOOK_PORT = 9010
MAX_ROUNDS = 5
TERMINAL = {TaskState.completed, TaskState.failed, TaskState.canceled, TaskState.rejected}


def extract_agent_text(task: Task) -> str:
    """Extract the agent's text response from an A2A Task."""
    # Artifacts first — the task's durable output
    for artifact in task.artifacts or []:
        for part in artifact.parts:
            if isinstance(part.root, TextPart):
                return part.root.text
    # A failed task explains itself in status.message
    status_message = task.status.message if task.status else None
    if status_message and status_message.role == Role.agent:
        for part in status_message.parts:
            if isinstance(part.root, TextPart):
                return part.root.text
    # Fall back to last agent message in history
    for msg in reversed(task.history or []):
        if msg.role == Role.agent:
            for part in msg.parts:
                if isinstance(part.root, TextPart):
                    return part.root.text
    return "(no response)"


def extract_price(text: str) -> str | None:
    """Best-effort extraction of a dollar amount from an agent message."""
    match = re.search(r"\$\s?([\d,]{4,})", text)
    return f"${match.group(1)}" if match else None


def tool_calls(message: Message | None) -> list[str]:
    """Names of the tools called in a status message (ADK sends tool calls as DataParts)."""
    if not message:
        return []
    return [
        p.root.data.get("name", "?")
        for p in message.parts
        if isinstance(p.root, DataPart) and "args" in p.root.data
    ]


# ── Talk to each agent the way its card says it supports ─────────────────────

def client_for(http: httpx.AsyncClient, card: AgentCard) -> Client:
    if card.capabilities.streaming:
        config = ClientConfig(httpx_client=http, streaming=True)
    else:
        # polling=True → message/send with blocking=false: the task comes back
        # at once (state "submitted") and we poll tasks/get until it ends.
        config = ClientConfig(httpx_client=http, streaming=False, polling=True)
    return ClientFactory(config).create(card)


async def ask(client: Client, agent_name: str, text: str, context_id: str | None) -> Task:
    """Send one message; follow the task to a final state (stream or poll)."""
    message = Message(
        message_id=f"msg_{uuid.uuid4().hex[:8]}",
        role=Role.user,
        parts=[TextPart(text=text)],
        context_id=context_id,
    )
    task = None
    async for event in client.send_message(message):
        if isinstance(event, Message):
            raise RuntimeError(f"{agent_name} replied with a Message, expected a Task: {event!r}")
        task, update = event
        # Streaming: events arrive while the agent works
        if isinstance(update, TaskStatusUpdateEvent) and tool_calls(update.status.message):
            print(f"    [{agent_name} ⇢ stream] {update.status.state.value}: calling {', '.join(tool_calls(update.status.message))}")
        elif isinstance(update, TaskArtifactUpdateEvent):
            print(f"    [{agent_name} ⇢ stream] artifact received")

    # Polling: message/send returned straight away — check back until done
    polls = 0
    if task.status.state not in TERMINAL:
        print(f"    [{agent_name} ⇠ poll] task {task.id[:8]} {task.status.state.value} — polling tasks/get")
    while task.status.state not in TERMINAL:
        await asyncio.sleep(1.0)
        polls += 1
        task = await client.get_task(TaskQueryParams(id=task.id))
    via = f"after {polls} polls" if polls else "via stream"
    print(f"    [{agent_name}] task {task.id[:8]} {task.status.state.value} {via}")
    return task


async def negotiate_by_push(http: httpx.AsyncClient, negotiation_url: str, webhook_port: int) -> None:
    """Hand the whole negotiation to one agent and get its updates by push."""
    print("\n" + "=" * 60)
    print("STEP 3: The same negotiation, run by ONE agent — results by push")
    print("=" * 60)
    try:
        card = await A2ACardResolver(httpx_client=http, base_url=negotiation_url).get_agent_card()
    except A2AClientHTTPError as e:
        print(f"\nNegotiation agent not reachable at {negotiation_url} (HTTP {e.status_code}) — skipping.")
        print("Start it with: python m2_adk_multiagents/a2a_demos/negotiation_a2a_server.py")
        return
    print("\nNegotiation Agent Card:")
    print(f"  Name:   {card.name}")
    print(f"  URL:    {card.url}")
    print(f"  Capabilities: streaming={card.capabilities.streaming}, "
          f"pushNotifications={card.capabilities.push_notifications}  → use push notifications")
    if not card.capabilities.push_notifications:
        print("  The card doesn't offer push notifications — skipping.")
        return

    # A small webhook server inside this script. The token is shared with the
    # agent's server, which sends it back in X-A2A-Notification-Token on every
    # POST, so we can reject POSTs that didn't come from it.
    token = secrets.token_urlsafe(16)
    done = asyncio.Event()
    posts = 0
    final_task: Task | None = None

    async def webhook(request: Request) -> JSONResponse:
        nonlocal posts, final_task
        posts += 1
        if request.headers.get("X-A2A-Notification-Token") != token:
            return JSONResponse({"ok": False}, status_code=401)
        task = Task.model_validate(await request.json())     # each POST is the whole Task
        message = task.status.message
        if tool_calls(message):
            print(f"    [negotiation ⇠ push #{posts}] {task.status.state.value}: calling {', '.join(tool_calls(message))}")
        elif message and message.parts and isinstance(message.parts[0].root, TextPart):
            print(f"    [negotiation ⇠ push #{posts}] {task.status.state.value}: {message.parts[0].root.text.strip()[:100]}")
        if task.status.state in TERMINAL:
            final_task = task
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

    try:
        client = ClientFactory(ClientConfig(
            httpx_client=http,
            streaming=False,
            polling=True,                     # blocking=false: don't wait for the result
            push_notification_configs=[PushNotificationConfig(url=webhook_url, token=token)],
        )).create(card)
        message = Message(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            role=Role.user,
            parts=[TextPart(text="Start the negotiation.")],
        )
        async for event in client.send_message(message):
            task = event[0] if isinstance(event, tuple) else None
        print(f"\n→ message/send with webhook {webhook_url}")
        print(f"    returned at once: task {task.id[:8]} {task.status.state.value} — "
              "no open connection, no polling; waiting for POSTs\n")
        await asyncio.wait_for(done.wait(), timeout=600)
    finally:
        server.should_exit = True
        await server_task

    print(f"\n← Final result (pushed, {posts} POSTs) — task {final_task.status.state.value}:")
    print(extract_agent_text(final_task))


async def main() -> None:
    parser = argparse.ArgumentParser(description="A2A orchestrated multi-round negotiation")
    parser.add_argument("--base-url", default=BASE_URL, help="Base URL of adk web --a2a")
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS, help="Max negotiation rounds")
    parser.add_argument("--negotiation-url", default=NEGOTIATION_URL, help="negotiation_a2a_server.py")
    parser.add_argument("--webhook-port", type=int, default=WEBHOOK_PORT)
    args = parser.parse_args()

    # Direct configuration: we know where the agents live. With a registry
    # (Google Cloud Agent Registry, AGNTCY Agent Directory, ...) the matchmaker
    # would instead search for "an agent with a seller skill" and get these
    # Agent Cards back — see a2a_protocols.md §13.1.
    buyer_url = f"{args.base_url}/a2a/buyer_agent"
    seller_url = f"{args.base_url}/a2a/seller_agent"

    async with httpx.AsyncClient(timeout=120.0) as http:

        # ── Step 1: Discover both agents via Agent Cards ──────────────
        print("=" * 60)
        print("STEP 1: Agent Card Discovery")
        print("=" * 60)

        cards = {}
        for role, url in (("buyer", buyer_url), ("seller", seller_url)):
            card = await A2ACardResolver(httpx_client=http, base_url=url).get_agent_card()
            cards[role] = card
            how = "message/stream" if card.capabilities.streaming else "message/send + tasks/get polling"
            print(f"\n{role.title()} Agent Card:")
            print(f"  Name:   {card.name}")
            print(f"  URL:    {card.url}")
            print(f"  Skills: {[s.name for s in card.skills]}")
            print(f"  Capabilities: streaming={card.capabilities.streaming}, "
                  f"pushNotifications={card.capabilities.push_notifications}  → use {how}")

        buyer_client = client_for(http, cards["buyer"])
        seller_client = client_for(http, cards["seller"])

        # ── Step 2: Multi-round negotiation ───────────────────────────
        print("\n" + "=" * 60)
        print("STEP 2: Multi-Round Negotiation via A2A")
        print("=" * 60)

        buyer_context_id = None
        seller_context_id = None
        seller_response_text = None  # No seller response for round 1
        tasks_created = 0
        outcome = None

        for round_num in range(1, args.max_rounds + 1):
            print(f"\n{'─' * 50}")
            print(f"ROUND {round_num}")
            print(f"{'─' * 50}")

            # ── Ask buyer for an offer ────────────────────────────────
            if seller_response_text:
                buyer_prompt = (
                    f"The seller responded: {seller_response_text}\n\n"
                    f"This is round {round_num}. Make your next offer."
                )
            else:
                buyer_prompt = (
                    "Make your opening offer for 742 Evergreen Terrace, "
                    "Austin TX 78701 (listed at $485,000). "
                    "Use your pricing tools first."
                )

            print(f"\n→ Sending to BUYER:\n{buyer_prompt}")
            buyer_task = await ask(buyer_client, "buyer", buyer_prompt, buyer_context_id)
            buyer_context_id = buyer_task.context_id
            tasks_created += 1
            buyer_offer_text = extract_agent_text(buyer_task)
            if buyer_task.status.state != TaskState.completed:
                print(f"\nBuyer task ended {buyer_task.status.state.value}: {buyer_offer_text}")
                outcome = f"buyer_task_{buyer_task.status.state.value}"
                break
            print(f"← Buyer says (artifact):\n{buyer_offer_text}")

            # ── Buyer walked away? End the negotiation ────────────────
            if re.search(r"\bWALK[\s_-]?AWAY\b", buyer_offer_text, re.IGNORECASE):
                print(f"\n{'=' * 60}")
                print(f"BUYER WALKED AWAY in round {round_num} — no deal.")
                print(f"{'=' * 60}")
                outcome = "buyer_walked_away"
                break

            # ── Forward buyer's offer to seller ───────────────────────
            seller_prompt = (
                f"The buyer makes this offer:\n\n{buyer_offer_text}\n\n"
                f"This is round {round_num}. Respond with ACCEPT or COUNTER."
            )

            print(f"\n→ Sending to SELLER:\n{seller_prompt}")
            seller_task = await ask(seller_client, "seller", seller_prompt, seller_context_id)
            seller_context_id = seller_task.context_id
            tasks_created += 1
            seller_response_text = extract_agent_text(seller_task)
            if seller_task.status.state != TaskState.completed:
                print(f"\nSeller task ended {seller_task.status.state.value}: {seller_response_text}")
                outcome = f"seller_task_{seller_task.status.state.value}"
                break
            print(f"← Seller says (artifact):\n{seller_response_text}")

            # ── Check for acceptance (exactly one keyword expected) ───
            has_counter = bool(re.search(r"\bCOUNTER\b", seller_response_text, re.IGNORECASE))
            has_accept = bool(re.search(r"\bACCEPT\b", seller_response_text, re.IGNORECASE))
            if has_accept and not has_counter:
                agreed_price = extract_price(seller_response_text)
                print(f"\n{'=' * 60}")
                print(f"DEAL REACHED in round {round_num}!")
                print(f"{'=' * 60}")
                deal_msg = "Buyer's final offer was accepted by the seller."
                if agreed_price:
                    deal_msg += f" Agreed price: {agreed_price}."
                print(deal_msg)
                outcome = "deal"
                break
        else:
            print(f"\n{'=' * 60}")
            print(f"MAX ROUNDS ({args.max_rounds}) reached — no agreement.")
            print(f"{'=' * 60}")
            outcome = "max_rounds"

        # ── Summary ──────────────────────────────────────────────────
        print("\nA2A Protocol Summary:")
        print(f"  Outcome:          {outcome}")
        print(f"  Buyer  contextId: {buyer_context_id}  (reached by polling)")
        print(f"  Seller contextId: {seller_context_id}  (reached by streaming)")
        print(f"  A2A tasks created: {tasks_created} (one per message)")
        print("  Each agent maintained its own conversation thread.")

        # ── Step 3: one agent runs the whole negotiation (push) ───────
        await negotiate_by_push(http, args.negotiation_url, args.webhook_port)


if __name__ == "__main__":
    asyncio.run(main())
