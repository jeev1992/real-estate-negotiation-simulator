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

  3. STATE OUTPUT: The agent produces a negotiation message dict that
      LangGraph stores in shared state for the seller node.

  4. STATE: The agent maintains its conversation history (buyer_llm_messages)
     across rounds so GPT-4o remembers previous offers and counters.

FLOW PER ROUND:
  1. Receive seller's counter-offer from shared LangGraph state
  2. GPT-4o decides which MCP tools to call this round (ReAct-style planning)
  3. Agent executes those MCP calls (get_market_price, calculate_discount)
  4. Add market data + counter to GPT-4o context
  5. GPT-4o decides next offer (or walk-away)
  6. Return a negotiation message dict with the decision

WHY LLM-DRIVEN TOOL SELECTION (not hardcoded):
  The whole point of an agent is that it decides its own actions.
  If we hardcode "always call these 2 tools," we've written a script.
  The planner call is cheap (temp=0, tiny prompt) and teaches the right pattern:
  the agent reads context, decides what information it needs, then acts.
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

from m3_langgraph_multiagents.negotiation_types import (
    NegotiationMessage,
    create_offer,
    create_withdrawal,
    create_acceptance,
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

BUYER_MCP_PLANNER_PROMPT = """You are selecting MCP tools for a buyer negotiation agent.

Return strict JSON in this format:
{
    "tool_calls": [
        {"tool": "<tool_name>", "arguments": { ... }}
    ]
}

Available tools and required arguments:
- get_market_price: {"address": "string", "property_type": "single_family|condo|townhouse"}
- calculate_discount: {
        "base_price": number,
        "market_condition": "hot|balanced|cold",
        "days_on_market": number,
        "property_condition": "excellent|good|fair|poor"
    }

Rules:
- Call 1-2 tools only.
- Prefer get_market_price first when market context is stale or unknown.
- Call calculate_discount when offer-range guidance is needed.
- Never invent tools outside the list.
- Output JSON only.
"""


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
    4. Converts the LLM response to a negotiation message dict

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


    async def _plan_mcp_tool_calls(self, planning_context: str) -> list[dict]:
        """
        Ask GPT-4o which MCP tools to call this round.

        AGENT TEACHING POINT:
        This is the ReAct-style planning step. The agent reads the current
        context (round, seller counter, budget gap) and decides what information
        it needs before formulating its response. This is what makes it an agent
        rather than a hardcoded script.

        Uses temp=0 and a minimal prompt so the decision is fast and cheap.
        """
        response = await self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": BUYER_MCP_PLANNER_PROMPT},
                {"role": "user", "content": planning_context},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        content = response.choices[0].message.content
        parsed = json.loads(content)
        tool_calls = parsed.get("tool_calls", [])

        allowed_tools = {"get_market_price", "calculate_discount"}
        valid_calls: list[dict] = []

        for call in tool_calls:
            tool = call.get("tool")
            arguments = call.get("arguments", {})
            if tool in allowed_tools and isinstance(arguments, dict):
                valid_calls.append({"tool": tool, "arguments": arguments})

        return valid_calls[:2]

    async def _gather_mcp_context(
        self,
        stage: str,
        seller_price: Optional[float] = None,
    ) -> tuple[dict, dict]:
        """
        Let the agent decide which MCP tools to call, then execute them.

        The two-step pattern here is intentional and teachable:
          Step 1 (plan):    GPT-4o reads context, returns {"tool_calls": [...]}
          Step 2 (execute): We call those tools and return the results

        Compare to M4 (ADK): Gemini does the same thing automatically inside
        MCPToolset's function-calling loop. Here we make the mechanism visible.
        """
        planning_context = (
            f"Stage: {stage}\n"
            f"Property: {PROPERTY_ADDRESS}\n"
            f"Listing price: {LISTING_PRICE}\n"
            f"Buyer budget: {BUYER_BUDGET}\n"
            f"Seller counter (if any): {seller_price if seller_price is not None else 'N/A'}\n"
            "Need market comparables and tactical pricing guidance for next buyer response."
        )

        market_data: dict = {}
        discount_data: dict = {}

        try:
            planned_calls = await self._plan_mcp_tool_calls(planning_context)
            print(f"   [Buyer] Agent planned MCP calls: {[c['tool'] for c in planned_calls]}")

            for call in planned_calls:
                tool = call["tool"]
                arguments = call["arguments"]

                if tool == "get_market_price":
                    args = {
                        "address": arguments.get("address", PROPERTY_ADDRESS),
                        "property_type": arguments.get("property_type", "single_family"),
                    }
                    print("   [Buyer] Calling MCP: get_market_price...")
                    market_data = await call_pricing_mcp("get_market_price", args)
                    print(f"   [Buyer] MCP returned: avg comp ${market_data.get('market_statistics', {}).get('avg_comparable_price', 'N/A'):,}")

                elif tool == "calculate_discount":
                    args = {
                        "base_price": float(arguments.get("base_price", LISTING_PRICE)),
                        "market_condition": arguments.get("market_condition", "balanced"),
                        "days_on_market": int(arguments.get("days_on_market", 18)),
                        "property_condition": arguments.get("property_condition", "good"),
                    }
                    print("   [Buyer] Calling MCP: calculate_discount...")
                    discount_data = await call_pricing_mcp("calculate_discount", args)
                    print(f"   [Buyer] MCP returned: offer range ${discount_data.get('suggested_offer_prices', {}).get('moderate', 'N/A'):,}")

            if not planned_calls:
                print("   [Buyer] Agent planned no MCP calls this round")

        except Exception as e:
            print(f"   [Buyer] MCP planning error (continuing without MCP data): {e}")

        self._market_data = market_data
        return market_data, discount_data

    async def make_initial_offer(self) -> NegotiationMessage:
        """
        Make the opening offer.

        Called at round 1, before any seller counter-offer exists.
        The agent fetches market data and uses it to justify its opening bid.
        """
        self.round = 1
        print(f"\n[Buyer] Round {self.round}: Preparing initial offer...")

        # Step 1: Agent decides which MCP tools to call, then executes them
        market_data, discount_data = await self._gather_mcp_context(stage="initial_offer")

        # Step 2: Build context for GPT-4o
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

        # Step 3: GPT-4o decides the offer
        decision = await self._call_llm(user_message)

        print(f"   [Buyer] Decision: offer ${decision.get('offer_price', 0):,}")
        print(f"   [Buyer] Reasoning: {decision.get('reasoning', '')[:80]}...")

        # Step 4: Convert to negotiation message
        return create_offer(
            session_id=self.session_id,
            round_num=self.round,
            price=float(decision["offer_price"]),
            message=decision["message"],
        )

    async def respond_to_counter(self, seller_message: NegotiationMessage) -> NegotiationMessage:
        """
        Respond to a seller counter-offer.

        The agent adds the seller's counter to its LLM context and
        calls GPT-4o to decide whether to increase the offer, accept, or walk away.
        """
        self.round += 1
        self._last_seller_message_id = seller_message["message_id"]

        print(f"\n[Buyer] Round {self.round}: Received counter-offer ${seller_message.get('price', 0):,.0f}")

        # Sanity check: if seller already came below our budget, consider accepting
        seller_price = seller_message.get("price") or 0

        # Step 1: Agent decides which MCP tools to call, then executes them
        market_data, discount_data = await self._gather_mcp_context(
            stage="respond_to_counter",
            seller_price=float(seller_price),
        )

        # Step 2: Build context for GPT-4o
        user_message = f"""
The seller has responded with a counter-offer.

SELLER'S COUNTER-OFFER:
Price: ${seller_price:,.0f}
Conditions: {seller_message.get('conditions', [])}
Closing timeline: {seller_message.get('closing_timeline_days')} days
Seller's message: "{seller_message.get('message', '')}"

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
