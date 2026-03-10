import asyncio
import os

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part


billing_agent = LlmAgent(
    name="billing_agent",
    model="openai/gpt-4o",
    instruction=(
        "You are a billing support specialist at a SaaS company. "
        "Handle charges, refunds, invoices, subscriptions, and payment methods. "
        "Respond empathetically with concrete next steps in 2-3 paragraphs."
    ),
)

technical_agent = LlmAgent(
    name="technical_agent",
    model="openai/gpt-4o",
    instruction=(
        "You are a technical support specialist. "
        "Handle bugs/errors/crashes and provide numbered troubleshooting steps."
    ),
)

general_agent = LlmAgent(
    name="general_agent",
    model="openai/gpt-4o",
    instruction=(
        "You are a friendly general support agent. "
        "Handle account/how-to/general inquiries concisely."
    ),
)

orchestrator = LlmAgent(
    name="support_orchestrator",
    model="openai/gpt-4o",
    instruction=(
        "Classify incoming support tickets into billing, technical, or general, "
        "then immediately transfer to the matching sub-agent. "
        "Do not answer directly as orchestrator."
    ),
    sub_agents=[billing_agent, technical_agent, general_agent],
)


async def handle_ticket(ticket: str, session_id: str = "support_001") -> str:
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

    async for event in runner.run_async(
        user_id="customer",
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    return final_response


if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. Add it to .env or environment before running ex12.")
        raise SystemExit(1)

    tickets = [
        ("I was charged twice for my subscription this month. Please refund the extra charge.", "support_runner_001"),
        ("The app crashes every time I upload a file. Error: Internal Server Error.", "support_runner_002"),
        ("How do I update the email address on my account?", "support_runner_003"),
    ]

    async def run() -> None:
        for ticket, session_id in tickets:
            print(f"\nTicket: {ticket}")
            try:
                print(await handle_ticket(ticket, session_id=session_id))
            except Exception as error:
                message = str(error)
                if "RESOURCE_EXHAUSTED" in message or "429" in message:
                    print("Provider quota exceeded (429 / RESOURCE_EXHAUSTED).")
                    print("Retry later or use a key/project with available quota.")
                    raise SystemExit(1)
                print(f"ADK run failed: {error}")
                raise SystemExit(1)

    asyncio.run(run())
