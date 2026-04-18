"""
Demo 09 — Agent-as-Tool (AgentTool)
====================================
ADK lets you wrap a whole agent and present it to another agent as if it
were a single tool. The "specialist" agent here acts like a callable
function the "coordinator" agent can invoke.

This is the foundation for nested expert hierarchies (an agent that knows
when to delegate to another agent) without the routing complexity of full
sub-agent orchestration.

Run:
    python m3_adk_multiagents/demos/09_agent_as_tool.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.agent_tool import AgentTool
from google.genai.types import Content, Part

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

MODEL = "openai/gpt-4o"
APP = "demo_agent_as_tool"


def build() -> LlmAgent:
    # Specialist: takes a property address and returns a one-line valuation
    # opinion. It has no tools of its own — pure LLM logic.
    valuator = LlmAgent(
        name="valuator",
        model=MODEL,
        description="Estimates the fair market value of an Austin property.",
        instruction=(
            "You receive a property address. Return ONE sentence with your "
            "estimated value range and the single biggest pricing factor."
        ),
    )

    # Coordinator: gets a high-level user request, decides when to call the
    # valuator. AgentTool exposes the valuator as a normal function tool.
    coordinator = LlmAgent(
        name="coordinator",
        model=MODEL,
        instruction=(
            "You help users decide what to offer on a property. When you need "
            "a valuation, call the `valuator` tool with the property address. "
            "Then write a one-paragraph offer recommendation."
        ),
        tools=[AgentTool(agent=valuator)],
    )
    return coordinator


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set"); return

    sessions = InMemorySessionService()
    session = await sessions.create_session(app_name=APP, user_id="demo", session_id="s1")
    runner = Runner(app_name=APP, agent=build(), session_service=sessions)

    async for event in runner.run_async(
        user_id="demo",
        session_id=session.id,
        new_message=Content(
            role="user",
            parts=[Part(text="I'm thinking about offering on 742 Evergreen Terrace, Austin TX 78701. What should I do?")],
        ),
    ):
        if event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts).strip()
            if text:
                print(f"[{event.author}] {text}\n")


if __name__ == "__main__":
    asyncio.run(main())
