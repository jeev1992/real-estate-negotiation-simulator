"""
Solution — Exercise 3: A2A multi-round client
================================================

A standalone script that drives a buyer ↔ seller negotiation over the
A2A protocol. The script knows nothing about how either agent is
implemented — it only knows the A2A protocol.

Two key A2A concepts on display:
  • Agent Card discovery — fetch /.well-known/agent-card.json
  • contextId threading  — each agent has its own thread; we maintain both

Prereq: both agents must already be running:

    adk web --a2a m3_adk_multiagents/negotiation_agents/

Then run:

    python m3_adk_multiagents/solution/ex03_a2a_multiround_client/multi_round_client.py

Optional:
    --base-url http://127.0.0.1:8000      # default
    --max-rounds 5                         # default
"""

import argparse
import asyncio
import re
import uuid

import httpx
from a2a.client import A2ACardResolver


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

    Returns (result_dict, new_context_id).
    On round 1, pass context_id=None — the server assigns one.
    On later rounds, pass the contextId from the prior response.
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
    result = data.get("result", {})
    return result, result.get("contextId")


def has_acceptance(text: str) -> bool:
    """Detect ACCEPT in the seller's response — word-boundary, case-insensitive.

    Why word-boundary? Because the substring 'accept' appears in 'acceptable',
    which the seller's tool calls return ('minimum acceptable price'). Without
    \\b we'd false-trigger on every counter-offer that mentions the floor.
    """
    return bool(re.search(r"\bACCEPT\b", text, re.IGNORECASE)) and \
           not bool(re.search(r"\bCOUNTER\b", text, re.IGNORECASE))


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
            buyer_offer_text = extract_agent_text(buyer_result)
            print(f"\n→ BUYER (contextId={buyer_context_id[:8]}...):")
            print(f"  {buyer_offer_text[:250]}...")

            # ── Forward the buyer's offer to the seller ───────────────────
            seller_prompt = (
                f"The buyer makes this offer:\n\n{buyer_offer_text}\n\n"
                f"This is round {round_num}. Respond with ACCEPT or COUNTER."
            )

            seller_result, seller_context_id = await send_a2a_message(
                http, seller_card["url"], seller_prompt, seller_context_id
            )
            seller_response_text = extract_agent_text(seller_result)
            print(f"\n← SELLER (contextId={seller_context_id[:8]}...):")
            print(f"  {seller_response_text[:250]}...")

            # ── Termination check ─────────────────────────────────────────
            if has_acceptance(seller_response_text):
                print(f"\n{'=' * 60}")
                print(f"DEAL REACHED in round {round_num}")
                print(f"{'=' * 60}")
                break
        else:
            print(f"\n{'=' * 60}")
            print(f"MAX ROUNDS ({max_rounds}) REACHED — no agreement")
            print(f"{'=' * 60}")

        # ─ Summary ────────────────────────────────────────────────────────
        print(f"\nA2A summary:")
        print(f"  Buyer  contextId: {buyer_context_id}")
        print(f"  Seller contextId: {seller_context_id}")
        print(f"  → They are DIFFERENT — your script bridged two threads.")
        print(f"  Total A2A messages sent: {round_num * 2}")


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    args = parser.parse_args()

    await run_negotiation(args.base_url, args.max_rounds)


if __name__ == "__main__":
    asyncio.run(main())
