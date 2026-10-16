"""
Negotiation agent over A2A — with push notifications
======================================================
Serves the `negotiation` agent (negotiation_agents/negotiation/agent.py) as an
A2A server on http://localhost:8003/ whose Agent Card advertises
`pushNotifications: true`.

Why not `adk web --a2a` like the buyer and seller?
  ADK's built-in A2A server stores a client's push-notification config but
  creates no push *sender*, so it would accept a webhook and never call it.
  Here we assemble the server ourselves from the same building blocks and add
  the missing piece:

    Runner              runs the ADK agent (the engine adk web wraps)
    A2aAgentExecutor    ADK's adapter: A2A request → Runner → A2A events
    DefaultRequestHandler  the A2A SDK's JSON-RPC logic (tasks, streaming, push)
    BasePushNotificationSender  POSTs task updates to the client's webhook  ← added

The card comes from negotiation_agents/negotiation/a2a_card.json (named so
that `adk web --a2a` does not also publish this agent without push support).

Run:
    python m2_adk_multiagents/a2a_demos/negotiation_a2a_server.py
    → Agent Card: http://localhost:8003/.well-known/agent-card.json
"""

import json
import sys
from pathlib import Path

import httpx
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import AgentCard
from dotenv import load_dotenv
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

_M2 = Path(__file__).resolve().parents[1]
load_dotenv(_M2.parent / ".env")
sys.path.insert(0, str(_M2 / "negotiation_agents"))
from negotiation.agent import root_agent  # noqa: E402

PORT = 8003
CARD_FILE = _M2 / "negotiation_agents" / "negotiation" / "a2a_card.json"


def build_app():
    card = AgentCard(**json.loads(CARD_FILE.read_text(encoding="utf-8")))
    runner = Runner(
        app_name=root_agent.name,
        agent=root_agent,
        session_service=InMemorySessionService(),
        artifact_service=InMemoryArtifactService(),
        memory_service=InMemoryMemoryService(),
    )
    push_configs = InMemoryPushNotificationConfigStore()
    handler = DefaultRequestHandler(
        agent_executor=A2aAgentExecutor(runner=runner),
        task_store=InMemoryTaskStore(),
        push_config_store=push_configs,
        push_sender=BasePushNotificationSender(httpx.AsyncClient(timeout=30.0), push_configs),
    )
    return A2AStarletteApplication(agent_card=card, http_handler=handler).build()


if __name__ == "__main__":
    print(f"negotiation A2A server (push notifications) → http://localhost:{PORT}/")
    print(f"   Agent Card: http://localhost:{PORT}/.well-known/agent-card.json")
    uvicorn.run(build_app(), host="127.0.0.1", port=PORT, log_level="warning")
