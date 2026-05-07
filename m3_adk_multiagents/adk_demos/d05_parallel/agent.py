"""
Demo 05 — ParallelAgent
=========================
Three sub-agents run concurrently, each writing to a different state key.
Useful for fan-out research — gathering multiple independent signals.

ADK CONCEPTS:
  - ParallelAgent: runs all children concurrently (not sequentially)
  - Each child writes to its own output_key — no conflicts
  - All results land in session state for a downstream agent to consume

Run:
    adk web m3_adk_multiagents/adk_demos/d05_parallel/
"""

from google.adk.agents import LlmAgent, ParallelAgent

import os

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

schools = LlmAgent(
    name="schools_signal",
    model=MODEL,
    instruction="One sentence on Austin ISD school quality near 78701.",
    output_key="schools",
)

comps = LlmAgent(
    name="comps_signal",
    model=MODEL,
    instruction="One sentence on recent comparable home sales near 78701.",
    output_key="comps",
)

inventory = LlmAgent(
    name="inventory_signal",
    model=MODEL,
    instruction="One sentence on current housing inventory pressure in 78701.",
    output_key="inventory",
)

root_agent = ParallelAgent(
    name="market_signals",
    description="Gather school, comp, and inventory signals concurrently.",
    sub_agents=[schools, comps, inventory],
)
