"""
Demo 04 — SequentialAgent
==========================
Three sub-agents chained in declaration order.  Each writes to session
state via output_key; the next agent reads it via {placeholder} syntax.

Pipeline:  market_brief  →  offer_drafter  →  message_polisher

ADK CONCEPTS:
  - SequentialAgent: runs children in order, stops when the last finishes
  - output_key: each agent writes its output to a named state key
  - {state_key} in instructions: agents read prior outputs from state

Run:
    adk web m3_adk_multiagents/adk_demos/d04_sequential/
"""

from google.adk.agents import LlmAgent, SequentialAgent

import os

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

market_brief = LlmAgent(
    name="market_brief",
    model=MODEL,
    instruction=(
        "Write a 2-line market summary for the Austin 78701 ZIP. "
        "Include median price and days-on-market. Be concrete."
    ),
    output_key="market_summary",
)

offer_drafter = LlmAgent(
    name="offer_drafter",
    model=MODEL,
    instruction=(
        "Read {market_summary} and draft a one-line opening buyer offer "
        "for 742 Evergreen Terrace listed at $485k. Output ONLY the offer text."
    ),
    output_key="offer_text",
)

polisher = LlmAgent(
    name="message_polisher",
    model=MODEL,
    instruction=(
        "Polish {offer_text} into a professional one-paragraph email body "
        "suitable to send to the listing agent."
    ),
    output_key="final_email",
)

root_agent = SequentialAgent(
    name="negotiation_pipeline",
    description="Three-stage pipeline: research → draft → polish.",
    sub_agents=[market_brief, offer_drafter, polisher],
)
