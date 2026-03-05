"""
Buyer Agent — Simple Python Version
======================================
A real estate buyer agent implemented using OpenAI GPT-4o and MCP tools.

ARCHITECTURE:
  This is the "simple" version — plain Python without ADK.
  It demonstrates the core concepts clearly:

  1. MCP TOOL CALLS: The agent calls get_market_price() and calculate_discount()
     via the MCP Python client before forming any offer.

  2. LLM REASONING: GPT-4o decides the actual offer price and message
     based on the market data retrieved via MCP.

  3. A2A OUTPUT: The agent produces an A2AMessage that gets routed to
     the seller via the A2AMessageBus.

  4. STATE: The agent maintains its conversation history (buyer_llm_messages)
     across rounds so GPT-4o remembers previous offers and counters.

FLOW PER ROUND:
  1. Receive seller's counter-offer (A2AMessage via bus)
  2. Call MCP pricing server to get fresh market data
  3. Call MCP pricing server to calculate discount range
  4. Add market data + counter to GPT-4o context
  5. GPT-4o decides next offer (or walk-away)
  6. Return A2AMessage with the decision
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI

# MCP client imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# A2A message schema from our a2a_simple module
from m3_agents.a2a_simple import (
    A2AMessage,
    create_offer,
    create_withdrawal,
)


# ─── Configuration ────────────────────────────────────────────────────────────

PROPERTY_ADDRESS = "742 Evergreen Terrace, Austin, TX 78701"
PROPERTY_ID = "742-evergreen-austin-78701"
LISTING_PRICE = 485_000
BUYER_BUDGET = 460_000
WALK_AWAY_THRESHOLD = BUYER_BUDGET  # Never offer above this

# Path to the pricing MCP server
# Absolute path to the pricing server — works regardless of working directory
PRICING_SERVER_PATH = str(Path(__file__).parent.parent / "m2_mcp" / "pricing_server.py")

# OpenAI model
OPENAI_MODEL = "gpt-4o"

BUYER_SYSTEM_PROMPT = f"""You are an expert real estate buyer agent representing a client
who wants to purchase the following property:

Property: {PROPERTY_ADDRESS}
Type: Single Family Home, 4 BR / 3 BA, 2,400 sqft, built 2005
Listed at: ${LISTING_PRICE:,}

YOUR CLIENT'S PROFILE:
- Maximum budget: ${BUYER_BUDGET:,} (ABSOLUTE CEILING — never offer above this)
- Target acquisition price: $445,000–$455,000
- Walk-away point: If seller won't go below ${WALK_AWAY_THRESHOLD:,}
- Closing flexibility: 30–45 days
- Pre-approved for financing

YOUR STRATEGY:
- Round 1: Offer approximately 12% below asking ($425,000)
- Subsequent rounds: Increase in 2–4% increments
- Always use market data to JUSTIFY your offer
- Highlight inspection contingency as leverage
- Be professional but firm

YOUR RESPONSE FORMAT (strict JSON):
{{
    "offer_price": <integer, the dollar amount of your offer>,
    "message": "<professional message to the seller justifying your offer>",
    "reasoning": "<your internal strategy notes — what you observed and why you chose this price>",
    "walk_away": <true if you're withdrawing, false otherwise>,
    "walk_away_reason": "<only if walk_away is true — brief explanation>"
}}

