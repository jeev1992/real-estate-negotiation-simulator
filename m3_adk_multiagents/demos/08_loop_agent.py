"""
Demo 08 — ADK LoopAgent
========================
LoopAgent re-runs its sub-agents until either:
  - max_iterations is hit, OR
  - a child emits an EscalateAction (action="escalate") to break the loop.

Here a "haggler" proposes a price, then a "judge" decides whether the price
is acceptable. The judge escalates to stop the loop once the price is in
the target range — otherwise the haggler tries again.

Run:
    python m3_adk_multiagents/demos/08_loop_agent.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

MODEL = "openai/gpt-4o"
APP = "demo_loop"


def stop_when_in_range(callback_context: CallbackContext):
    """after_agent_callback that escalates the loop when the price fits.

    The haggler writes its latest proposal into state['proposal']. We parse
    it and, if it's between $450k and $470k, emit an Escalate action so
    LoopAgent terminates after this iteration.
    """
    raw = callback_context.state.get("proposal", "")
    digits = "".join(c for c in str(raw) if c.isdigit())
    try:
        price = int(digits)
    except ValueError:
        return None
    if 450_000 <= price <= 470_000:
        callback_context.actions.escalate = True
    return None


def build() -> LoopAgent:
    haggler = LlmAgent(
        name="haggler",
        model=MODEL,
        instruction=(
            "Propose a single integer dollar price between $440,000 and $480,000 "
            "for 742 Evergreen Terrace. Output ONLY the integer (e.g. 462000). "
            "Vary your answer each time you are called."
        ),
        output_key="proposal",
        after_agent_callback=stop_when_in_range,
    )
    return LoopAgent(
        name="haggle_loop",
        sub_agents=[haggler],
        max_iterations=5,
    )


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set"); return

    sessions = InMemorySessionService()
    session = await sessions.create_session(app_name=APP, user_id="demo", session_id="s1")
    runner = Runner(app_name=APP, agent=build(), session_service=sessions)

    iter_count = 0
    async for event in runner.run_async(
        user_id="demo",
        session_id=session.id,
        new_message=Content(role="user", parts=[Part(text="start")]),
    ):
        if event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts).strip()
            if text:
                iter_count += 1
                print(f"[iter {iter_count}] proposal={text}")
        if event.actions and event.actions.escalate:
            print("loop escalated -> stopping")


if __name__ == "__main__":
    asyncio.run(main())
