"""
Main Entry Point — Simple Python Version
==========================================
Runs the real estate negotiation using OpenAI GPT-4o agents
orchestrated by LangGraph.

WHAT THIS DEMONSTRATES:
  ✅ MCP tool calls (pricing + inventory servers via Python client)
    ✅ Typed negotiation messages (structured state between agents)
  ✅ LangGraph orchestration (state machine managing the negotiation loop)
  ✅ OpenAI GPT-4o (powers both buyer and seller reasoning)

ARCHITECTURE:
    main_langgraph_multiagent.py
    └── m3_langgraph_multiagents/langgraph_flow.py  (manages the negotiation loop)
          ├── m3_langgraph_multiagents/buyer_simple.py  (GPT-4o + MCP)
          │     └── m2_mcp/pricing_server.py (MCP tools)
          └── m3_langgraph_multiagents/seller_simple.py (GPT-4o + MCP)
                ├── m2_mcp/pricing_server.py (MCP tools)
                └── m2_mcp/inventory_server.py (MCP tools)

SETUP:
  1. Install dependencies:
       pip install -r requirements.txt

  2. Set environment variables:
       export OPENAI_API_KEY=sk-...

  3. Run:
      python m3_langgraph_multiagents/main_langgraph_multiagent.py

OPTIONAL FLAGS:
  --rounds N     Set maximum negotiation rounds (default: 5)
  --session ID   Set session identifier (default: auto-generated)
  --verbose      Show detailed MCP call logs
"""

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Validate environment before importing anything
def check_environment() -> None:
    """Check that required environment variables are set."""
    missing = []

    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")

    if missing:
        print("ERROR: Missing required environment variables:")
        for var in missing:
            print(f"   export {var}=<your_value>")
        print()
        print("Get your OpenAI API key at: https://platform.openai.com/api-keys")
        sys.exit(1)


async def main() -> None:
    """Main entry point for the simple Python negotiation demo."""

    # ── Parse arguments ───────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="Real Estate Negotiation Simulator — Simple Python Version"
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=5,
        help="Maximum number of negotiation rounds (default: 5)"
    )
    parser.add_argument(
        "--session",
        type=str,
        default=None,
        help="Session ID for this negotiation (default: auto-generated UUID)"
    )
    parser.add_argument(
        "--buyer-budget",
        type=float,
        default=460_000,
        help="Buyer's maximum budget in dollars (default: 460000)"
    )
    parser.add_argument(
        "--seller-minimum",
        type=float,
        default=445_000,
        help="Seller's minimum acceptable price (default: 445000)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed MCP call and LLM interaction logs"
    )
    args = parser.parse_args()

    session_id = args.session or f"neg_{uuid.uuid4().hex[:8]}"

    # ── Environment check ─────────────────────────────────────────────────────
    check_environment()

    # ── Banner ────────────────────────────────────────────────────────────────
    print()
    print("=" * 68)
    print("REAL ESTATE NEGOTIATION SIMULATOR")
    print("Simple Python Version (OpenAI GPT-4o + LangGraph)")
    print("Concepts: MCP + Typed Messages + LangGraph")
    print("=" * 68)
    print()
    print("CONFIGURATION:")
    print(f"  Property:       742 Evergreen Terrace, Austin, TX 78701")
    print(f"  Listing Price:  $485,000")
    print(f"  Buyer Budget:   ${args.buyer_budget:,.0f}")
    print(f"  Seller Minimum: ${args.seller_minimum:,.0f}")
    print(f"  Max Rounds:     {args.rounds}")
    print(f"  Session ID:     {session_id}")
    print(f"  LLM:            OpenAI GPT-4o")
    print()

    print("WHAT TO WATCH FOR:")
    print("  [Buyer] Calling MCP:  -> agent is fetching market data via MCP")
    print("  [Seller] Calling MCP: -> agent is fetching pricing/inventory via MCP")
    print("  [LangGraph] ->        -> LangGraph is routing between nodes")
    print("  A2A messages          -> structured JSON between agents")
    print()

    # ── Run the LangGraph orchestration ──────────────────────────────────────
    from m3_langgraph_multiagents.langgraph_flow import run_negotiation

    try:
        final_state = await run_negotiation(
            session_id=session_id,
            property_address="742 Evergreen Terrace, Austin, TX 78701",
            listing_price=485_000.0,
            buyer_budget=args.buyer_budget,
            seller_minimum=args.seller_minimum,
            max_rounds=args.rounds,
        )

        # ── Post-negotiation summary ──────────────────────────────────────────
        print("\nNEXT STEPS:")
        print("  - Try the ADK version:  python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102")
        print("  - GitHub MCP demo:      python m2_mcp/github_demo_client.py")
        print("  - Exercises:            open exercises/exercises.md")
        print()

        return final_state

    except KeyboardInterrupt:
        print("\n\nNegotiation interrupted by user")
        sys.exit(0)

    except Exception as e:
        print(f"\nERROR during negotiation: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
