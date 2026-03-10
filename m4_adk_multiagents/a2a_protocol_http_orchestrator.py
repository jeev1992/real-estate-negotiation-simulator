"""
HTTP A2A Negotiation Orchestrator (Google ADK-native state)
===========================================================
Runs a multi-round negotiation loop over HTTP A2A.

- Buyer turn is produced by BuyerAgentADK.
- Seller turn is requested from a remote A2A seller server.
- Orchestration state (round/status/prices) is persisted in ADK InMemorySessionService.

Run (terminal 1):
  python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102

Run (terminal 2):
  python m4_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Literal, Optional

import httpx
from a2a.client import A2AClient, A2ACardResolver
from a2a.types import Message, MessageSendParams, Role, SendMessageRequest, TextPart
from dotenv import load_dotenv
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.sessions import InMemorySessionService
from pydantic import BaseModel, Field, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from m4_adk_multiagents.buyer_adk import BuyerAgentADK


class SellerEnvelope(BaseModel):
    session_id: str
    round: int
    from_agent: Literal["seller"]
    to_agent: Literal["buyer"]
    message_type: Literal["COUNTER_OFFER", "ACCEPT", "REJECT"]
    price: float | None = None
    message: str
    conditions: list[str] = Field(default_factory=list)
    closing_timeline_days: int | None = None
    in_reply_to: str | None = None


def _extract_texts(obj: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "text" and isinstance(value, str):
                texts.append(value)
            else:
                texts.extend(_extract_texts(value))
    elif isinstance(obj, list):
        for item in obj:
            texts.extend(_extract_texts(item))
    return texts


def _extract_first_seller_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    for text in _extract_texts(payload):
        try:
            candidate = json.loads(text)
            if isinstance(candidate, dict):
                parsed = SellerEnvelope.model_validate(candidate)
                return parsed.model_dump(mode="json")
        except ValidationError:
            continue
        except json.JSONDecodeError:
            continue
    raise ValueError("No valid seller envelope found in A2A response text parts.")


class ADKOrchestrationState:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.app_name = "a2a_http_orchestrator"
        self.user_id = "orchestrator"
        self._service = InMemorySessionService()

    async def initialize(self, max_rounds: int) -> None:
        await self._service.create_session(
            app_name=self.app_name,
            user_id=self.user_id,
            session_id=self.session_id,
            state={"round": 0, "status": "negotiating", "max_rounds": max_rounds},
        )

    async def update(self, state_delta: dict[str, Any]) -> None:
        session = await self._service.get_session(
            app_name=self.app_name,
            user_id=self.user_id,
            session_id=self.session_id,
        )
        if session is None:
            raise RuntimeError("Orchestration ADK session not found.")
        await self._service.append_event(
            session=session,
            event=Event(author=self.user_id, actions=EventActions(stateDelta=state_delta)),
        )

    async def read_state(self) -> dict[str, Any]:
        session = await self._service.get_session(
            app_name=self.app_name,
            user_id=self.user_id,
            session_id=self.session_id,
        )
        if session is None:
            return {}
        return dict(session.state)


async def main() -> None:
    parser = argparse.ArgumentParser(description="HTTP A2A orchestration loop demo")
    parser.add_argument("--seller-url", default="http://127.0.0.1:9102")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--session", default=None)
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. Set it before running this demo.")
        raise SystemExit(1)

    session_id = args.session or f"a2a_http_{uuid.uuid4().hex[:8]}"
    state = ADKOrchestrationState(session_id=session_id)
    await state.initialize(max_rounds=args.rounds)

    print(f"\nSession: {session_id}")
    print(f"Seller URL: {args.seller_url}")
    print(f"Max rounds: {args.rounds}")

    async with BuyerAgentADK(session_id=f"{session_id}_buyer") as buyer:
        async with httpx.AsyncClient(timeout=45.0) as http_client:
            resolver = A2ACardResolver(httpx_client=http_client, base_url=args.seller_url)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            last_seller: Optional[dict[str, Any]] = None
            status = "negotiating"
            agreed_price: Optional[float] = None

            for round_num in range(1, args.rounds + 1):
                if round_num == 1:
                    buyer_message = await buyer.make_initial_offer_envelope()
                else:
                    if last_seller is None:
                        raise RuntimeError("Missing seller message for next buyer turn.")
                    buyer_message = await buyer.respond_to_counter_envelope(last_seller)

                print(f"\n[Buyer] Round {buyer_message['round']} | {buyer_message['message_type']} | ${buyer_message.get('price') or 0:,.0f}")

                await state.update(
                    {
                        "round": buyer_message["round"],
                        "status": "buyer_walked" if buyer_message["message_type"] == "WITHDRAW" else "negotiating",
                        "last_buyer_type": buyer_message["message_type"],
                        "last_buyer_price": buyer_message.get("price"),
                    }
                )

                if buyer_message["message_type"] == "WITHDRAW":
                    status = "buyer_walked"
                    break

                request = SendMessageRequest(
                    id=f"req_{uuid.uuid4().hex[:8]}",
                    params=MessageSendParams(
                        message=Message(
                            messageId=f"msg_{uuid.uuid4().hex[:8]}",
                            role=Role.user,
                            parts=[TextPart(text=json.dumps(buyer_message))],
                        )
                    ),
                )

                response = await client.send_message(request)
                dumped = response.model_dump(mode="json")
                seller_message = _extract_first_seller_envelope(dumped)
                last_seller = seller_message

                print(f"[Seller] Round {seller_message['round']} | {seller_message['message_type']} | ${seller_message.get('price') or 0:,.0f}")

                if seller_message["message_type"] == "ACCEPT":
                    status = "agreed"
                    agreed_price = seller_message.get("price")
                elif seller_message["message_type"] == "REJECT":
                    status = "seller_rejected"
                else:
                    status = "negotiating"

                await state.update(
                    {
                        "round": seller_message["round"],
                        "status": status,
                        "last_seller_type": seller_message["message_type"],
                        "last_seller_price": seller_message.get("price"),
                        "agreed_price": agreed_price,
                    }
                )

                if status != "negotiating":
                    break

            if status == "negotiating":
                status = "deadlocked"
                await state.update({"status": status})

            current = await state.read_state()
            print("\n=== A2A ORCHESTRATION RESULT ===")
            print(f"Status: {status}")
            if agreed_price:
                print(f"Agreed price: ${agreed_price:,.0f}")
            print(f"ADK session state: {json.dumps(current, indent=2)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (ValueError, ValidationError) as error:
        print(f"ERROR: {error}")
        raise SystemExit(1)
