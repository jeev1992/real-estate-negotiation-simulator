"""
Buyer Agent — Google ADK Version
====================================
Real estate buyer agent built with Google ADK and Gemini 2.0 Flash.

ADK CONCEPTS DEMONSTRATED:
  1. LlmAgent — defining an agent with model, instruction, and tools
  2. MCPToolset — connecting to MCP servers via stdio transport
  3. Runner — executing the agent and getting responses
  4. InMemorySessionService — managing conversation state across turns

COMPARISON WITH SIMPLE VERSION:
  Simple (buyer_simple.py):
    - Manual MCP client calls
    - Manual conversation history management
    - Returns structured JSON via response_format

  ADK (this file):
    - MCPToolset handles MCP connections automatically
    - ADK Runner manages conversation history via sessions
    - Agent instructions guide response format
    - Gemini 2.0 Flash (free tier)

HOW ADK HANDLES MCP:
  MCPToolset connects to the MCP server and discovers all tools automatically.
  The tools are presented to Gemini as function-calling tools.
  When Gemini decides to call a tool, ADK executes it and feeds the
  result back into the conversation — all automatically.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

# Google ADK imports
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)

from m4_adk_multiagents.adk_a2a_types import ADKNegotiationMessage
from m4_adk_multiagents.messaging_adk import parse_buyer_response, format_seller_message_for_buyer

# Absolute path to pricing server — safe regardless of working directory
_PRICING_SERVER = str(Path(__file__).parent.parent / "m2_mcp" / "pricing_server.py")


# ─── Configuration ────────────────────────────────────────────────────────────

PROPERTY_ADDRESS = "742 Evergreen Terrace, Austin, TX 78701"
LISTING_PRICE = 485_000
BUYER_BUDGET = 460_000
MINIMUM_PRICE = 445_000

# ADK uses Gemini 2.0 Flash — free tier, fast, capable
GEMINI_MODEL = "gemini-2.0-flash"

APP_NAME = "real_estate_negotiation_buyer"

BUYER_INSTRUCTION = f"""You are an expert real estate buyer agent representing a client
purchasing {PROPERTY_ADDRESS} (listed at ${LISTING_PRICE:,}).

YOUR CLIENT'S CONSTRAINTS:
- Maximum budget: ${BUYER_BUDGET:,} (NEVER offer above this — absolute ceiling)
- Target acquisition price: $445,000–$455,000
- Walk-away price: If seller won't go below ${BUYER_BUDGET:,}
- Can close in 30–45 days
- Pre-approved for financing

YOUR STRATEGY:
- BEFORE every offer, call get_market_price to get comparable sales data
- BEFORE every offer, call calculate_discount to determine the right range
- Round 1: Offer ~12% below asking ($425,000)
- Each subsequent round: Increase by 2–4%
- Use market data to justify EVERY offer
- Emphasize your financing approval as a strength
- Walk away (set walk_away: true) if seller won't go below ${BUYER_BUDGET:,}

AVAILABLE MCP TOOLS (auto-discovered from pricing server):
- get_market_price(address, property_type) → market comps, estimated value
- calculate_discount(base_price, market_condition, days_on_market) → offer ranges

RESPONSE FORMAT — always respond with valid JSON:
{{
    "offer_price": <integer — your offer in dollars>,
    "message": "<professional message to seller with market data justification>",
    "reasoning": "<internal notes — your strategy>",
    "walk_away": <true/false>,
    "walk_away_reason": "<optional — only if walk_away is true>",
    "conditions": ["<list of offer conditions>"],
    "closing_timeline_days": <integer>
}}

