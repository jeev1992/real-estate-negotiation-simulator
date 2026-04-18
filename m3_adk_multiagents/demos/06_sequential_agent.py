"""
Demo 06 — ADK SequentialAgent
==============================
Three sub-agents chained together. Each produces output that the next reads
from session state. SequentialAgent is the simplest workflow primitive in
ADK — it runs children in declaration order and stops when the last finishes.

Pipeline: market_brief -> offer_drafter -> message_polisher

Run:
    python m3_adk_multiagents/demos/06_sequential_agent.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

MODEL = "openai/gpt-4o"
APP = "demo_sequential"


def build() -> SequentialAgent:
    market_brief = LlmAgent(
        name="market_brief",
        model=MODEL,
        instruction=(
            "Write a 2-line market summary for the Austin 78701 ZIP. "
            "Be concrete and specific."
        ),
        output_key="market_summary",
    )

    offer_drafter = LlmAgent(
        name="offer_drafter",
        model=MODEL,
        instruction=(
            "Read {market_summary} and draft a one-line opening buyer offer "
            "for 742 Evergreen Terrace listed at $485k. Output ONLY the offer text."
        ),
        output_key="offer_text",
    )

    polisher = LlmAgent(
        name="message_polisher",
        model=MODEL,
        instruction=(
            "Polish {offer_text} into a professional one-paragraph email body."
        ),
        output_key="final_email",
    )

    return SequentialAgent(
        name="negotiation_pipeline",
        sub_agents=[market_brief, offer_drafter, polisher],
    )


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set"); return

    pipeline = build()
    sessions = InMemorySessionService()
    session = await sessions.create_session(app_name=APP, user_id="demo", session_id="s1")
    runner = Runner(app_name=APP, agent=pipeline, session_service=sessions)

    async for event in runner.run_async(
        user_id="demo",
        session_id=session.id,
        new_message=Content(role="user", parts=[Part(text="kick off")]),
    ):
        if event.content and event.content.parts:
            who = event.author or "?"
            text = "".join(p.text or "" for p in event.content.parts).strip()
            if text:
                print(f"[{who}] {text}\n")

    final = await sessions.get_session(app_name=APP, user_id="demo", session_id=session.id)
    print("--- final session state ---")
    for k, v in final.state.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