CRITICAL RULES:
- NEVER offer above ${WALK_AWAY_THRESHOLD:,}
- If seller won't move below your budget, set walk_away: true
- Always reference market data in your message
- Keep message professional and factual
- Your reasoning field is private (not shown to seller)"""


# ─── MCP Helper ───────────────────────────────────────────────────────────────

async def call_pricing_mcp(tool_name: str, arguments: dict) -> dict:
    """
    Call a tool on the pricing MCP server.

    MCP CONCEPT:
    This function demonstrates the full MCP client lifecycle:
    1. Define how to connect (StdioServerParameters)
    2. Open transport (stdio_client context manager)
    3. Create MCP session (ClientSession context manager)
    4. Initialize session (MCP handshake)
    5. Call tool by name with arguments
    6. Parse and return the result

    In production, you'd keep the session open between calls
    (not reconnect every time). Here we reconnect each call
    for simplicity and to make the pattern clear.
    """
    server_params = StdioServerParameters(
        command=sys.executable,  # "python" — current interpreter
        args=[PRICING_SERVER_PATH],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(tool_name, arguments)

            # MCP results come back as content blocks
            if result.content and len(result.content) > 0:
                text = result.content[0].text
                return json.loads(text)

    return {}


# ─── Buyer Agent Class ────────────────────────────────────────────────────────

class BuyerAgent:
    """
    Real estate buyer agent powered by OpenAI GPT-4o.

    The agent maintains its own conversation history (buyer_llm_messages)
    so it remembers all previous rounds. Each round:
    1. Fetches fresh market data via MCP
    2. Adds the seller's counter + market data to its context
    3. Calls GPT-4o to decide the next offer
    4. Converts the LLM response to an A2AMessage

    WHY KEEP CONVERSATION HISTORY?
    Without history, the agent starts fresh each round and may:
    - Make inconsistent offers (offer less than previous round)
    - Forget the seller's previous arguments
    - Lose negotiating context

    With history, GPT-4o sees the full negotiation thread and
    makes coherent, progressive offers.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.round = 0

        # Conversation history for GPT-4o
        self.llm_messages: list[dict] = [
            {"role": "system", "content": BUYER_SYSTEM_PROMPT}
        ]

        # Cached market data (fetched once, reused)
        self._market_data: Optional[dict] = None
        self._last_seller_message_id: Optional[str] = None

    async def _get_market_data(self) -> dict:
        """Fetch and cache market pricing data from MCP server."""
        if self._market_data is None:
            print("   [Buyer] Calling MCP: get_market_price...")
            self._market_data = await call_pricing_mcp(
                "get_market_price",
                {
                    "address": PROPERTY_ADDRESS,
                    "property_type": "single_family"
                }
            )
            print(f"   [Buyer] MCP returned: avg comp ${self._market_data.get('market_statistics', {}).get('avg_comparable_price', 'N/A'):,}")
        return self._market_data

    async def _get_discount_analysis(self, market_condition: str, days_on_market: int) -> dict:
        """Fetch discount analysis from MCP server."""
        print("   [Buyer] Calling MCP: calculate_discount...")
        result = await call_pricing_mcp(
            "calculate_discount",
            {
                "base_price": float(LISTING_PRICE),
                "market_condition": market_condition,
                "days_on_market": days_on_market,
                "property_condition": "good"
            }
        )
        print(f"   [Buyer] MCP returned: offer range ${result.get('suggested_offer_prices', {}).get('moderate', 'N/A'):,}")
        return result

    async def _call_llm(self, user_message: str) -> dict:
        """
        Call GPT-4o with the current conversation context.

        We use json_object response format to ensure the LLM always
        returns valid JSON that we can parse reliably.
        """
        self.llm_messages.append({"role": "user", "content": user_message})

        response = await self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=self.llm_messages,
            response_format={"type": "json_object"},
            temperature=0.4,  # Lower temperature = more consistent negotiation
        )

        reply_content = response.choices[0].message.content
        self.llm_messages.append({"role": "assistant", "content": reply_content})

        return json.loads(reply_content)

    async def make_initial_offer(self) -> A2AMessage:
        """
        Make the opening offer.

        Called at round 1, before any seller counter-offer exists.
        The agent fetches market data and uses it to justify its opening bid.
        """
        self.round = 1
        print(f"\n[Buyer] Round {self.round}: Preparing initial offer...")

        # Step 1: Get market data via MCP
        market_data = await self._get_market_data()
        market_condition = market_data.get("market_conditions", {}).get("market_type", "balanced")
        days_on_market = market_data.get("pricing", {}).get("days_on_market", 18)

        # Step 2: Get discount analysis via MCP
        discount_data = await self._get_discount_analysis(market_condition, days_on_market)

        # Step 3: Build context for GPT-4o
        user_message = f"""
You are making your INITIAL OFFER on {PROPERTY_ADDRESS}.

MARKET DATA (from MCP pricing server):
{json.dumps(market_data.get('market_statistics', {}), indent=2)}

MARKET CONDITIONS:
{json.dumps(market_data.get('market_conditions', {}), indent=2)}

DISCOUNT ANALYSIS (from MCP server):
{json.dumps(discount_data.get('discount_analysis', {}), indent=2)}
Suggested offer range: {json.dumps(discount_data.get('suggested_offer_prices', {}), indent=2)}

PROPERTY UPGRADES TO ACKNOWLEDGE:
{market_data.get('property_details', {}).get('recent_upgrades', [])}

This is your FIRST offer. Start strategically below your budget.
Based on the market data, what is your opening offer?
"""

        # Step 4: GPT-4o decides the offer
        decision = await self._call_llm(user_message)

        print(f"   [Buyer] Decision: offer ${decision.get('offer_price', 0):,}")
        print(f"   [Buyer] Reasoning: {decision.get('reasoning', '')[:80]}...")

        # Step 5: Convert to A2AMessage
        return create_offer(
            session_id=self.session_id,
            round_num=self.round,
            price=float(decision["offer_price"]),
            message=decision["message"],
        )

    async def respond_to_counter(self, seller_message: A2AMessage) -> A2AMessage:
        """
        Respond to a seller counter-offer.

        The agent adds the seller's counter to its LLM context and
        calls GPT-4o to decide whether to increase the offer, accept, or walk away.
        """
        self.round += 1
        self._last_seller_message_id = seller_message.message_id

        print(f"\n[Buyer] Round {self.round}: Received counter-offer ${seller_message.payload.price:,.0f}")

        # Sanity check: if seller already came below our budget, consider accepting
        seller_price = seller_message.payload.price or 0

        # Step 1: Refresh discount analysis with current market
        market_data = await self._get_market_data()
        market_condition = market_data.get("market_conditions", {}).get("market_type", "balanced")
        days_on_market = market_data.get("pricing", {}).get("days_on_market", 18)
        discount_data = await self._get_discount_analysis(market_condition, days_on_market)

        # Step 2: Build context for GPT-4o
        user_message = f"""
The seller has responded with a counter-offer.

SELLER'S COUNTER-OFFER:
Price: ${seller_price:,.0f}
Conditions: {seller_message.payload.conditions}
Closing timeline: {seller_message.payload.closing_timeline_days} days
Seller's message: "{seller_message.payload.message}"

CURRENT NEGOTIATION STATUS:
- Round: {self.round} of 5 maximum
- Your budget ceiling: ${BUYER_BUDGET:,}
- Seller's counter: ${seller_price:,.0f}
- Gap from your budget: ${seller_price - BUYER_BUDGET:,.0f} ({'WITHIN BUDGET' if seller_price <= BUYER_BUDGET else 'ABOVE BUDGET'})

FRESH MARKET DATA:
Avg comparable price: ${market_data.get('market_statistics', {}).get('avg_comparable_price', 0):,.0f}
Discount range: {json.dumps(discount_data.get('suggested_offer_prices', {}), indent=2)}

DECISION GUIDANCE:
- If seller counter is at or below ${BUYER_BUDGET:,}, you may consider accepting
- If this is round 4-5 and seller is close to budget, consider accepting
- If seller shows no movement, consider withdrawing
- Otherwise, increase your offer by 2-4%

What is your response?
"""

        # Step 3: GPT-4o decides
        decision = await self._call_llm(user_message)

        print(f"   [Buyer] Decision: {decision.get('offer_price', 'walk-away')} | walk_away={decision.get('walk_away', False)}")

        # Step 4: Handle walk-away
        if decision.get("walk_away", False):
            print(f"   [Buyer] Walking away: {decision.get('walk_away_reason', 'Budget exceeded')}")
            return create_withdrawal(
                session_id=self.session_id,
                round_num=self.round,
                reason=decision.get("walk_away_reason", "Offer exceeds our budget."),
                in_reply_to=self._last_seller_message_id
            )

        # Step 5: Handle acceptance
        offer_price = float(decision.get("offer_price", 0))

        if seller_price <= BUYER_BUDGET and seller_price <= offer_price:
            # Seller is within our budget — accept!
            from m3_agents.a2a_simple import create_acceptance
            print(f"   [Buyer] Accepting seller's counter at ${seller_price:,.0f}")
            return create_acceptance(
                session_id=self.session_id,
                round_num=self.round,
                from_agent="buyer",
                agreed_price=seller_price,
                message=f"We accept your counter-offer of ${seller_price:,.0f}. Looking forward to closing!",
                in_reply_to=self._last_seller_message_id
            )

        # Step 6: Return new offer
        return create_offer(
            session_id=self.session_id,
            round_num=self.round,
            price=offer_price,
            message=decision["message"],
            in_reply_to=self._last_seller_message_id
        )
