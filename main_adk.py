"""
Main Entry Point — Google ADK Version
=======================================
Runs the real estate negotiation using Google ADK agents
powered by Gemini 2.0 Flash (free tier).

WHAT THIS DEMONSTRATES:
  ✅ Google ADK (LlmAgent, Runner, SessionService)
  ✅ MCPToolset (automatic MCP tool discovery for ADK agents)
  ✅ Gemini 2.0 Flash (free tier — no billing required)
  ✅ A2A messaging (same schema as simple version)
  ✅ Dual MCP connections (seller uses pricing + inventory servers)

ARCHITECTURE:
  main_adk.py  (orchestrator — coordinates two ADK agents)
    ├── m4_adk/buyer_adk.py   (Gemini + MCPToolset → pricing_server)
    │     └── m2_mcp/pricing_server.py
    └── m4_adk/seller_adk.py  (Gemini + MCPToolset → pricing + inventory)
          ├── m2_mcp/pricing_server.py
          └── m2_mcp/inventory_server.py

HOW THE ADK VERSION DIFFERS FROM SIMPLE:
  Simple version:
  - BuyerAgent manually calls MCP tools then GPT-4o
  - LangGraph manages the negotiation loop

  ADK version:
  - LlmAgent (Gemini) decides when to call which MCP tools autonomously
  - MCPToolset handles MCP connections transparently
  - Orchestrator in main_adk.py manages the loop (not LangGraph)
  - Sessions managed by ADK's InMemorySessionService

SETUP:
  1. Install:
       pip install -r requirements.txt

  2. Get free Gemini API key:
       https://aistudio.google.com → Get API key

  3. Set environment:
       export GOOGLE_API_KEY=AIza...

  4. Run:
       python main_adk.py
"""

import argparse
import asyncio
import os
import sys
import uuid


def check_environment() -> None:
    """Check required environment variables for ADK/Gemini."""
    missing = []

    if not os.environ.get("GOOGLE_API_KEY"):
        missing.append("GOOGLE_API_KEY")

    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   export {var}=<your_value>")
        print()
        print("Get your FREE Gemini API key at: https://aistudio.google.com")
        print("No credit card required for the free tier!")
        sys.exit(1)


