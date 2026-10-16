"""
Demo 03 (terminal) — Many users, one session database
=======================================================
The adk web UI always runs as a single user ("user"), so it can't show what
happens when several people use the same agent. This script can: it drives
the d03 agent as different users, writing to the SAME SQLite file adk web
uses (d03_sessions_state/.adk/session.db), then prints the database tables.

Scenario:
    alice  session 1   offers $430,000, then $445,000
    bob    session 1   offers $440,000
    alice  session 2   offers $450,000 (a brand-new conversation)

In class, run it AFTER the single-user adk web walkthrough and WITHOUT
--reset: alice and bob are added to the same database, so the tables show
the class's own "user" rows next to theirs, and app: totals include everyone.

What to look for in the output:
    sessions     one row per (user, session) — offer_history differs per row
    user_states  one row per user — each user's own lifetime total
    app_states   ONE row for the agent — every user's offers combined

Run:
    python m2_adk_multiagents/adk_demos/d03_sessions_state/run_multi_user.py
    python m2_adk_multiagents/adk_demos/d03_sessions_state/run_multi_user.py --reset   # wipe the DB first

Stop adk web before running the script (and always before --reset).
"""

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.genai import types

_AGENT_DIR = Path(__file__).resolve().parent
_DEMOS_DIR = _AGENT_DIR.parent
load_dotenv(_DEMOS_DIR.parents[1] / ".env")
sys.path.insert(0, str(_DEMOS_DIR))
from d03_sessions_state.agent import root_agent  # noqa: E402

# Same app name and DB file that adk web uses for this agent.
APP_NAME = "d03_sessions_state"
DB_PATH = _AGENT_DIR / ".adk" / "session.db"

SCENARIO = [
    ("alice", 1, "I offer $430,000."),
    ("alice", 1, "I offer $445,000."),
    ("bob", 1, "I offer $440,000."),
    ("alice", 2, "I offer $450,000."),
]


async def play(runner: Runner) -> None:
    session_ids: dict[tuple[str, int], str] = {}
    for user_id, n, text in SCENARIO:
        if (user_id, n) not in session_ids:
            session = await runner.session_service.create_session(app_name=APP_NAME, user_id=user_id)
            session_ids[(user_id, n)] = session.id
            print(f"\n{user_id}: new session {n} ({session.id[:8]})")
        message = types.Content(role="user", parts=[types.Part(text=text)])
        async for event in runner.run_async(
            user_id=user_id, session_id=session_ids[(user_id, n)], new_message=message
        ):
            for part in (event.content.parts if event.content else None) or []:
                if part.function_response and part.function_response.name == "record_offer":
                    print(f"  {text:20} -> {json.dumps(part.function_response.response)}")


def show_tables() -> None:
    with sqlite3.connect(DB_PATH) as db:
        print("\n" + "=" * 78)
        print(f"ONE DATABASE FOR EVERY USER: {DB_PATH}")
        print("=" * 78)

        print("\nsessions  (no prefix — one row per user per conversation)")
        for user_id, sid, state in db.execute(
            "SELECT user_id, id, state FROM sessions WHERE app_name=? ORDER BY user_id, create_time",
            (APP_NAME,),
        ):
            print(f"  {user_id:8} {sid[:8]}  {state}")

        print("\nuser_states  (user: prefix — one row per user, prefix stripped)")
        for user_id, state in db.execute(
            "SELECT user_id, state FROM user_states WHERE app_name=? ORDER BY user_id", (APP_NAME,)
        ):
            print(f"  {user_id:8} {state}")

        print("\napp_states  (app: prefix — ONE row shared by all users, prefix stripped)")
        for (state,) in db.execute("SELECT state FROM app_states WHERE app_name=?", (APP_NAME,)):
            print(f"  {state}")

        print("\nevents per user (full conversation history, same table for everyone)")
        for user_id, count in db.execute(
            "SELECT user_id, COUNT(*) FROM events WHERE app_name=? GROUP BY user_id ORDER BY user_id",
            (APP_NAME,),
        ):
            print(f"  {user_id:8} {count} events")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the d03 agent as several users on one session DB.")
    parser.add_argument("--reset", action="store_true", help="Delete the session DB first (stop adk web before using).")
    args = parser.parse_args()

    if args.reset and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Deleted {DB_PATH}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=SqliteSessionService(db_path=str(DB_PATH)),
    )
    try:
        await play(runner)
    finally:
        await runner.close()
    show_tables()
    print(
        "\nNext: adk web m2_adk_multiagents/adk_demos/ → d03_sessions_state → New Session → \"I offer $452,000\".\n"
        "The UI runs as user 'user': the new session's offer_history starts empty, user:total_offers "
        "continues from user's own earlier offers, and app:total_offers includes every user above."
    )


if __name__ == "__main__":
    asyncio.run(main())
