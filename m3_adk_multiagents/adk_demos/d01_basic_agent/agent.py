"""
Demo 01 — Basic LlmAgent
==========================
The simplest ADK agent: one LlmAgent with one function tool.
No MCP, no orchestration — just an agent that can call a tool.

ADK CONCEPTS:
  - LlmAgent: the core building block
  - Function tools: plain Python functions the LLM can call
  - root_agent: the variable adk web discovers

Run:
    adk web m3_adk_multiagents/adk_demos/d01_basic_agent/
"""

from google.adk.agents import LlmAgent


def get_quick_estimate(address: str) -> dict:
    """Return a rough market estimate for a property address."""
    estimates = {
        "742 Evergreen Terrace": {"estimate_usd": 462_000, "confidence": "high"},
        "123 Main St": {"estimate_usd": 380_000, "confidence": "medium"},
    }
    for key, value in estimates.items():
        if key.lower() in address.lower():
            return {"address": address, **value}
    return {"address": address, "estimate_usd": 450_000, "confidence": "low"}


root_agent = LlmAgent(
    name="basic_agent",
    model="openai/gpt-4o",
    description="A simple real estate assistant that estimates property values.",
    instruction=(
        "You are a helpful real estate assistant. When asked about a property, "
        "use the get_quick_estimate tool to look up its value, then give a "
        "brief summary including the estimate and confidence level."
    ),
    tools=[get_quick_estimate],
)