CRITICAL: Always call MCP tools BEFORE deciding your offer price.
CRITICAL: Never include commas in numeric values in JSON."""


# ─── ADK Agent Factory ────────────────────────────────────────────────────────

class BuyerAgentADK:
    """
    ADK-based buyer agent that wraps an LlmAgent with MCPToolset.

    ADK LIFECYCLE:
    1. __init__: Set up configuration (no connections yet)
    2. __aenter__: Connect to MCP servers, create LlmAgent, create Runner
    3. make_offer / respond_to_counter: Execute agent turns via Runner
    4. __aexit__: Close MCP connections and clean up

    WHY CONTEXT MANAGER?
    MCPToolset connections need to be properly cleaned up.
    Using async context manager ensures connections close even if errors occur.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.user_id = "buyer_agent"

        # Will be initialized in __aenter__
        self._agent: Optional[LlmAgent] = None
        self._runner: Optional[Runner] = None
        self._session_service: Optional[InMemorySessionService] = None
        self._pricing_toolset: Optional[MCPToolset] = None
        self._round = 0

    async def __aenter__(self) -> "BuyerAgentADK":
        """
        Initialize the ADK agent with MCP tools.

        ADK TEACHING POINT:
        This is where MCPToolset connects to the MCP server, discovers
        all available tools, and makes them available to the LlmAgent.
        The LlmAgent's Gemini model can then call these tools automatically.
        """
        print("   [Buyer ADK] Connecting to pricing MCP server...")

        # Create MCPToolset — this is the ADK's MCP integration
        # StdioServerParameters tells ADK how to spawn the MCP server
        # Store as instance variable so __aexit__ can close the subprocess.
        self._pricing_toolset = MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                )
            )
        )

        # Initialize tools from the MCP server
        # ADK discovers available tools via MCP's list_tools protocol
        # These tools are then formatted as Gemini function-calling tools
        tools = await self._pricing_toolset.get_tools()

        # Safe tool name extraction — handles empty list without IndexError
        tool_names = [t.name for t in tools if hasattr(t, 'name')]
        print(f"   [Buyer ADK] Discovered MCP tools: {tool_names if tool_names else 'none'}")

        # Create the LlmAgent with discovered MCP tools
        self._agent = LlmAgent(
            name="buyer_agent",
            model=GEMINI_MODEL,
            description=f"Real estate buyer agent for {PROPERTY_ADDRESS}",
            instruction=BUYER_INSTRUCTION,
            tools=tools,
        )

        # Create session service (manages conversation history)
        self._session_service = InMemorySessionService()

        # Create runner (executes the agent)
        self._runner = Runner(
            agent=self._agent,
            app_name=APP_NAME,
            session_service=self._session_service,
        )

        # Create the session for this negotiation
        await self._session_service.create_session(
            app_name=APP_NAME,
            user_id=self.user_id,
            session_id=self.session_id,
        )

        print(f"   [Buyer ADK] Agent ready. Model: {GEMINI_MODEL}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close MCP server subprocess."""
        if self._pricing_toolset is not None:
            try:
                await self._pricing_toolset.close()
            except Exception:
                pass
        print("   [Buyer ADK] MCP connections closed.")

    async def _run_agent(self, prompt: str) -> str:
        """
        Execute one turn of the agent and return its text response.

        ADK TEACHING POINT:
        runner.run_async() returns an async generator of events.
        Events can be: tool calls, tool results, partial responses, final response.
        We collect events until we get is_final_response().

        The agent may call MCP tools multiple times per turn before
        returning its final response. ADK handles this loop automatically.
        """
        from google.genai.types import Content, Part

        content = Content(parts=[Part(text=prompt)])

        final_response = ""
        async for event in self._runner.run_async(
            user_id=self.user_id,
            session_id=self.session_id,
            new_message=content,
        ):
            # Show tool calls for educational purposes
            if hasattr(event, 'tool_calls') and event.tool_calls:
                for tc in event.tool_calls:
                    print(f"   [Buyer ADK] Calling tool: {tc.function.name}({tc.function.arguments[:50]}...)")

            # Capture final response
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        final_response += part.text

        return final_response

    async def make_initial_offer(self) -> ADKNegotiationMessage:
        """Make the opening offer via ADK agent."""
        self._round = 1
        print(f"\n[Buyer ADK] Round {self._round}: Making initial offer...")

        prompt = f"""You are making your INITIAL offer on {PROPERTY_ADDRESS} (listed at ${LISTING_PRICE:,}).

INSTRUCTIONS:
1. First, call get_market_price("{PROPERTY_ADDRESS}", "single_family") to get market data
2. Then call calculate_discount({LISTING_PRICE}, market_condition, days_on_market) with values from step 1
3. Based on this data, formulate your opening offer (start ~12% below asking)
4. Return your response as JSON with: offer_price, message, reasoning, walk_away, conditions, closing_timeline_days

This is Round 1 of 5. Make a strong opening offer backed by market data."""

        raw_response = await self._run_agent(prompt)
        print(f"   [Buyer ADK] Raw response length: {len(raw_response)} chars")

        # Parse the response into an ADKNegotiationMessage
        message = parse_buyer_response(
            raw_response=raw_response,
            session_id=self.session_id,
            round_num=self._round,
        )

        print(f"   [Buyer ADK] Offer: ${message.payload.price:,.0f}")
        return message

    async def respond_to_counter(self, seller_message: ADKNegotiationMessage) -> ADKNegotiationMessage:
        """Respond to a seller counter-offer."""
        self._round = seller_message.round
        print(f"\n[Buyer ADK] Round {self._round}: Responding to counter ${seller_message.payload.price:,.0f}...")

        # Format the seller's A2A message as a prompt
        prompt = format_seller_message_for_buyer(seller_message, self._round)

        raw_response = await self._run_agent(prompt)
        print(f"   [Buyer ADK] Raw response length: {len(raw_response)} chars")

        message = parse_buyer_response(
            raw_response=raw_response,
            session_id=self.session_id,
            round_num=self._round + 1,
            in_reply_to=seller_message.message_id
        )

        if message.payload.price:
            print(f"   [Buyer ADK] Next offer: ${message.payload.price:,.0f}")
        else:
            print(f"   [Buyer ADK] Decision: {message.message_type}")

        return message
