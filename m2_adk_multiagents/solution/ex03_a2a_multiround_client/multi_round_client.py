"""
Solution — Exercise 3: A2A multi-round client
================================================

A standalone script that drives a buyer ↔ seller negotiation over the
A2A protocol. The script knows nothing about how either agent is
implemented — it only knows the A2A protocol.

Key A2A concepts on display:
  • Agent Card discovery — fetch /.well-known/agent-card.json
  • The wire format      — a hand-built JSON-RPC `message/send` (demo 13 does
                           the same negotiation with the SDK's Client)
  • contextId threading  — each agent has its own thread; we maintain both
  • Checking results     — a JSON-RPC `error` reply, and a Task whose state
                           isn't `completed`, both stop the negotiation
  • Structured results   — the seller's decision is read from its
                           submit_decision tool result in the Task history,
                           not from its prose

Prereq: both agents must already be running:

    adk web --a2a m2_adk_multiagents/negotiation_agents/

Then run:

    python m2_adk_multiagents/solution/ex03_a2a_multiround_client/multi_round_client.py

Optional:
    --base-url http://127.0.0.1:8000      # default — where the Agent Cards are fetched
    --max-rounds 5                         # default

Messages go to the `url` in each Agent Card (that's the protocol). The cards
come from negotiation_agents/*/agent.json and say http://localhost:8000/... —
if you run adk web on another port, update those too.
"""

import argparse
import asyncio
import re
import sys
import uuid

import httpx
from a2a.client import A2ACardResolver
from a2a.client.errors import A2AClientHTTPError


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_MAX_ROUNDS = 5


# ─── Helpers ──────────────────────────────────────────────────────────────────

def extract_agent_text(result: dict) -> str:
    """Pull the agent's text response from an A2A result.

    Strategy: prefer `artifacts` (durable outputs of the task) over `history`
    (the conversation transcript). If neither has text, return a placeholder.
    """
    # Artifacts first — this is where the agent's "deliverable" lives.
    for artifact in result.get("artifacts") or []:
        for part in artifact.get("parts") or []:
            if part.get("kind") == "text":
                return part["text"]

    # A failed task explains itself in status.message.
    status_message = (result.get("status") or {}).get("message")
    if status_message and status_message.get("role") == "agent":
        for part in status_message.get("parts") or []:
            if part.get("kind") == "text":
                return part["text"]

    # Fallback: last agent message in history.
    for msg in reversed(result.get("history") or []):
        if msg.get("role") == "agent":
            for part in msg.get("parts") or []:
                if part.get("kind") == "text":
                    return part["text"]

    return "(no response)"


async def send_a2a_message(
    http: httpx.AsyncClient,
    agent_url: str,
    text: str,
    context_id: str | None = None,
) -> tuple[dict, str | None]:
    """Send a TextPart message to an A2A agent.

    Returns (result_dict, new_context_id) — result_dict is the Task.
    On round 1, pass context_id=None — the server assigns one.
    On later rounds, pass the contextId from the prior response.

    Raises RuntimeError on a JSON-RPC error reply (sent with HTTP 200, so
    raise_for_status() alone doesn't catch it).
    """
    request_body = {
        "jsonrpc": "2.0",
        "id": f"req_{uuid.uuid4().hex[:8]}",
        "method": "message/send",
        "params": {
            "message": {
                "messageId": f"msg_{uuid.uuid4().hex[:8]}",
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
                # Threading: include contextId only if we have one.
                **({"contextId": context_id} if context_id else {}),
            }
        },
    }
    resp = await http.post(agent_url, json=request_body)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        error = data["error"]
        raise RuntimeError(f"JSON-RPC error {error.get('code')}: {error.get('message')}")
    result = data["result"]
    return result, result.get("contextId")


def task_state(result: dict) -> str:
    """The Task's state: "completed", "failed", ... (blocking message/send returns a final one)."""
    return (result.get("status") or {}).get("state", "unknown")


def seller_decision(result: dict) -> dict | None:
    """The seller's last recorded decision, e.g. {"recorded": "ACCEPT", "price": 446000}.

    The seller records every decision with its submit_decision tool, and ADK
    puts tool results in the Task history as data parts:
        {"kind": "data", "data": {"name": "submit_decision", "response": {...}}}
    That result is authoritative — the tool enforces the seller's floor and can
    record a different action than the model asked for. The prose isn't: a
    regex for ACCEPT matches "I cannot ACCEPT $440,000", and the first dollar
    amount in "With $75,000 in upgrades, I accept $446,000" is $75,000.
    """
    decision = None
    for msg in result.get("history") or []:
        for part in msg.get("parts") or []:
            data = part.get("data") if part.get("kind") == "data" else None
            response = (data or {}).get("response")
            if (data or {}).get("name") == "submit_decision" and isinstance(response, dict) \
                    and "recorded" in response:
                decision = response
    return decision


# "WALK AWAY", but not "I will not walk away" / "won't walk away".
_WALK_AWAY_RE = re.compile(r"(?<!not )(?<!n't )\bWALK[\s_-]?AWAY\b", re.IGNORECASE)


# ─── The orchestrator ─────────────────────────────────────────────────────────

