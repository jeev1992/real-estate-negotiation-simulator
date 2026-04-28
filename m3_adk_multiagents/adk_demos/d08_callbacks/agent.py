"""
Demo 08 — Callbacks (before_tool / after_tool / before_model)
==============================================================
Policy hooks injected without changing the agent's instructions.
Three callbacks demonstrate security, access control, and observability:
  - before_model_callback: redact PII (SSNs) from prompts
  - before_tool_callback: block disallowed tools (allowlist)
  - after_tool_callback: log every tool result for observability

ADK CONCEPTS:
  - Callbacks run synchronously around model + tool calls
  - before_tool returning a dict short-circuits the tool (returns that dict)
  - before_tool returning None allows the call to proceed
  - Callbacks are how you enforce policy without prompt-engineering it

Run:
    adk web m3_adk_multiagents/adk_demos/d08_callbacks/
"""

import re

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

MODEL = "openai/gpt-4o"
ALLOWED_TOOLS = {"get_quick_estimate"}
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def get_quick_estimate(address: str) -> dict:
    """Return a rough market estimate for a property address."""
    return {"address": address, "estimate_usd": 462_000}


def get_internal_admin(query: str) -> dict:
    """An internal tool the allowlist will block."""
    return {"secret": "should never run"}


# ── Callbacks ─────────────────────────────────────────────────────────────


def redact_pii(callback_context: CallbackContext, llm_request) -> None:
    """before_model: scrub SSN-shaped strings from every user message."""
    for content in llm_request.contents or []:
        for part in content.parts or []:
            if part.text and SSN_RE.search(part.text):
                part.text = SSN_RE.sub("[REDACTED]", part.text)
                print("[before_model] redacted PII from prompt")
    return None


def enforce_allowlist(
    tool: BaseTool, args: dict, tool_context: ToolContext
):
    """before_tool: deny tools not on the allowlist."""
    if tool.name not in ALLOWED_TOOLS:
        print(f"[before_tool] BLOCKED {tool.name}")
        return {"error": f"tool '{tool.name}' is not permitted"}
    print(f"[before_tool] allow {tool.name}({args})")
    return None


def log_tool_result(
    tool: BaseTool, args: dict, tool_context: ToolContext, tool_response
):
    """after_tool: observability hook — log every tool return value."""
    print(f"[after_tool] {tool.name} -> {tool_response}")
    return None


# ── Agent ─────────────────────────────────────────────────────────────────

root_agent = LlmAgent(
    name="callback_demo",
    model=MODEL,
    description="Demo agent with PII redaction, tool allowlisting, and logging.",
    instruction=(
        "Use `get_quick_estimate` when the user asks for a property valuation. "
        "Never call any other tool."
    ),
    tools=[get_quick_estimate, get_internal_admin],
    before_model_callback=redact_pii,
    before_tool_callback=enforce_allowlist,
    after_tool_callback=log_tool_result,
)
