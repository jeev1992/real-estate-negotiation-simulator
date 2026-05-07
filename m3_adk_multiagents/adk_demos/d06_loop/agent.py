"""
Demo 06 — LoopAgent
=====================
LoopAgent re-runs its sub-agents until max_iterations or an escalation.
A haggler proposes prices; the after_agent_callback checks if the price
is in the target range and escalates (breaks the loop) when it is.

ADK CONCEPTS:
  - LoopAgent: iterates sub-agents until a stop condition
  - after_agent_callback: runs after each agent turn
  - callback_context.actions.escalate = True: breaks the loop
  - output_key: captures each iteration's output in state

Run:
    adk web m3_adk_multiagents/adk_demos/d06_loop/
"""

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.agents.callback_context import CallbackContext

import os

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")


def stop_when_in_range(callback_context: CallbackContext):
    """Escalate (break the loop) when the proposed price is $450k–$470k."""
    raw = callback_context.state.get("proposal", "")
    digits = "".join(c for c in str(raw) if c.isdigit())
    try:
        price = int(digits)
    except ValueError:
        return None
    if 450_000 <= price <= 470_000:
        callback_context.actions.escalate = True
    return None


haggler = LlmAgent(
    name="haggler",
    model=MODEL,
    instruction=(
        "Propose a single integer dollar price between $440,000 and $480,000 "
        "for 742 Evergreen Terrace. Output ONLY the integer (e.g. 462000). "
        "Vary your answer each time you are called."
    ),
    output_key="proposal",
    after_agent_callback=stop_when_in_range,
)

root_agent = LoopAgent(
    name="haggle_loop",
    description="Iteratively propose prices until one lands in the target range.",
    sub_agents=[haggler],
    max_iterations=5,
)
