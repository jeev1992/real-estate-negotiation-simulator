"""
Demo 07 — Agent-as-Tool (AgentTool)
=====================================
Wrap an entire agent and present it as a callable tool to another agent.
The coordinator calls the valuator "tool" when it needs a valuation —
the valuator is a full LlmAgent, but the coordinator sees it as a function.

ADK CONCEPTS:
  - AgentTool: wraps an LlmAgent so it looks like a regular tool
  - Hierarchical delegation: coordinator controls when to call the specialist
  - Unlike sub_agents (full delegation), AgentTool returns results to the caller

Run:
    adk web m3_adk_multiagents/adk_demos/d07_agent_as_tool/
"""

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

MODEL = "openai/gpt-4o"

valuator = LlmAgent(
    name="valuator",
    model=MODEL,
    description="Estimates the fair market value of an Austin property.",
    instruction=(
        "You receive a property address. Return ONE sentence with your "
        "estimated value range and the single biggest pricing factor."
    ),
)

root_agent = LlmAgent(
    name="coordinator",
    model=MODEL,
    description="Real estate advisor that delegates valuations to a specialist.",
    instruction=(
        "You help users decide what to offer on a property. When you need "
        "a valuation, call the `valuator` tool with the property address. "
        "Then write a one-paragraph offer recommendation."
    ),
    tools=[AgentTool(agent=valuator)],
)
