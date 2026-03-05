"""
Customer Support Triage System -- LangGraph version.

Demonstrates:
  - StateGraph with TypedDict state
  - Annotated list reducer for history accumulation
  - Conditional routing after a triage node
  - Specialist agent nodes (billing, technical, general)
  - format_response_node as a final aggregator

Run:
    python bonus/support_triage_langgraph.py

Requires:
    OPENAI_API_KEY in environment or .env
"""

import asyncio
import json
import operator
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from openai import AsyncOpenAI

client = AsyncOpenAI()


# ── State Schema ──────────────────────────────────────────────────────────────

class SupportState(TypedDict):
    ticket: str                               # Raw ticket text
    classification: str                       # "billing" | "technical" | "general"
    urgency: str                              # "low" | "medium" | "high"
    assigned_to: str                          # Which specialist handled the ticket
    specialist_response: str                  # Specialist's draft response
    final_response: str                       # Formatted final output
    history: Annotated[list[dict], operator.add]  # Accumulated step log


# ── Nodes ─────────────────────────────────────────────────────────────────────

async def triage_node(state: SupportState) -> dict:
    """
    Classify the incoming ticket and assess urgency.

    Uses response_format=json_object so the output is always parseable.
    Falls back to "general" / "low" on any parsing error.
    """
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a customer support triage agent.\n"
                    "Classify the incoming ticket and return JSON with:\n"
                    "  classification: billing | technical | general\n"
                    "  urgency: low | medium | high\n"
                    "  reasoning: one sentence explaining why\n\n"
                    "Billing:   charges, refunds, invoices, subscriptions, payment methods\n"
                    "Technical: bugs, errors, crashes, system issues, feature questions\n"
                    "General:   account questions, how-tos, feedback, everything else"
                ),
            },
            {
                "role": "user",
                "content": f"Classify this support ticket:\n\n{state['ticket']}",
            },
        ],
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    classification = result.get("classification", "general").strip().lower()
    urgency = result.get("urgency", "low").strip().lower()

    # Normalize unexpected values to safe defaults
    if classification not in ("billing", "technical", "general"):
        classification = "general"
    if urgency not in ("low", "medium", "high"):
        urgency = "low"

    print(f"   [Triage] -> {classification.upper()} | urgency: {urgency}")
    return {
        "classification": classification,
        "urgency": urgency,
        "history": [
            {
                "step": "triage",
                "classification": classification,
                "urgency": urgency,
                "reasoning": result.get("reasoning", ""),
            }
        ],
    }


async def billing_node(state: SupportState) -> dict:
    """
    Billing specialist handles the ticket.
    Responds with empathy and specific action steps.
    """
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a billing support specialist at a SaaS company. "
                    "You handle questions about charges, refunds, invoices, "
                    "subscriptions, and payment methods. "
                    "Be empathetic, clear, and give specific action steps. "
                    "Keep your response to 2-3 paragraphs."
                ),
            },
            {
                "role": "user",
                "content": f"Customer support ticket:\n\n{state['ticket']}",
            },
        ],
    )
    text = response.choices[0].message.content
    print(f"   [Billing] -> drafted response ({len(text)} chars)")
    return {
        "assigned_to": "billing",
        "specialist_response": text,
        "history": [{"step": "billing", "chars": len(text)}],
    }


async def technical_node(state: SupportState) -> dict:
    """
    Technical specialist handles the ticket.
    Provides numbered troubleshooting steps when applicable.
    """
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a technical support specialist at a SaaS company. "
                    "You handle bugs, errors, crashes, feature questions, and system issues. "
                    "Provide numbered troubleshooting steps when relevant. "
                    "Be precise and actionable."
                ),
            },
            {
                "role": "user",
                "content": f"Customer support ticket:\n\n{state['ticket']}",
            },
        ],
    )
    text = response.choices[0].message.content
    print(f"   [Technical] -> drafted response ({len(text)} chars)")
    return {
        "assigned_to": "technical",
        "specialist_response": text,
        "history": [{"step": "technical", "chars": len(text)}],
    }


