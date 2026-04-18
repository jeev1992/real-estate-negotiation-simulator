"""
Demo 10 — ToolContext: state, artifacts, and actions
=====================================================
A function tool can take an extra `tool_context: ToolContext` parameter that
ADK populates automatically. Through it, the tool can:
  - read/write session state (with scope prefixes: app:, user:, temp:)
  - save and load artifacts (binary blobs the agent can refer to later)
  - request escalation, transfer_to_agent, or skip_summarization

This demo writes a counter into user-scoped state across two turns and
shows the value persisting per user across sessions.

Run:
    python m3_adk_multiagents/demos/10_tool_context.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Content, Part

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

MODEL = "openai/gpt-4o"
APP = "demo_tool_context"


def bump_offer_counter(tool_context: ToolContext) -> dict:
    """Increment a per-user counter and return its new value.

    The "user:" prefix scopes the key to the user_id, so it survives
    across sessions for the same user.
    """
    current = tool_context.state.get("user:offer_attempts", 0)
    tool_context.state["user:offer_attempts"] = current + 1
    return {"offer_attempts": current + 1}


def build() -> LlmAgent:
    return LlmAgent(
        name="offer_counter",
        model=MODEL,
        instruction=(
            "When the user asks how many times they have made an offer, call "
            "`bump_offer_counter` and report the new count from its result."
        ),
        tools=[bump_offer_counter],
    )


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set"); return

    sessions = InMemorySessionService()
    runner = Runner(app_name=APP, agent=build(), session_service=sessions)

    user = "alice"
    for turn, sid in enumerate(["s1", "s2", "s3"], start=1):
        await sessions.create_session(app_name=APP, user_id=user, session_id=sid)
        print(f"\n--- turn {turn} (session {sid}) ---")
        async for event in runner.run_async(
            user_id=user, session_id=sid,
            new_message=Content(role="user", parts=[Part(text="How many offers so far?")]),
        ):
            if event.content and event.content.parts:
                text = "".join(p.text or "" for p in event.content.parts).strip()
                if text:
                    print(f"[{event.author}] {text}")


if __name__ == "__main__":
    asyncio.run(main())
