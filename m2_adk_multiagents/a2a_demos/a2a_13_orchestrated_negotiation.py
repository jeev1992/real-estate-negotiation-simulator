"""
Demo 13 — A2A Orchestrated Negotiation
=========================================
Full multi-round buyer ↔ seller negotiation where BOTH agents are
discovered via Agent Cards and communicate through A2A messages.

THIS IS THE PAYOFF DEMO. It shows:
  1. Agent Card discovery for BOTH buyer and seller
  2. The client reading each card's capabilities and getting results the
     way that agent supports:
       buyer_agent   streaming: false → POLLING: message/send (non-blocking) + tasks/get
       seller_agent  streaming: true  → STREAMING: message/stream (live events)
  3. Multi-round negotiation: buyer offers → script relays to seller → seller responds
  4. contextId threads each side's conversation independently; every
     round is a new Task, and the agent's reply is read from its Artifact
  5. The script acts as a "matchmaker" — neither agent knows about the other

HOW IT WORKS:
  The script is NOT an agent itself — it's a simple orchestrator that:
  - Discovers buyer_agent and seller_agent via their Agent Cards
  - Asks the buyer to make an offer (polling: send, then tasks/get until done)
  - Forwards the buyer's offer to the seller (streaming: tool calls arrive live)
  - Reads the seller's decision (ACCEPT or COUNTER) from the structured
    submit_decision tool result in the task history — not from the prose
  - If COUNTER: sends the counter back to the buyer for next round
  - Repeats until ACCEPT, WALK AWAY, a task that doesn't complete, or max rounds

  Each agent has its own contextId — the buyer's conversation thread
  and the seller's conversation thread are separate. The script bridges
  them by extracting text from one response and sending it to the other.

WHAT LEARNERS SEE:
  - Two Agent Card fetches, with the capability each one advertises
  - Buyer turns: task submitted → polled → completed
  - Seller turns: the seller's MCP tool calls streamed as they happen
  - Agreement, walk-away, or max rounds reached

Prereq:
    adk web --a2a m2_adk_multiagents/negotiation_agents/

Run:
    python m2_adk_multiagents/a2a_demos/a2a_13_orchestrated_negotiation.py
"""

import argparse
import asyncio
import re
import sys
import uuid

import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, ClientFactory
from a2a.client.errors import A2AClientError, A2AClientHTTPError
from a2a.types import (
    AgentCard,
    DataPart,
    Message,
    Role,
    Task,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskQueryParams,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)

BASE_URL = "http://127.0.0.1:8000"
MAX_ROUNDS = 5
POLL_TIMEOUT_S = 180.0
TERMINAL = {TaskState.completed, TaskState.failed, TaskState.canceled, TaskState.rejected}
# Not finished, but polling won't help — the agent is waiting on the client.
INTERRUPTED = {TaskState.input_required, TaskState.auth_required}


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


def seller_decision(task: Task) -> dict | None:
    """The seller's last successfully recorded submit_decision result, e.g. {"recorded": "ACCEPT", "price": 446000}.

    ADK puts tool results in history as DataParts ({"name", "response"}). The
    tool's result is authoritative: it enforces the floor in code and may record
    a different action than the LLM asked for, and the prose can be ambiguous
    ("I cannot ACCEPT $440,000").
    """
    decision = None
    for msg in task.history or []:
        for part in msg.parts:
            data = part.root.data if isinstance(part.root, DataPart) else {}
            response = data.get("response")
            if data.get("name") == "submit_decision" and isinstance(response, dict) and "recorded" in response:
                decision = response
    return decision


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


async def ask(
    client: Client, agent_name: str, text: str, context_id: str | None, poll_timeout: float = POLL_TIMEOUT_S
) -> Task:
    """Send one message; follow the task until it ends or needs the client (stream, then poll if needed)."""
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

    if task is None:
        raise RuntimeError(f"{agent_name} sent no response")

    # Polling: message/send returned straight away — check back until done,
    # but stop if the agent needs input/auth, and give up after a deadline.
    polls = 0
    stop_states = TERMINAL | INTERRUPTED
    if task.status.state not in stop_states:
        print(f"    [{agent_name} ⇠ poll] task {task.id[:8]} {task.status.state.value} — polling tasks/get")
    deadline = asyncio.get_running_loop().time() + poll_timeout
    while task.status.state not in stop_states:
        if asyncio.get_running_loop().time() >= deadline:
            print(f"    [{agent_name}] task {task.id[:8]} still {task.status.state.value} "
                  f"after {poll_timeout:.0f}s — canceling it")
            try:
                task = await client.cancel_task(TaskIdParams(id=task.id))
            except A2AClientError as e:
                print(f"    [{agent_name}] cancel failed: {e}")
            return task
        await asyncio.sleep(1.0)
        polls += 1
        task = await client.get_task(TaskQueryParams(id=task.id))
    via = f"after {polls} polls" if polls else "via stream"
    print(f"    [{agent_name}] task {task.id[:8]} {task.status.state.value} {via}")
    return task


async def main() -> None:
    parser = argparse.ArgumentParser(description="A2A orchestrated multi-round negotiation")
    parser.add_argument("--base-url", default=BASE_URL, help="Base URL of adk web --a2a")
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS, help="Max negotiation rounds")
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
            # (The negated forms "not walk away" / "won't walk away" don't count.)
            if re.search(r"(?<!not )(?<!n't )\bWALK[\s_-]?AWAY\b", buyer_offer_text, re.IGNORECASE):
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

            # ── Check the decision the seller's submit_decision tool recorded ─
            decision = seller_decision(seller_task)
            if decision is None:
                print("\n  ⚠ seller did not record a decision with submit_decision — treating it as no deal this round")
            elif decision["recorded"] == "ACCEPT":
                print(f"\n{'=' * 60}")
                print(f"DEAL REACHED in round {round_num}!")
                print(f"{'=' * 60}")
                print(f"Seller recorded ACCEPT at ${decision['price']:,} (from submit_decision).")
                outcome = "deal"
                break
            else:
                print(f"\n  seller recorded {decision['recorded']} at ${decision['price']:,}")
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


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # so the output can be piped/redirected on Windows
    try:
        asyncio.run(main())
    except A2AClientHTTPError as e:
        if e.status_code != 503:   # 503 = the SDK's code for "nothing answered" (network error)
            raise
        sys.exit(f"Can't reach the agent: {e.message}\n"
                 "Start the agents first:  adk web --a2a m2_adk_multiagents/negotiation_agents/")
