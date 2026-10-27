"""
Demo 09 (terminal) — Print the ADK event stream
=================================================
`adk web` hides the Runner from you. This script drives the SAME root_agent
from agent.py with an explicit Runner and prints every Event that
Runner.run_async() yields, so you can see the stream the web UI is built on.

For each Event it prints:
  - author               who produced it (the agent's name)
  - function_call        the model asking ADK to run a tool (name + args)
  - function_response    the tool's return value fed back to the model
  - text                 model text output
  - state_delta          session-state keys changed by this step
  - escalate / transfer  control-flow signals (loops, agent hand-offs)
  - final_response       True when an event ends an agent's step — here, the
                         turn's last text answer

After each turn it reloads the session and prints the accumulated state,
so you can watch `offer_count` grow across turns.

Run:
    python m2_adk_multiagents/adk_demos/d09_event_stream/run_event_stream.py

    # Custom turns (each argument is one user message, same session):
    python m2_adk_multiagents/adk_demos/d09_event_stream/run_event_stream.py \\
        "What should I offer on 742 Evergreen Terrace?" "Try 123 Main St"

    # Also dump every Event as raw JSON:
    python m2_adk_multiagents/adk_demos/d09_event_stream/run_event_stream.py --raw
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.genai import types

_DEMOS_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")

sys.path.insert(0, str(_DEMOS_DIR))
from d09_event_stream.agent import root_agent  # noqa: E402

# Matches the package folder name, which is the app name `adk web` uses.
APP_NAME = "d09_event_stream"
USER_ID = "demo_user"

DEFAULT_TURNS = [
    "What should I offer on 742 Evergreen Terrace, Austin, TX 78701?",
    "Now do the same for 123 Main St, Austin, TX.",
]


def _compact(value, limit: int = 320) -> str:
    text = json.dumps(value, default=str)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def print_event(index: int, event: Event, raw: bool) -> None:
    print(f"\n  [Event {index}] author={event.author}  "
          f"final_response={event.is_final_response()}")

    for part in (event.content.parts if event.content else None) or []:
        if part.function_call:
            call = part.function_call
            print(f"    function_call      {call.name}({_compact(call.args)})")
        elif part.function_response:
            resp = part.function_response
            print(f"    function_response  {resp.name} -> {_compact(resp.response)}")
        elif part.text and part.text.strip():
            print(f"    text               {part.text.strip()}")

    actions = event.actions
    if actions.state_delta:
        print(f"    state_delta        {_compact(actions.state_delta)}")
    if actions.escalate:
        print("    escalate           True")
    if actions.transfer_to_agent:
        print(f"    transfer_to_agent  {actions.transfer_to_agent}")
    if event.error_message:
        print(f"    error              {event.error_message}")

    if raw:
        print(event.model_dump_json(indent=2, exclude_none=True))


async def run(turns: list[str], raw: bool) -> None:
    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )
    print(f"Session {session.id} created (state={session.state})")

    try:
        for turn_number, text in enumerate(turns, 1):
            print("\n" + "=" * 70)
            print(f"TURN {turn_number}  user: {text}")
            print("=" * 70)

            message = types.Content(role="user", parts=[types.Part(text=text)])
            yielded = 0
            async for event in runner.run_async(
                user_id=USER_ID, session_id=session.id, new_message=message
            ):
                yielded += 1
                print_event(yielded, event, raw)

            session = await runner.session_service.get_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=session.id
            )
            print(f"\n  -> run_async yielded {yielded} events this turn. "
                  f"The session now stores {len(session.events)} events in total "
                  f"(your user messages are stored too, but are not yielded).")
            print(f"  -> session state: {_compact(session.state, limit=400)}")
    finally:
        await runner.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the ADK event stream for demo 09.")
    parser.add_argument("turns", nargs="*", help="User messages to send, in order (same session).")
    parser.add_argument("--raw", action="store_true", help="Also print each Event as raw JSON.")
    args = parser.parse_args()
    # Model text and user messages can contain characters (→, …) that a
    # redirected Windows console (cp1252) can't encode.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set (add it to .env or your environment).")
        sys.exit(1)

    asyncio.run(run(args.turns or DEFAULT_TURNS, args.raw))


if __name__ == "__main__":
    main()
