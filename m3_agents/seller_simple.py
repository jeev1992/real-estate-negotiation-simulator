"""
Seller Agent — Simple Python Version
========================================
A real estate seller agent implemented using OpenAI GPT-4o and MCP tools.

ARCHITECTURE:
  Mirror of buyer_simple.py but with opposing goals and different MCP tools.

  KEY DIFFERENCE FROM BUYER:
  The seller agent connects to BOTH MCP servers:
  - pricing_server: to understand market value and buyer's perspective
  - inventory_server: to know its floor price and market pressure

  This demonstrates MCP's access control concept:
  - Seller has access to get_minimum_acceptable_price()
  - Buyer does NOT (it connects to a different set of tools)

STRATEGY:
  - Starts at $477,000 (lists at $485,000 but expects negotiation)
  - Highlights renovation value (kitchen $45K, roof $18K, HVAC $12K)
  - Drops in small increments: $477K → $469K → $462K → $456K → $449K
  - Never goes below $445,000 (mortgage payoff requirement)
  - Accepts any offer at or above $445,000
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from m3_agents.a2a_simple import (
    A2AMessage,
    create_counter_offer,
    create_acceptance,
)


# ─── Configuration ────────────────────────────────────────────────────────────

PROPERTY_ADDRESS = "742 Evergreen Terrace, Austin, TX 78701"
PROPERTY_ID = "742-evergreen-austin-78701"
LISTING_PRICE = 485_000
MINIMUM_PRICE = 445_000  # Absolute floor — mortgage payoff requirement
IDEAL_PRICE = 465_000    # Target closing price

# Absolute paths to MCP servers — work regardless of working directory
_REPO_ROOT = Path(__file__).parent.parent
PRICING_SERVER_PATH = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")
INVENTORY_SERVER_PATH = str(_REPO_ROOT / "m2_mcp" / "inventory_server.py")

OPENAI_MODEL = "gpt-4o"

SELLER_SYSTEM_PROMPT = f"""You are an expert real estate listing agent representing the sellers of:

Property: {PROPERTY_ADDRESS}
Type: Single Family Home, 4 BR / 3 BA, 2,400 sqft, built 2005
Listed at: ${LISTING_PRICE:,}

PROPERTY HIGHLIGHTS (use these to justify your price):
  • Kitchen fully renovated in 2023 — $45,000 upgrade (quartz counters, new appliances)
  • New roof installed 2022 — $18,000 (30-year architectural shingles)
  • HVAC system replaced 2021 — $12,000 (Carrier 16 SEER)
  • Total recent upgrades: $75,000+
  • School district: Austin ISD — rated 8/10
  • No HOA fees

YOUR SELLER'S PROFILE:
  - Minimum acceptable price: ${MINIMUM_PRICE:,} (CANNOT go below — mortgage payoff)
  - Ideal closing price: ${IDEAL_PRICE:,}
  - Must close by: March 31, 2025 (seller has purchased another home)
  - Willing to include all appliances
  - Flexible on closing date (30–60 days)

YOUR STRATEGY:
  - Round 1: Counter at $477,000 (hold strong, highlight renovations)
  - Each round: Drop by $5,000–$8,000 only
  - Always reference the $75K in upgrades as added value
  - Use inventory/market data to show seller's market advantage
  - If buyer reaches ${MINIMUM_PRICE:,} or above, ACCEPT immediately

YOUR RESPONSE FORMAT (strict JSON):
{{
    "counter_price": <integer — your counter-offer price>,
    "message": "<professional message to buyer, referencing property value>",
    "reasoning": "<internal notes — your strategy and observations>",
    "accept": <true if you're accepting the buyer's offer, false otherwise>,
    "reject": <true if you're terminating negotiations, false otherwise>
}}

CRITICAL RULES:
  - NEVER counter below ${MINIMUM_PRICE:,} — this is your mortgage payoff minimum
  - If buyer offers ${MINIMUM_PRICE:,} or more, set accept: true immediately
  - Emphasize the $75,000 in recent renovations in EVERY response
  - Be firm but professional — don't be insulted by low offers"""


# ─── MCP Helpers ──────────────────────────────────────────────────────────────