async def general_node(state: SupportState) -> dict:
    """
    General support agent handles the ticket.
    Friendly, warm, and concise for everything that doesn't fit billing/technical.
    """
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a friendly general support agent at a SaaS company. "
                    "You handle account questions, how-to guides, general feedback, "
                    "and anything that doesn't fit billing or technical categories. "
                    "Be warm, helpful, and concise."
                ),
            },
            {
                "role": "user",
                "content": f"Customer support ticket:\n\n{state['ticket']}",
            },
        ],
    )
    text = response.choices[0].message.content
    print(f"   [General] -> drafted response ({len(text)} chars)")
    return {
        "assigned_to": "general",
        "specialist_response": text,
        "history": [{"step": "general", "chars": len(text)}],
    }


async def format_response_node(state: SupportState) -> dict:
    """
    Assemble the final formatted response with a metadata header.

    Urgency tags: [!] = high, [~] = medium, [ ] = low
    """
    urgency_tag = {"high": "[!]", "medium": "[~]", "low": "[ ]"}.get(
        state.get("urgency", "low"), "[ ]"
    )
    final = (
        f"SUPPORT TICKET RESPONSE\n"
        f"{'=' * 42}\n"
        f"Classified: {state.get('classification', 'general').upper()}\n"
        f"Urgency:    {urgency_tag} {state.get('urgency', 'low').upper()}\n"
        f"Handled by: {state.get('assigned_to', 'support').title()} Team\n"
        f"{'─' * 42}\n\n"
        f"{state.get('specialist_response', '')}"
    )
    return {
        "final_response": final,
        "history": [{"step": "format_response", "done": True}],
    }


# ── Router ────────────────────────────────────────────────────────────────────

def route_after_triage(state: SupportState) -> str:
    """
    Deterministic Python router — reads state["classification"].

    Falls back to "general" for any unexpected value (defensive).
    Compare this to ADK's implicit LLM-based routing in support_triage_adk.py.
    """
    classification = state.get("classification", "general")
    return classification if classification in ("billing", "technical", "general") else "general"


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_support_graph():
    """
    Graph topology:

        START
          |
        triage
          | (conditional)
      /   |   \
   billing technical general
      \   |   /
      format_response
          |
         END
    """
    workflow = StateGraph(SupportState)

    workflow.add_node("triage", triage_node)
    workflow.add_node("billing", billing_node)
    workflow.add_node("technical", technical_node)
    workflow.add_node("general", general_node)
    workflow.add_node("format_response", format_response_node)

    workflow.set_entry_point("triage")

    workflow.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "billing": "billing",
            "technical": "technical",
            "general": "general",
        },
    )

    workflow.add_edge("billing", "format_response")
    workflow.add_edge("technical", "format_response")
    workflow.add_edge("general", "format_response")
    workflow.add_edge("format_response", END)

    return workflow.compile()


# ── Public API ────────────────────────────────────────────────────────────────

async def handle_ticket(ticket: str) -> str:
    """Process a support ticket end-to-end and return the formatted response."""
    app = build_support_graph()
    result = await app.ainvoke({"ticket": ticket, "history": []})
    return result["final_response"]


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    TICKETS = [
        "I was charged twice for my subscription this month. "
        "The double charge appeared on March 1st. Please refund the extra amount.",

        "The app crashes every time I try to upload a file larger than 10 MB. "
        "I get an 'Internal Server Error' in the browser console. "
        "This started happening after the update on Feb 28th.",

        "How do I update the email address associated with my account? "
        "I've changed jobs and need to switch to my personal email.",
    ]

    async def run():
        for i, ticket in enumerate(TICKETS, 1):
            print(f"\n{'=' * 55}")
            print(f"Ticket {i}: {ticket[:65]}...")
            print("─" * 55)
            print(await handle_ticket(ticket))

    asyncio.run(run())
