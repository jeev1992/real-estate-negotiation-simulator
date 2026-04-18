"""
Demo 07 — ADK ParallelAgent
============================
Three sub-agents run concurrently and write into different state keys.
Useful for fan-out research (different signals for the same decision).

Run:
    python m3_adk_multiagents/demos/07_parallel_agent.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, ParallelAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

MODEL = "openai/gpt-4o"
APP = "demo_parallel"


def build() -> ParallelAgent:
    schools = LlmAgent(
        name="schools_signal",
        model=MODEL,
        instruction="One sentence on Austin ISD school quality near 78701.",
        output_key="schools",
    )
    comps = LlmAgent(
        name="comps_signal",
        model=MODEL,
        instruction="One sentence on recent comparable home sales near 78701.",
        output_key="comps",
    )
    inventory = LlmAgent(
        name="inventory_signal",
        model=MODEL,
        instruction="One sentence on current housing inventory pressure in 78701.",
        output_key="inventory",
    )
    return ParallelAgent(
        name="market_signals",
        sub_agents=[schools, comps, inventory],
    )


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set"); return

    sessions = InMemorySessionService()
    session = await sessions.create_session(app_name=APP, user_id="demo", session_id="s1")
    runner = Runner(app_name=APP, agent=build(), session_service=sessions)

    async for event in runner.run_async(
        user_id="demo",
        session_id=session.id,
        new_message=Content(role="user", parts=[Part(text="gather signals")]),
    ):
        if event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts).strip()
            if text:
                print(f"[{event.author}] {text}\n")

    final = await sessions.get_session(app_name=APP, user_id="demo", session_id=session.id)
    print("--- merged session state (set in parallel) ---")
    for k, v in final.state.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
