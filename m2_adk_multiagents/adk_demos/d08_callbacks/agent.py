"""
Demo 08 — Callbacks: deterministic policy around the agent, model, and tools
=============================================================================
Five hooks, in the order they fire during a turn. None of the policies
below is in the agent's instruction — the prompt doesn't even forbid the
admin tool. The callbacks enforce them anyway.

  before_agent_callback  — agent-level: count turns. The only hooks that
                           workflow agents (Loop/Sequential/Parallel) have too.
  before_model_callback  — input guardrail: redact SSNs before the LLM sees them.
  before_tool_callback   — access control: block get_internal_admin, even
                           though its description invites the model to use it.
  after_tool_callback    — data filtering: strip the confidential
                           seller_floor_usd field from tool results.
  after_model_callback   — output guardrail: remove phone numbers from the
                           reply, wherever they came from.

Return-value rules:
  - None              → continue normally
  - before_tool dict  → the tool is skipped; the dict becomes its result
  - after_tool dict   → replaces the tool's result
  - before_model LlmResponse → the LLM call is skipped (see the ex05 solution)
  - after_model LlmResponse  → replaces the model's response

Every callback prints to the terminal AND appends to state["callback_audit"],
so you can watch them fire in the adk web State tab.

Run:
    adk web m2_adk_multiagents/adk_demos/
"""

import os
import re

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

ALLOWED_TOOLS = {"get_quick_estimate"}
CONFIDENTIAL_FIELDS = {"seller_floor_usd"}
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"(?:\(\d{3}\)\s?|\b\d{3}[-.\s])\d{3}[-.\s]\d{4}\b")


# ── Tools ─────────────────────────────────────────────────────────────────


def get_quick_estimate(address: str) -> dict:
    """Return a rough market estimate and the listing agent for a property address."""
    return {
        "address": address,
        "estimate_usd": 462_000,
        "listing_agent": "Jane Doe, (512) 555-0143",
        "seller_floor_usd": 445_000,  # confidential — after_tool strips it
    }


def get_internal_admin(query: str) -> dict:
    """Internal admin lookup: seller records, minimum prices, and owner details
    for any property. Use this for questions about a seller's minimum price."""
    return {"secret": "should never run"}


# ── Callbacks ─────────────────────────────────────────────────────────────


def _audit(ctx, hook: str, message: str) -> None:
    """Print and record each callback firing so it shows up in the State tab."""
    print(f"[{hook}] {message}")
    ctx.state["callback_audit"] = ctx.state.get("callback_audit", []) + [f"{hook}: {message}"]


def count_turns(callback_context: CallbackContext):
    """before_agent: runs once per turn, before any model or tool call."""
    turn = callback_context.state.get("turn_count", 0) + 1
    callback_context.state["turn_count"] = turn
    _audit(callback_context, "before_agent", f"turn {turn} started")
    return None


def redact_pii(callback_context: CallbackContext, llm_request: LlmRequest):
    """before_model: scrub SSN-shaped strings from the request sent to the LLM.

    The request is a copy, so the session history keeps the original text —
    which is why this redaction repeats on every later model call.
    """
    redacted = 0
    for content in llm_request.contents or []:
        for part in content.parts or []:
            if part.text and SSN_RE.search(part.text):
                part.text = SSN_RE.sub("[REDACTED-SSN]", part.text)
                redacted += 1
    if redacted:
        _audit(callback_context, "before_model", f"redacted SSN in {redacted} message(s)")
    return None


def enforce_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
    """before_tool: deny tools not on the allowlist."""
    if tool.name not in ALLOWED_TOOLS:
        _audit(tool_context, "before_tool", f"BLOCKED {tool.name}({args})")
        return {"error": f"tool '{tool.name}' is not permitted for this agent"}
    _audit(tool_context, "before_tool", f"allowed {tool.name}")
    return None


def strip_confidential(
    tool: BaseTool, args: dict, tool_context: ToolContext, tool_response
):
    """after_tool: remove confidential fields before the LLM sees the result."""
    if isinstance(tool_response, dict) and CONFIDENTIAL_FIELDS & tool_response.keys():
        removed = sorted(CONFIDENTIAL_FIELDS & tool_response.keys())
        _audit(tool_context, "after_tool", f"stripped {removed} from {tool.name}")
        return {k: v for k, v in tool_response.items() if k not in CONFIDENTIAL_FIELDS}
    return None


def scrub_reply(callback_context: CallbackContext, llm_response: LlmResponse):
    """after_model: never let a phone number leave the agent, whatever its source."""
    parts = llm_response.content.parts if llm_response.content else None
    changed = False
    for part in parts or []:
        if part.text and PHONE_RE.search(part.text):
            part.text = PHONE_RE.sub("[phone removed]", part.text)
            changed = True
    if changed:
        _audit(callback_context, "after_model", "removed phone number(s) from the reply")
        return llm_response
    return None


# ── Agent ─────────────────────────────────────────────────────────────────

root_agent = LlmAgent(
    name="callback_demo",
    model=MODEL,
    description="Demo agent with input/output guardrails, a tool allowlist, and result filtering.",
    instruction=(
        "You are a real estate assistant. Use your tools to answer questions "
        "about property values, sellers, and listing agents."
    ),
    tools=[get_quick_estimate, get_internal_admin],
    before_agent_callback=count_turns,
    before_model_callback=redact_pii,
    before_tool_callback=enforce_allowlist,
    after_tool_callback=strip_confidential,
    after_model_callback=scrub_reply,
)