async def run_adk_negotiation(
    session_id: str,
    max_rounds: int = 5,
    buyer_budget: float = 460_000,
    seller_minimum: float = 445_000,
) -> dict:
    """
    Run the complete negotiation using ADK agents.

    ADK ORCHESTRATION PATTERN:
    Unlike the LangGraph version where the graph manages the loop,
    here the orchestrator (this function) manually manages the loop.

    Each round:
    1. Buyer agent's LlmAgent runs → calls MCP tools → produces offer
    2. We parse the offer into an A2AMessage
    3. Seller agent's LlmAgent runs (receiving buyer's A2A message as prompt)
    4. We parse the counter into an A2AMessage
    5. Check for agreement / deadlock
    6. Loop back to step 1 if continuing

    WHY THIS APPROACH?
    ADK agents are designed to be stateful within their own session.
    Coordination between agents is the orchestrator's job, not ADK's.
    This separation of concerns makes each agent simpler and more focused.
    """
    from m4_adk.buyer_adk import BuyerAgentADK
    from m4_adk.seller_adk import SellerAgentADK
    from m4_adk.messaging_adk import (
        NegotiationSession,
        print_round_summary,
        print_final_result,
    )
    from m3_agents.a2a_simple import A2AMessage

    # Create session tracker (holds negotiation state for ADK version)
    session = NegotiationSession(
        session_id=session_id,
        property_address="742 Evergreen Terrace, Austin, TX 78701",
        listing_price=485_000,
        buyer_budget=buyer_budget,
        seller_minimum=seller_minimum,
        max_rounds=max_rounds,
    )

    print(f"\nSession: {session_id}")
    print(f"Model: Gemini 2.0 Flash (free tier)")
    print(f"MCP: pricing_server.py + inventory_server.py")
    print()

    # Initialize both ADK agents as context managers
    # This connects to MCP servers and sets up Gemini
    async with BuyerAgentADK(session_id=f"{session_id}_buyer") as buyer:
        async with SellerAgentADK(session_id=f"{session_id}_seller") as seller:

            print("\n[Orchestrator] Both ADK agents initialized. Starting negotiation.")

            # ── Round loop ────────────────────────────────────────────────────
            for round_num in range(1, max_rounds + 1):

                # ── BUYER TURN ────────────────────────────────────────────────
                if round_num == 1:
                    # First round: make initial offer
                    buyer_message = await buyer.make_initial_offer()
                else:
                    # Subsequent rounds: respond to last seller counter
                    last_seller_msg = session.message_history[-1]
                    buyer_message = await buyer.respond_to_counter(last_seller_msg)

                session.record_message(buyer_message)
                print_round_summary(session, buyer_message)

                # Check if buyer terminated
                if session.is_concluded():
                    break

                # ── SELLER TURN ───────────────────────────────────────────────
                seller_message = await seller.respond_to_offer(buyer_message)
                session.record_message(seller_message)
                print_round_summary(session, seller_message)

                # Check if seller terminated
                if session.is_concluded():
                    break

                # ── Deadlock check ────────────────────────────────────────────
                if round_num >= max_rounds and not session.is_concluded():
                    session.status = "deadlocked"
                    print(f"\n[Orchestrator] ⏱️  Max rounds ({max_rounds}) reached — deadlock")
                    break

            # ── Final result ──────────────────────────────────────────────────
            print_final_result(session)

    return {
        "status": session.status,
        "agreed_price": session.agreed_price,
        "rounds_used": session.current_round,
        "message_count": len(session.message_history),
    }


async def main() -> None:
    """Main entry point for the ADK version."""

    parser = argparse.ArgumentParser(
        description="Real Estate Negotiation Simulator — Google ADK Version"
    )
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--session", type=str, default=None)
    parser.add_argument("--buyer-budget", type=float, default=460_000)
    parser.add_argument("--seller-minimum", type=float, default=445_000)
    args = parser.parse_args()

    session_id = args.session or f"adk_{uuid.uuid4().hex[:8]}"

    check_environment()

    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║        REAL ESTATE NEGOTIATION SIMULATOR                        ║")
    print("║        Google ADK Version (Gemini 2.0 Flash — Free Tier)        ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  Concepts: ADK + MCPToolset + A2A + Gemini                      ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    print("CONFIGURATION:")
    print(f"  Property:       742 Evergreen Terrace, Austin, TX 78701")
    print(f"  Listing Price:  $485,000")
    print(f"  Buyer Budget:   ${args.buyer_budget:,.0f}")
    print(f"  Seller Minimum: ${args.seller_minimum:,.0f}")
    print(f"  Max Rounds:     {args.rounds}")
    print(f"  Session ID:     {session_id}")
    print(f"  LLM:            Gemini 2.0 Flash (Google AI free tier)")
    print()
    print("WHAT TO WATCH FOR:")
    print("  [Buyer ADK]  Calling tool: → ADK is calling an MCP tool")
    print("  [Seller ADK] Connecting:   → ADK is connecting to MCP server")
    print("  [Orchestrator]             → Managing the A2A message exchange")
    print()

    try:
        result = await run_adk_negotiation(
            session_id=session_id,
            max_rounds=args.rounds,
            buyer_budget=args.buyer_budget,
            seller_minimum=args.seller_minimum,
        )

        print("\nNEXT STEPS:")
        print("  • Try the simple version: python main_simple.py")
        print("  • Compare results between versions")
        print("  • Exercises: open exercises/exercises.md")
        print()

        return result

    except KeyboardInterrupt:
        print("\n\n⚠️  Negotiation interrupted by user")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error during ADK negotiation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
