"""
Negotiation Orchestrator — Idiomatic ADK
==========================================
LoopAgent wrapping a SequentialAgent (buyer → seller) to run multi-round
negotiation. Demonstrates: LoopAgent, SequentialAgent, output_key state
passing, after_agent_callback with escalation.

Run with:
    adk web m3_adk_multiagents/negotiation_agents/
"""

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext

MODEL = "openai/gpt-4o"


def _check_agreement(callback_context: CallbackContext):
    """After the seller responds, check if they accepted. Escalate to stop."""
    response = str(callback_context.state.get("seller_response", "")).upper()
    if "ACCEPT" in response:
        callback_context.actions.escalate = True
    return None


buyer = LlmAgent(
    name="buyer",
    model=MODEL,
    instruction=(
        "You are a buyer for 742 Evergreen Terrace (listed $485,000).\n"
        "Budget: $460,000 max. Target: $445k–$455k.\n\n"
        "Round 1: offer ~$425,000. Each round: increase by 2–4%%.\n"
        "If the seller has responded, read {seller_response} and adjust.\n"
        "Walk away if seller won't go below $460,000.\n\n"
        "Write your offer as a dollar amount with brief justification."
    ),
    output_key="buyer_offer",
)

seller = LlmAgent(
    name="seller",
    model=MODEL,
    instruction=(
        "You are the seller of 742 Evergreen Terrace (listed $485,000).\n"
        "Minimum acceptable price: $445,000.\n\n"
        "Read {buyer_offer}. If the offer is >= $445,000, respond with ACCEPT "
        "and the agreed price. Otherwise counter-offer.\n"
        "Start counter at $477k, drop $5k–$8k per round.\n"
        "NEVER go below $445,000.\n\n"
        "Write ACCEPT <price> or COUNTER <price> with justification."
    ),
    output_key="seller_response",
    after_agent_callback=_check_agreement,
)

negotiation_round = SequentialAgent(
    name="round",
    sub_agents=[buyer, seller],
)

root_agent = LoopAgent(
    name="negotiation",
    description="Multi-round buyer ↔ seller negotiation for 742 Evergreen Terrace.",
    sub_agents=[negotiation_round],
    max_iterations=5,
)
