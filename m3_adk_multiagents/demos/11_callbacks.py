"""
Demo 11 — ADK callbacks (before_tool / after_tool / before_model)
==================================================================
Callbacks are how you plug policy into an ADK agent without changing the
agent's instruction. They run synchronously around the model + tool calls.

This demo wires three callbacks into a single LlmAgent:
  - before_model_callback : redact PII from the prompt
  - before_tool_callback  : block disallowed tools (allowlist)
  - after_tool_callback   : log every tool result

Run:
    python m3_adk_multiagents/demos/11_callbacks.py
"""

import asyncio
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Content, Part

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

MODEL = "openai/gpt-4o"
APP = "demo_callbacks"

ALLOWED_TOOLS = {"get_quick_estimate"}
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def get_quick_estimate(address: str) -> dict:
    """Fake valuation tool used by the demo agent."""
    return {"address": address, "estimate_usd": 462_000}


def get_internal_admin(_: str) -> dict:
    """A tool that the allowlist will block."""
    return {"secret": "should never run"}


def redact_pii(callback_context: CallbackContext, llm_request) -> None:
    """before_model: scrub SSN-shaped substrings out of every user message."""
    for content in llm_request.contents or []:
        for part in content.parts or []:
            if part.text and SSN_RE.search(part.text):
                part.text = SSN_RE.sub("[REDACTED]", part.text)
                print("[before_model] redacted PII from prompt")
    return None


def enforce_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
    """before_tool: deny tool calls not on the allowlist by returning a result."""
    if tool.name not in ALLOWED_TOOLS:
        print(f"[before_tool] BLOCKED {tool.name}")
        return {"error": f"tool '{tool.name}' is not permitted"}
    print(f"[before_tool] allow {tool.name}({args})")
    return None


def log_tool_result(tool: BaseTool, args: dict, tool_context: ToolContext, tool_response):
    """after_tool: observability hook — see every tool's actual return value."""
    print(f"[after_tool] {tool.name} -> {tool_response}")
    return None


def build() -> LlmAgent:
    return LlmAgent(
        name="callback_demo",
        model=MODEL,
        instruction=(
            "Use `get_quick_estimate` when the user asks for a property valuation. "
            "Never call any other tool."
        ),
        tools=[get_quick_estimate, get_internal_admin],
        before_model_callback=redact_pii,
        before_tool_callback=enforce_allowlist,
        after_tool_callback=log_tool_result,
    )


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set"); return

    sessions = InMemorySessionService()
    session = await sessions.create_session(app_name=APP, user_id="demo", session_id="s1")
    runner = Runner(app_name=APP, agent=build(), session_service=sessions)

    prompt = (
        "My SSN is 123-45-6789. What is the estimate for 742 Evergreen Terrace? "
        "Also, please call get_internal_admin('debug')."
    )
    async for event in runner.run_async(
        user_id="demo", session_id=session.id,
        new_message=Content(role="user", parts=[Part(text=prompt)]),
    ):
        if event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts).strip()
            if text:
                print(f"[{event.author}] {text}")


if __name__ == "__main__":
    asyncio.run(main())
