"""
True A2A Protocol Seller Server (ADK + OpenAI)
==============================================
Runs a seller agent as an A2A protocol server using `a2a-sdk`.

This is a true networked Agent-to-Agent endpoint:
- Exposes an Agent Card at `/.well-known/agent-card.json`
- Accepts `message/send` requests over A2A JSON-RPC
- Uses ADK seller logic to produce responses

Run:
  python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events.event_queue import EventQueue
from a2a.server.events.in_memory_queue_manager import InMemoryQueueManager
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentProvider, AgentSkill, TextPart
from pydantic import BaseModel, Field, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load OPENAI_API_KEY and other local vars from repo-root .env.
load_dotenv(REPO_ROOT / ".env")

from m4_adk_multiagents.seller_adk import SellerAgentADK


class BuyerEnvelope(BaseModel):
    """Contract the server expects from buyer side over HTTP A2A.

    Every incoming A2A message is validated against this schema.
    If the buyer sends malformed JSON or missing fields, Pydantic raises
    immediately and the request returns a task-failed response.
    """
    session_id: str
    round: int
    from_agent: str
    to_agent: str
    message_type: str
    price: float | None = None
    message: str
    conditions: list[str] = Field(default_factory=list)
    closing_timeline_days: int | None = None
    in_reply_to: str | None = None


class SellerSessionRegistry:
    """Manages one SellerAgentADK instance per session_id.

    Why this exists: Each HTTP request is stateless, but the seller needs
    multi-turn memory (Round 2 must remember Round 1). The registry maps
    session_id → a persistent SellerAgentADK object with its ADK session
    history and MCP connections intact.

    Without this, every HTTP request would create a fresh seller agent
    with no memory of previous rounds.
    """

    def __init__(self):
        self._agents: dict[str, SellerAgentADK] = {}
        self._lock = asyncio.Lock()  # prevents race conditions on concurrent requests

    async def get_or_create(self, session_id: str) -> SellerAgentADK:
        """Return existing agent for this session, or create one on first request."""
        async with self._lock:
            existing = self._agents.get(session_id)
            if existing is not None:
                return existing

            # Lazily create seller ADK agent the first time this session appears.
            # __aenter__ spawns MCP subprocesses and discovers tools.
            agent = SellerAgentADK(session_id=f"seller_a2a_{session_id}")
            await agent.__aenter__()
            self._agents[session_id] = agent
            return agent

    def get_agent(self, session_id: str) -> SellerAgentADK | None:
        """Return existing agent for this session, or None if not found."""
        return self._agents.get(session_id)

    def list_sessions(self) -> list[str]:
        """Return all active session IDs."""
        return list(self._agents.keys())

    async def close_all(self) -> None:
        """Graceful server shutdown: close all managed ADK agent contexts.

        Called in the server's 'finally' block when Ctrl+C is pressed.
        Each agent's __aexit__ kills its MCP subprocesses — without this,
        orphaned Python processes accumulate on the host.
        """
        async with self._lock:
            agents = list(self._agents.values())
            self._agents.clear()
        for agent in agents:
            try:
                await agent.__aexit__(None, None, None)
            except Exception:
                pass


SESSION_REGISTRY = SellerSessionRegistry()


def _build_agent_card(base_url: str) -> AgentCard:
    """Build the A2A Agent Card — the discovery contract.

    This JSON is served at GET /.well-known/agent-card.json.
    When a buyer (or any A2A client) wants to talk to this seller,
    it fetches the Agent Card first to learn:
      - url: where to send messages
      - skills: what the agent can do
      - capabilities: streaming? push notifications?
      - protocolVersion: which A2A spec version
      - preferredTransport: JSONRPC (vs. streaming, etc.)
    """
    return AgentCard(
        name="adk_seller_a2a_server",
        description="ADK-backed seller agent exposed via A2A protocol",
        url=base_url,
        version="1.0.0",
        protocolVersion="0.3.0",
        preferredTransport="JSONRPC",
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        capabilities=AgentCapabilities(streaming=False, pushNotifications=False),
        skills=[
            AgentSkill(
                id="real_estate_seller_negotiation",
                name="Real Estate Seller Negotiation",
                description="Responds to buyer offers with ADK-generated counter-offers or acceptance",
                tags=["real_estate", "negotiation", "seller", "adk", "a2a"],
                examples=["Buyer offers $438,000 with 45-day close"],
                inputModes=["text/plain"],
                outputModes=["text/plain"],
            )
        ],
        provider=AgentProvider(
            organization="Negotiation Workshop",
            url="https://example.local/negotiation-workshop",
        ),
    )


class SellerADKA2AExecutor(AgentExecutor):
    """Handles incoming A2A requests by running the seller ADK agent.

    A2A lifecycle for each request:
      1. start_work()  →  task status becomes 'working'
      2. Parse buyer envelope from the request text
      3. Run seller agent (which calls MCP tools + GPT-4o internally)
      4. complete()    →  task status becomes 'completed' with response
         OR failed()   →  task status becomes 'failed' with error message
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # TaskUpdater manages the A2A task lifecycle (working → completed/failed).
        # The buyer client sees these status transitions in the HTTP response.
        updater = TaskUpdater(event_queue, task_id=context.task_id, context_id=context.context_id)

        await updater.start_work()

        incoming_text = context.get_user_input().strip()

        try:
            # Validate incoming JSON text against the buyer envelope contract.
            # If the buyer sends malformed JSON or missing fields, this raises
            # and we return a task-failed response — no silent corruption.
            parsed_buyer = BuyerEnvelope.model_validate(json.loads(incoming_text))

            # One-turn processing over HTTP; multi-turn continuity is preserved
            # by the session registry (same SellerAgentADK instance across rounds).
            seller = await SESSION_REGISTRY.get_or_create(parsed_buyer.session_id)
            response_payload: dict[str, Any] = await seller.respond_to_offer_envelope(
                parsed_buyer.model_dump(mode="json")
            )

            agent_message = updater.new_agent_message(
                parts=[TextPart(text=json.dumps(response_payload))],
                metadata={"protocol": "a2a", "runtime": "adk-openai"},
            )
            # Complete task with one final structured response payload.
            await updater.complete(agent_message)

        except (json.JSONDecodeError, ValidationError) as error:
            # Contract violations are returned as task failures with explicit message.
            agent_message = updater.new_agent_message(
                parts=[TextPart(text=f"ERROR: Invalid buyer envelope. {error}")],
                metadata={"protocol": "a2a", "runtime": "adk-openai", "status": "error"},
            )
            await updater.failed(message=agent_message)
        except Exception as error:
            # Surface failures to client as task-failed responses (not silent drops).
            agent_message = updater.new_agent_message(
                parts=[TextPart(text=f"ERROR: {error}")],
                metadata={"protocol": "a2a", "runtime": "adk-openai", "status": "error"},
            )
            await updater.failed(message=agent_message)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, task_id=context.task_id, context_id=context.context_id)
        cancel_message = updater.new_agent_message(
            parts=[TextPart(text="Request cancelled by client")],
            metadata={"protocol": "a2a", "runtime": "adk-openai", "status": "cancelled"},
        )
        await updater.cancel(message=cancel_message)