async def run_negotiation(base_url: str, max_rounds: int) -> None:
    buyer_url = f"{base_url}/a2a/buyer_agent"
    seller_url = f"{base_url}/a2a/seller_agent"

    async with httpx.AsyncClient(timeout=120.0) as http:

        # ─ Step 1: discover both agents via Agent Cards ───────────────────
        print("=" * 60)
        print("STEP 1 — Agent Card Discovery")
        print("=" * 60)

        buyer_card = (await A2ACardResolver(httpx_client=http, base_url=buyer_url)
                      .get_agent_card()).model_dump(mode="json")
        seller_card = (await A2ACardResolver(httpx_client=http, base_url=seller_url)
                       .get_agent_card()).model_dump(mode="json")

        for label, card in [("Buyer", buyer_card), ("Seller", seller_card)]:
            print(f"\n{label} Agent Card:")
            print(f"  Name:   {card['name']}")
            print(f"  URL:    {card['url']}")
            print(f"  Skills: {[s['name'] for s in card.get('skills', [])]}")

        # ─ Step 2: multi-round loop ───────────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 2 — Multi-Round Negotiation")
        print("=" * 60)

        # Each agent has its OWN contextId. The script maintains both.
        # On round 1, both are None — server assigns them on first POST.
        buyer_context_id: str | None = None
        seller_context_id: str | None = None
        seller_response_text: str | None = None  # nothing on round 1
        messages_sent = 0
        outcome = None

        for round_num in range(1, max_rounds + 1):
            print(f"\n{'─' * 50}\nROUND {round_num}\n{'─' * 50}")

            # ── Ask the buyer ─────────────────────────────────────────────
            if seller_response_text:
                buyer_prompt = (
                    f"The seller responded: {seller_response_text}\n\n"
                    f"This is round {round_num}. Make your next offer."
                )
            else:
                buyer_prompt = (
                    "Make your opening offer for 742 Evergreen Terrace, "
                    "Austin TX 78701 (listed at $485,000)."
                )

            buyer_result, buyer_context_id = await send_a2a_message(
                http, buyer_card["url"], buyer_prompt, buyer_context_id
            )
            messages_sent += 1
            buyer_offer_text = extract_agent_text(buyer_result)
            if task_state(buyer_result) != "completed":
                print(f"\nBuyer task ended '{task_state(buyer_result)}': {buyer_offer_text}")
                outcome = f"buyer_task_{task_state(buyer_result)}"
                break
            print(f"\n→ BUYER (contextId={(buyer_context_id or '')[:8]}...):")
            print(f"  {buyer_offer_text}")

            # ── Buyer walked away? End the negotiation ──────────────────
            if _WALK_AWAY_RE.search(buyer_offer_text):
                print(f"\n{'=' * 60}")
                print(f"BUYER WALKED AWAY in round {round_num} — no deal")
                print(f"{'=' * 60}")
                outcome = "buyer_walked_away"
                break

            # ── Forward the buyer's offer to the seller ───────────────────
            seller_prompt = (
                f"The buyer makes this offer:\n\n{buyer_offer_text}\n\n"
                f"This is round {round_num}. Respond with ACCEPT or COUNTER."
            )

            seller_result, seller_context_id = await send_a2a_message(
                http, seller_card["url"], seller_prompt, seller_context_id
            )
            messages_sent += 1
            seller_response_text = extract_agent_text(seller_result)
            if task_state(seller_result) != "completed":
                print(f"\nSeller task ended '{task_state(seller_result)}': {seller_response_text}")
                outcome = f"seller_task_{task_state(seller_result)}"
                break
            print(f"\n← SELLER (contextId={(seller_context_id or '')[:8]}...):")
            print(f"  {seller_response_text}")

            # ── Termination check: the decision submit_decision recorded ──
            decision = seller_decision(seller_result)
            if decision is None:
                print("\n  ⚠ seller recorded no decision with submit_decision — no deal this round")
            elif decision["recorded"] == "ACCEPT":
                print(f"\n{'=' * 60}")
                print(f"DEAL REACHED in round {round_num} at ${decision['price']:,} "
                      "(from submit_decision)")
                print(f"{'=' * 60}")
                outcome = "deal"
                break
            else:
                print(f"\n  seller recorded {decision['recorded']} at ${decision['price']:,}")
        else:
            print(f"\n{'=' * 60}")
            print(f"MAX ROUNDS ({max_rounds}) REACHED — no agreement")
            print(f"{'=' * 60}")
            outcome = "max_rounds"

        # ─ Summary ────────────────────────────────────────────────────────
        print(f"\nA2A summary:")
        print(f"  Outcome:          {outcome}")
        print(f"  Buyer  contextId: {buyer_context_id}")
        print(f"  Seller contextId: {seller_context_id}")
        print(f"  → They are DIFFERENT — your script bridged two threads.")
        print(f"  Total A2A messages sent: {messages_sent}")


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    args = parser.parse_args()

    await run_negotiation(args.base_url, args.max_rounds)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # so the output can be piped/redirected on Windows
    try:
        asyncio.run(main())
    except (A2AClientHTTPError, httpx.ConnectError) as e:
        if isinstance(e, A2AClientHTTPError) and e.status_code != 503:
            raise
        sys.exit(f"Can't reach the agent: {e}\n"
                 "Start the agents first:  adk web --a2a m2_adk_multiagents/negotiation_agents/")
