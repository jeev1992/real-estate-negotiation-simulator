"""
ADK Orchestrator Agents Demo
============================
Demonstrates LoopAgent orchestration using only buyer and seller ADK agents.

This keeps the demo aligned with negotiation semantics:
    - buyer_agent and seller_agent are the only sub-agents
    - LoopAgent is the orchestrator
    - max_iterations controls negotiation rounds

Usage:
    # No API calls. Verifies LoopAgent + buyer/seller object construction only.
  python m4_adk_multiagents/bonus/adk_orchestrator_agents_demo.py --check

    # Optional live run (requires GOOGLE_API_KEY)
    python m4_adk_multiagents/bonus/adk_orchestrator_agents_demo.py --run --max-iterations 3
"""

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


MODEL = "gemini-2.0-flash"
APP_NAME = "adk_orchestrator_demo"


def build_buyer_seller_loop(max_iterations: int) -> tuple[LlmAgent, LlmAgent, LoopAgent]:
    buyer_agent = LlmAgent(
        name="buyer_agent",
        model=MODEL,
        description="Buyer side of the negotiation",
        instruction=(
            "You are the buyer agent. Propose a concise offer update. "
            "Stay at or below $460,000 and justify with one short rationale."
        ),
    )

    seller_agent = LlmAgent(
        name="seller_agent",
        model=MODEL,
        description="Seller side of the negotiation",
        instruction=(
            "You are the seller agent. Propose a concise counter or acceptance decision. "
            "Never go below $445,000."
        ),
    )

    loop_agent = LoopAgent(
        name="buyer_seller_loop",
        description="Loop orchestration for buyer/seller negotiation rounds",
        sub_agents=[buyer_agent, seller_agent],
        max_iterations=max_iterations,
    )

    return buyer_agent, seller_agent, loop_agent


def run_check_mode(max_iterations: int) -> None:
    buyer_agent, seller_agent, loop_agent = build_buyer_seller_loop(max_iterations=max_iterations)

    print("ADK orchestrator demo check")
    print("- LlmAgent + LoopAgent import: OK")
    print("- Buyer/Seller agents created:\n")
    print(f"  [buyer]  {buyer_agent.__class__.__name__}: {buyer_agent.name}")
    print(f"  [seller] {seller_agent.__class__.__name__}: {seller_agent.name}")
    print(f"  [loop]   {loop_agent.__class__.__name__}: {loop_agent.name}")
    print(f"\nLoop max_iterations: {max_iterations}")


async def run_live(prompt: str, max_iterations: int) -> None:
    if not os.environ.get("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY is required for --run")
        sys.exit(1)

    _, _, root_agent = build_buyer_seller_loop(max_iterations=max_iterations)
    session_id = f"orchestrator_demo_{uuid.uuid4().hex[:8]}"

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id="demo_user",
        session_id=session_id,
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    print(f"\nRunning: buyer/seller loop ({root_agent.__class__.__name__})")
    print(f"Max iterations: {max_iterations}")
    print(f"Prompt: {prompt}\n")

    content = Content(parts=[Part(text=prompt)])
    final_text = ""

    async for event in runner.run_async(
        user_id="demo_user",
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_text += part.text

    print("Final response:")
    print(final_text.strip() or "<empty>")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Google ADK orchestrator agents demo")
    parser.add_argument("--check", action="store_true", help="Validate buyer/seller LoopAgent construction only")
    parser.add_argument("--run", action="store_true", help="Optionally run the buyer/seller LoopAgent live")
    parser.add_argument("--max-iterations", type=int, default=3, help="LoopAgent max iterations (default: 3)")
    parser.add_argument(
        "--prompt",
        type=str,
        default="Run a short buyer/seller negotiation iteration and return concise outcome notes.",
        help="Prompt for --run mode",
    )
    args = parser.parse_args()

    if args.max_iterations < 1:
        print("ERROR: --max-iterations must be >= 1")
        sys.exit(1)

    if args.check or not args.run:
        run_check_mode(max_iterations=args.max_iterations)
        if not args.run:
            return

    await run_live(prompt=args.prompt, max_iterations=args.max_iterations)


if __name__ == "__main__":
    asyncio.run(main())
