"""
Main Entry Point — Google ADK Version
=======================================
Runs the real estate negotiation using Google ADK agents
powered by Gemini 2.0 Flash (free tier).

WHAT THIS DEMONSTRATES:
  ✅ Google ADK (LlmAgent, Runner, SessionService)
  ✅ MCPToolset (automatic MCP tool discovery for ADK agents)
  ✅ Gemini 2.0 Flash (free tier — no billing required)
    ✅ ADK-native agent messaging in Module 4
  ✅ Dual MCP connections (seller uses pricing + inventory servers)

ARCHITECTURE:
    main_adk_multiagent.py  (coordinator — coordinates two ADK agents)
    ├── m4_adk_multiagents/buyer_adk.py   (Gemini + MCPToolset → pricing_server)
    │     └── m2_mcp/pricing_server.py
    └── m4_adk_multiagents/seller_adk.py  (Gemini + MCPToolset → pricing + inventory)
          ├── m2_mcp/pricing_server.py
          └── m2_mcp/inventory_server.py
        + m4_adk_multiagents/adk_a2a_types.py (Module 4 ADK-native message model)

HOW THE ADK VERSION DIFFERS FROM SIMPLE:
  Simple version:
  - BuyerAgent manually calls MCP tools then GPT-4o
  - LangGraph manages the negotiation loop

  ADK version:
  - LlmAgent (Gemini) decides when to call which MCP tools autonomously
  - MCPToolset handles MCP connections transparently
    - Coordinator in main_adk_multiagent.py manages the loop (not LangGraph)
  - Sessions managed by ADK's InMemorySessionService

SETUP:
  1. Install:
       pip install -r requirements.txt

  2. Get free Gemini API key:
       https://aistudio.google.com → Get API key

  3. Set environment:
       export GOOGLE_API_KEY=AIza...

  4. Run:
      python m4_adk_multiagents/bonus/main_adk_multiagent.py
"""

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def check_environment() -> None:
    """Check required environment variables for ADK/Gemini."""
    missing = []

    if not os.environ.get("GOOGLE_API_KEY"):
        missing.append("GOOGLE_API_KEY")

    if missing:
        print("ERROR: Missing required environment variables:")
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

    ADK COORDINATION PATTERN:
    Unlike the LangGraph version where the graph manages the loop,
    here this function manually manages the loop.

    Each round:
    1. Buyer agent's LlmAgent runs → calls MCP tools → produces offer
    2. We parse the offer into an ADK-native negotiation message
    3. Seller agent's LlmAgent runs (receiving buyer message as prompt)
    4. We parse the counter into an ADK-native negotiation message
    5. Check for agreement / deadlock
    6. Loop back to step 1 if continuing

    WHY THIS APPROACH?
    ADK agents are designed to be stateful within their own session.
    Coordination between agents is handled by the runner logic here, not ADK's core runtime.
    This separation of concerns makes each agent simpler and more focused.
    """
    from m4_adk_multiagents.buyer_adk import BuyerAgentADK
    from m4_adk_multiagents.seller_adk import SellerAgentADK
    from m4_adk_multiagents.messaging_adk import (
        NegotiationSession,
        print_round_summary,
        print_final_result,
    )
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

            print("\n[Coordinator] Both ADK agents initialized. Starting negotiation.")

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
                    print(f"\n[Coordinator] Max rounds ({max_rounds}) reached -- deadlock")
                    break

            # ── Final result ──────────────────────────────────────────────────
            print_final_result(session)

    return {
        "status": session.status,
        "agreed_price": session.agreed_price,
        "rounds_used": session.current_round,
        "message_count": len(session.message_history),
    }


async def _run_check() -> None:
    """
    Validate the ADK setup without making any Gemini API calls.

    Checks:
      1. GOOGLE_API_KEY is set (done by check_environment() before this runs)
      2. All module imports succeed
      3. MCPToolset can connect to both MCP servers and list tools
      4. ADK agent objects can be constructed

    Exits 0 on success, 1 on any failure — safe to run repeatedly
    without consuming Gemini quota.
    """
    from m4_adk_multiagents.buyer_adk import BuyerAgentADK
    from m4_adk_multiagents.seller_adk import SellerAgentADK

    print("ADK setup check (no Gemini calls)...")

    try:
        async with BuyerAgentADK(session_id="check_buyer") as buyer:
            print("  buyer agent + pricing MCP: OK")

        async with SellerAgentADK(session_id="check_seller") as seller:
            print("  seller agent + pricing MCP + inventory MCP: OK")

        print("Setup check passed.")

    except Exception as e:
        print(f"Setup check FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def main() -> None:
    """Main entry point for the ADK version."""

    parser = argparse.ArgumentParser(
        description="Real Estate Negotiation Simulator — Google ADK Version"
    )
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--session", type=str, default=None)
    parser.add_argument("--buyer-budget", type=float, default=460_000)
    parser.add_argument("--seller-minimum", type=float, default=445_000)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate setup (env + MCP connections) without calling Gemini. Exit 0 on success.",
    )
    args = parser.parse_args()

    session_id = args.session or f"adk_{uuid.uuid4().hex[:8]}"

    check_environment()

    if args.check:
        await _run_check()
        return

    print()
    print("=" * 68)
    print("REAL ESTATE NEGOTIATION SIMULATOR")
    print("Google ADK Version (Gemini 2.0 Flash -- Free Tier)")
    print("Concepts: ADK + MCPToolset + A2A + Gemini")
    print("=" * 68)
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
    print("  [Buyer ADK]  Calling tool: -> ADK is calling an MCP tool")
    print("  [Seller ADK] Connecting:   -> ADK is connecting to MCP server")
    print("  [Coordinator]              -> Managing the A2A message exchange")
    print()

    try:
        result = await run_adk_negotiation(
            session_id=session_id,
            max_rounds=args.rounds,
            buyer_budget=args.buyer_budget,
            seller_minimum=args.seller_minimum,
        )

        print("\nNEXT STEPS:")
        print("  - Try the simple version: python m3_langgraph_multiagents/main_langgraph_multiagent.py")
        print("  - Compare results between versions")
        print("  - Exercises: open exercises/exercises.md")
        print()

        return result

    except KeyboardInterrupt:
        print("\n\nNegotiation interrupted by user")
        sys.exit(0)

    except Exception as e:
        print(f"\nERROR during ADK negotiation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