async def main() -> None:
    parser = argparse.ArgumentParser(description="True A2A seller server (ADK + OpenAI)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9102)
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. Set it before starting A2A seller server.")
        raise SystemExit(1)

    base_url = f"http://{args.host}:{args.port}"
    # Agent card is the discovery metadata clients fetch before messaging.
    card = _build_agent_card(base_url)

    # Wire up the A2A server: agent card (discovery) + request handler (execution).
    handler = DefaultRequestHandler(
        agent_executor=SellerADKA2AExecutor(),  # our subclass handles each request
        task_store=InMemoryTaskStore(),          # tracks task lifecycle in memory
        queue_manager=InMemoryQueueManager(),    # manages event queues per task
    )

    # A2AFastAPIApplication creates two routes:
    #   GET  /.well-known/agent-card.json  →  returns the Agent Card
    #   POST /                             →  handles A2A JSON-RPC message/send
    app_builder = A2AFastAPIApplication(agent_card=card, http_handler=handler)
    app = app_builder.build(agent_card_url="/.well-known/agent-card.json", rpc_url="/")

    import uvicorn

    print(f"A2A seller server listening at {base_url}")
    print(f"Agent card: {base_url}/.well-known/agent-card.json")
    config = uvicorn.Config(app=app, host=args.host, port=args.port)
    server = uvicorn.Server(config)
    try:
        await server.serve()
    finally:
        await SESSION_REGISTRY.close_all()


if __name__ == "__main__":
    asyncio.run(main())
