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
  - include_contents="none": the later agents see only the latest message
    (the previous agent's output) plus their instruction — not the user's
    request or older history. Without it every sub-agent reads the whole
    shared conversation.

Run:
    adk web m2_adk_multiagents/adk_demos/d04_sequential/
"""

from google.adk.agents import LlmAgent, SequentialAgent

import os

MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-4o")

market_brief = LlmAgent(
    name="market_brief",
    model=MODEL,
    instruction=(
        "You are the first step of a pipeline. Whatever the user's message says, "
        "your only job is this: write a 2-line market summary for the Austin 78701 "
        "ZIP, with a median price and typical days-on-market. You have no tools, so "
        "use your general knowledge and mark the figures as approximate. Don't ask "
        "questions and don't refuse."
    ),
    output_key="market_summary",
)

offer_drafter = LlmAgent(
    name="offer_drafter",
    model=MODEL,
    instruction=(
        "Market summary:\n<summary>\n{market_summary}\n</summary>\n\n"
        "Using that summary, draft a one-line opening buyer offer for "
        "742 Evergreen Terrace, listed at $485k — an opening offer, so below the "
        "asking price. Output ONLY the offer text."
    ),
    include_contents="none",
    output_key="offer_text",
)

polisher = LlmAgent(
    name="message_polisher",
    model=MODEL,
    instruction=(
        "Draft offer:\n<offer>\n{offer_text}\n</offer>\n\n"
        "Polish that offer into a professional one-paragraph email body "
        "suitable to send to the listing agent."
    ),
    include_contents="none",
    output_key="final_email",
)

root_agent = SequentialAgent(
    name="negotiation_pipeline",
    description="Three-stage pipeline: research → draft → polish.",
    sub_agents=[market_brief, offer_drafter, polisher],
)