async def call_mcp_server(server_path: str, tool_name: str, arguments: dict) -> dict:
    """
    Call a tool on any MCP server.

    Same pattern as buyer_simple.py's call_pricing_mcp() — demonstrates
    that the MCP client pattern is universal regardless of which server
    you're connecting to.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_path],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

            if result.content and len(result.content) > 0:
                return json.loads(result.content[0].text)

    return {}


# ─── Seller Agent Class ────────────────────────────────────────────────────────

class SellerAgent:
    """
    Real estate seller agent powered by OpenAI GPT-4o.

    KEY DIFFERENCES FROM BUYER AGENT:
    1. Connects to BOTH pricing and inventory MCP servers
    2. Has access to get_minimum_acceptable_price() (buyer does not)
    3. Strategy is to hold firm and drop slowly
    4. Accepts any offer >= minimum price

    INFORMATION ASYMMETRY TEACHING POINT:
    The seller knows its floor price from the inventory server.
    The buyer is trying to guess it from market data.
    This mirrors real-world real estate negotiations perfectly.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.round = 0

        # Conversation history
        self.llm_messages: list[dict] = [
            {"role": "system", "content": SELLER_SYSTEM_PROMPT}
        ]

        # Cached data
        self._market_data: Optional[dict] = None
        self._inventory_data: Optional[dict] = None
        self._seller_constraints: Optional[dict] = None
        self._last_buyer_message_id: Optional[str] = None

    async def _get_market_data(self) -> dict:
        """Fetch market data via pricing MCP server."""
        if self._market_data is None:
            print("   [Seller] Calling MCP (pricing): get_market_price...")
            self._market_data = await call_mcp_server(
                PRICING_SERVER_PATH,
                "get_market_price",
                {"address": PROPERTY_ADDRESS, "property_type": "single_family"}
            )
        return self._market_data

    async def _get_inventory_data(self) -> dict:
        """Fetch inventory data via inventory MCP server."""
        if self._inventory_data is None:
            print("   [Seller] Calling MCP (inventory): get_inventory_level...")
            self._inventory_data = await call_mcp_server(
                INVENTORY_SERVER_PATH,
                "get_inventory_level",
                {"zip_code": "78701"}
            )
        return self._inventory_data

    async def _get_seller_constraints(self) -> dict:
        """
        Fetch seller's floor price from inventory MCP server.

        ACCESS CONTROL TEACHING POINT:
        This is the tool the buyer does NOT call.
        In production, the inventory server would check auth headers
        and only return this data to the seller's agent.
        """
        if self._seller_constraints is None:
            print("   [Seller] Calling MCP (inventory): get_minimum_acceptable_price...")
            print("   [Seller] NOTE: Buyer agent does NOT have access to this tool")
            self._seller_constraints = await call_mcp_server(
                INVENTORY_SERVER_PATH,
                "get_minimum_acceptable_price",
                {"property_id": PROPERTY_ID}
            )
        return self._seller_constraints

    async def _call_llm(self, user_message: str) -> dict:
        """Call GPT-4o with current conversation context."""
        self.llm_messages.append({"role": "user", "content": user_message})

        response = await self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=self.llm_messages,
            response_format={"type": "json_object"},
            temperature=0.3,  # Seller is slightly more conservative
        )

        reply_content = response.choices[0].message.content
        self.llm_messages.append({"role": "assistant", "content": reply_content})

        return json.loads(reply_content)

    async def respond_to_offer(self, buyer_message: A2AMessage) -> A2AMessage:
        """
        Respond to a buyer's offer.

        This is called for BOTH initial offers and subsequent offers.
        The seller always:
        1. Gets market data to understand the landscape
        2. Gets inventory data to understand market pressure
        3. Gets its floor price (which buyer doesn't know)
        4. Asks GPT-4o to formulate the best counter

        A2A TEACHING POINT:
        The seller reads the buyer's A2AMessage for:
        - payload.price: the offer amount
        - payload.message: the buyer's justification
        - payload.conditions: what contingencies buyer wants
        - round: how many rounds remain
        """
        self.round = buyer_message.round
        self._last_buyer_message_id = buyer_message.message_id
        buyer_price = buyer_message.payload.price or 0

        print(f"\n[Seller] Round {self.round}: Received offer ${buyer_price:,.0f}")

        # Auto-accept if buyer meets minimum
        if buyer_price >= MINIMUM_PRICE:
            print(f"   [Seller] Buyer at ${buyer_price:,.0f} >= minimum ${MINIMUM_PRICE:,}. ACCEPTING!")
            return create_acceptance(
                session_id=self.session_id,
                round_num=self.round,
                from_agent="seller",
                agreed_price=buyer_price,
                message=(
                    f"We are pleased to accept your offer of ${buyer_price:,.0f}! "
                    f"Thank you for recognizing the value in this exceptional property. "
                    f"We look forward to working with you through closing."
                ),
                in_reply_to=self._last_buyer_message_id
            )

        # Step 1: Gather intelligence via MCP
        market_data = await self._get_market_data()
        inventory_data = await self._get_inventory_data()
        constraints = await self._get_seller_constraints()

        # Step 2: Build context for GPT-4o
        pricing_data = constraints.get("pricing_constraints", {})
        market_type = inventory_data.get("market_assessment", {}).get("condition", "balanced")
        avg_comp = market_data.get("market_statistics", {}).get("avg_comparable_price", 462_000)

        rounds_remaining = 5 - self.round

        user_message = f"""
You are responding to a buyer's offer on {PROPERTY_ADDRESS}.

BUYER'S OFFER (from A2A message):
  Price: ${buyer_price:,.0f}
  Conditions: {buyer_message.payload.conditions}
  Closing timeline: {buyer_message.payload.closing_timeline_days} days
  Buyer's justification: "{buyer_message.payload.message}"

MARKET INTELLIGENCE (from MCP servers):
  Market type: {market_type}
  Avg comparable price: ${avg_comp:,.0f}
  Days on market (this property): {market_data.get('pricing', {}).get('days_on_market', 18)}
  Active listings in 78701: {inventory_data.get('activity_30_days', {}).get('active_listings', 47)}
  Inventory (months): {inventory_data.get('activity_30_days', {}).get('absorption_rate_months', 3.1)}

YOUR PRICING CONSTRAINTS (from MCP inventory server — SELLER CONFIDENTIAL):
  Absolute minimum: ${pricing_data.get('minimum_acceptable_price', MINIMUM_PRICE):,}
  Target price: ${pricing_data.get('ideal_closing_price', IDEAL_PRICE):,}
  Negotiation room remaining: ${pricing_data.get('absolute_negotiation_room', 40_000):,}

NEGOTIATION STATUS:
  Current round: {self.round} of 5
  Rounds remaining: {rounds_remaining}
  Gap between buyer offer and your minimum: ${buyer_price - MINIMUM_PRICE:,.0f}
  {'⚠️  ONLY ' + str(rounds_remaining) + ' ROUNDS REMAIN — consider being more flexible' if rounds_remaining <= 2 else ''}

PROPERTY STRENGTHS TO EMPHASIZE:
  - Kitchen renovation 2023: $45,000 (quartz counters, premium appliances)
  - Roof replaced 2022: $18,000 (30-year warranty)
  - HVAC 2021: $12,000 (Carrier 16 SEER — energy efficient)
  - Total upgrades: $75,000+
  - No HOA fees

What is your counter-offer? Remember your floor is ${MINIMUM_PRICE:,}.
"""

        # Step 3: GPT-4o formulates the response
        decision = await self._call_llm(user_message)

        print(f"   [Seller] Decision: counter ${decision.get('counter_price', 0):,} | accept={decision.get('accept', False)}")

        # Step 4: Handle acceptance decision
        if decision.get("accept", False):
            return create_acceptance(
                session_id=self.session_id,
                round_num=self.round,
                from_agent="seller",
                agreed_price=buyer_price,
                message=decision["message"],
                in_reply_to=self._last_buyer_message_id
            )

        # Step 5: Validate counter doesn't go below floor
        counter_price = float(decision.get("counter_price", LISTING_PRICE))
        if counter_price < MINIMUM_PRICE:
            # LLM went below floor — correct it
            print(f"   [Seller] ⚠️  LLM went below floor! Correcting ${counter_price:,} → ${MINIMUM_PRICE:,}")
            counter_price = float(MINIMUM_PRICE)
            decision["message"] += f" Our absolute best price is ${MINIMUM_PRICE:,}."

        # Step 6: Return counter-offer
        return create_counter_offer(
            session_id=self.session_id,
            round_num=self.round,
            price=counter_price,
            message=decision["message"],
            in_reply_to=self._last_buyer_message_id
        )
