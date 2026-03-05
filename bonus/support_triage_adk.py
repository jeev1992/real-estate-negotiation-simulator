"""
Customer Support Triage System -- Google ADK version.

Demonstrates:
  - LlmAgent with sub_agents (orchestrator pattern)
  - Implicit LLM-based routing via agent_transfer
  - Runner + InMemorySessionService lifecycle
  - Collecting final response from async event stream

Compare with support_triage_langgraph.py to see how the same problem
is solved with explicit (LangGraph) vs. implicit (ADK) routing.

Run:
    python bonus/support_triage_adk.py

Requires:
    GOOGLE_API_KEY in environment or .env
"""

import asyncio
import os

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part


# ── Specialist Agents ─────────────────────────────────────────────────────────
# Each agent is a config object: model + instruction + optional tools/sub_agents.
# No Python routing code needed here -- the orchestrator's LLM decides who to call.

billing_agent = LlmAgent(
    name="billing_agent",
    model="gemini-2.0-flash",
    instruction=(
        "You are a billing support specialist at a SaaS company.\n"
        "Your domain: charges, refunds, invoices, subscriptions, payment methods.\n\n"
        "When a customer ticket is delegated to you:\n"
        "1. Acknowledge the issue with empathy\n"
        "2. Explain what you can do to help\n"
        "3. Provide specific action steps or resolution in 2-3 paragraphs\n\n"
        "Respond directly to the customer. "
        "Do not ask clarifying questions -- work with the information given."
    ),
)

technical_agent = LlmAgent(
    name="technical_agent",
    model="gemini-2.0-flash",
    instruction=(
        "You are a technical support specialist at a SaaS company.\n"
        "Your domain: bugs, errors, crashes, system issues, feature questions.\n\n"
        "When a customer ticket is delegated to you:\n"
        "1. Acknowledge the technical issue\n"
        "2. Provide numbered troubleshooting steps\n"
        "3. If likely a known issue, mention what the team is working on\n\n"
        "Respond directly to the customer. "
        "Be precise and actionable. "
        "Do not ask clarifying questions -- work with the information given."
    ),
)

general_agent = LlmAgent(
    name="general_agent",
    model="gemini-2.0-flash",
    instruction=(
        "You are a friendly general support agent at a SaaS company.\n"
        "Your domain: account questions, how-to guides, general feedback, "
        "and anything that doesn't fit billing or technical categories.\n\n"
        "When a customer ticket is delegated to you:\n"
        "1. Greet the customer warmly\n"
        "2. Answer their question directly and concisely\n"
        "3. Offer any relevant follow-up resources\n\n"
        "Respond directly to the customer. "
        "Do not ask clarifying questions -- work with the information given."
    ),
)


# ── Orchestrator ──────────────────────────────────────────────────────────────
# The orchestrator's instruction tells the LLM what to do with the ticket.
# Key: it should classify THEN transfer -- not respond itself.

orchestrator = LlmAgent(
    name="support_orchestrator",
    model="gemini-2.0-flash",
    instruction=(
        "You are a customer support orchestrator. Your ONLY job is to:\n\n"
        "Step 1 -- Classify the incoming ticket into exactly one category:\n"
        "  billing:   charges, refunds, invoices, subscriptions, payment methods\n"
        "  technical: bugs, errors, crashes, system issues, feature questions\n"
        "  general:   account questions, how-tos, feedback, anything else\n\n"
        "Step 2 -- Immediately transfer to the right specialist:\n"
        "  billing category   -> transfer to billing_agent\n"
        "  technical category -> transfer to technical_agent\n"
        "  general category   -> transfer to general_agent\n\n"
        "IMPORTANT: Do NOT write a response to the customer yourself.\n"
        "Transfer immediately after classifying. "
        "The specialist will compose the full customer response."
    ),
    sub_agents=[billing_agent, technical_agent, general_agent],
)


# ── Handler ───────────────────────────────────────────────────────────────────

async def handle_ticket(ticket: str, session_id: str = "support_001") -> str:
    """
    Process a support ticket using the ADK orchestrator + sub-agent pattern.

    The orchestrator classifies the ticket and delegates (via agent_transfer)
    to the appropriate specialist, who composes the final customer response.

    Args:
        ticket:     The customer's support ticket text.
        session_id: Unique identifier per ticket. Use a different ID each time
                    to avoid session state bleeding between tickets.

    Returns:
        The specialist agent's response text.
    """
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="support_triage",
        user_id="customer",
        session_id=session_id,
    )

    runner = Runner(
        agent=orchestrator,
        app_name="support_triage",
        session_service=session_service,
    )

    message = Content(parts=[Part(text=f"Support ticket:\n\n{ticket}")])

    final_response = ""
    final_author = "unknown"

    async for event in runner.run_async(
        user_id="customer",
        session_id=session_id,
        new_message=message,
    ):
        # Track which agent produced the final output
        if hasattr(event, "author") and event.author:
            final_author = event.author

        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    print(f"   [ADK] Responded by: {final_author}")
    return final_response


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Same three tickets as support_triage_langgraph.py for direct comparison
    TICKETS = [
        (
            "I was charged twice for my subscription this month. "
            "The double charge appeared on March 1st. Please refund the extra amount.",
            "support_billing_001",
        ),
        (
            "The app crashes every time I try to upload a file larger than 10 MB. "
            "I get an 'Internal Server Error' in the browser console. "
            "This started happening after the update on Feb 28th.",
            "support_technical_001",
        ),
        (
            "How do I update the email address associated with my account? "
            "I've changed jobs and need to switch to my personal email.",
            "support_general_001",
        ),
    ]

    async def run():
        for i, (ticket, session_id) in enumerate(TICKETS, 1):
            print(f"\n{'=' * 55}")
            print(f"Ticket {i}: {ticket[:65]}...")
            print("─" * 55)
            response = await handle_ticket(ticket, session_id=session_id)
            print(response)

    asyncio.run(run())
