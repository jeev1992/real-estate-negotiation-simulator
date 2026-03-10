"""
Seller Agent — ADK + OpenAI Version
=====================================
Real estate seller agent built with Google ADK and OpenAI GPT-4o.

KEY ADK DIFFERENCE FROM BUYER:
  The seller connects to TWO MCPToolsets simultaneously:
  - pricing_server: get_market_price, calculate_discount
  - inventory_server: get_inventory_level, get_minimum_acceptable_price

  ADK's MCPToolset handles both connections independently.
    The agent sees all tools from both servers as a unified tool list.
    The model decides which tools to call based on the context.

INFORMATION ASYMMETRY (A2A TEACHING POINT):
  Seller has: get_minimum_acceptable_price (knows its floor)
  Buyer does NOT have this tool

  This mirrors real estate reality and demonstrates how MCP
  access control creates information asymmetry between agents.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Literal, Optional

from google.adk.agents import LlmAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from pydantic import BaseModel, Field, ValidationError

# Absolute paths to MCP servers
_REPO_ROOT = Path(__file__).parent.parent
_PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m2_mcp" / "inventory_server.py")


# ─── Configuration ────────────────────────────────────────────────────────────

PROPERTY_ADDRESS = "742 Evergreen Terrace, Austin, TX 78701"
PROPERTY_ID = "742-evergreen-austin-78701"
LISTING_PRICE = 485_000
MINIMUM_PRICE = 445_000
IDEAL_PRICE = 465_000

# ADK provider-style model id used by google-adk + litellm bridge.
OPENAI_MODEL = "openai/gpt-4o"
APP_NAME = "real_estate_negotiation_seller"


class SellerStructuredOutput(BaseModel):
    counter_price: Optional[float] = None
    counter_offer: Optional[float] = None
    price: Optional[float] = None
    agreed_price: Optional[float] = None
    message: str
    reasoning: Optional[str] = None
    accept: bool = False
    reject: bool = False
    conditions: list[str] = Field(default_factory=list)
    closing_timeline_days: Optional[int] = None


class SellerEnvelope(BaseModel):
    session_id: str
    round: int
    from_agent: Literal["seller"] = "seller"
    to_agent: Literal["buyer"] = "buyer"
    message_type: Literal["COUNTER_OFFER", "ACCEPT", "REJECT"]
    price: Optional[float] = None
    message: str
    conditions: list[str] = Field(default_factory=list)
    closing_timeline_days: Optional[int] = None
    in_reply_to: Optional[str] = None


def _parse_strict_json_output(raw_text: str) -> SellerStructuredOutput:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Model output is not valid JSON: {error}") from error

    try:
        return SellerStructuredOutput.model_validate(parsed)
    except ValidationError as error:
        raise ValueError(f"Model output failed SellerStructuredOutput validation: {error}") from error


def _format_buyer_envelope_for_seller(buyer_message: dict, round_num: int) -> str:
    price = buyer_message.get("price")
    price_str = f"${price:,.0f}" if isinstance(price, (int, float)) else "N/A"
    conditions_list = buyer_message.get("conditions")
    conditions = ", ".join(conditions_list) if isinstance(conditions_list, list) and conditions_list else "Standard terms"
    days = buyer_message.get("closing_timeline_days") or 45
    buyer_type = buyer_message.get("message_type", "OFFER")
    buyer_text = buyer_message.get("message", "")
    return f"""BUYER'S OFFER (Round {round_num}):

Message type: {buyer_type}
Offer price: {price_str}
Conditions: {conditions}
Closing timeline: {days} days
Buyer's justification: "{buyer_text}"

This is round {round_num} of 5 maximum rounds.

Please evaluate this offer and respond.
Remember to call get_market_price, get_inventory_level, and get_minimum_acceptable_price.
Respond with a JSON object: counter_price, message, reasoning, accept, reject.
Return ONLY JSON. No markdown fences. No prose outside JSON."""

SELLER_INSTRUCTION = f"""You are an expert real estate listing agent representing the sellers of
{PROPERTY_ADDRESS} (listed at ${LISTING_PRICE:,}).

PROPERTY HIGHLIGHTS (emphasize these in every response):
  • Kitchen fully renovated 2023: $45,000 (quartz counters, Bosch appliances)
  • New roof 2022: $18,000 (30-year architectural shingles, transferable warranty)
  • HVAC replaced 2021: $12,000 (Carrier 16 SEER, energy-efficient)
  • Total recent upgrades: $75,000+
  • School district: Austin ISD — rated 8/10
  • Zero HOA fees (saves ~$300/month vs comparable properties)

YOUR STRATEGY:
BEFORE responding to any offer:
1. Call get_market_price("{PROPERTY_ADDRESS}", "single_family") to understand the market
2. Call get_inventory_level("78701") to understand market pressure
3. Call get_minimum_acceptable_price("{PROPERTY_ID}") to confirm your floor price

PRICING STRATEGY:
- Start counter at $477,000 (Round 1)
- Drop by $5,000–$8,000 per round only
- NEVER go below the minimum from get_minimum_acceptable_price()
- If buyer offers at or above minimum, ACCEPT immediately
- Emphasize $75,000 in upgrades to justify premium pricing

AVAILABLE MCP TOOLS (from pricing + inventory servers):
Pricing server:
  - get_market_price(address, property_type)
  - calculate_discount(base_price, market_condition, days_on_market)
Inventory server:
  - get_inventory_level(zip_code)
  - get_minimum_acceptable_price(property_id)

RESPONSE FORMAT — always respond with valid JSON:
{{
    "counter_price": <integer — your counter-offer in dollars>,
    "message": "<professional message to buyer referencing property value>",
    "reasoning": "<internal notes — your strategy>",
    "accept": <true if accepting buyer's offer, false otherwise>,
    "reject": <true if terminating, false otherwise>,
    "conditions": ["<list of conditions>"],
    "closing_timeline_days": <integer>
}}

CRITICAL RULES:
- Call get_minimum_acceptable_price FIRST to know your absolute floor
- NEVER counter below that minimum (it's your mortgage payoff requirement)
- If buyer is at or above minimum → set accept: true
- Always reference the $75,000 in upgrades to justify your price
- Be firm but professional
CRITICAL OUTPUT RULE: Return ONLY one JSON object with no extra text or markdown fences."""


# ─── ADK Seller Agent ─────────────────────────────────────────────────────────

class SellerAgentADK:
    """
    ADK-based seller agent with dual MCP server connections.

    ADK CONCEPT — MULTIPLE MCPToolsets:
    An agent can connect to multiple MCP servers simultaneously.
    ADK merges the tool lists from all servers into one unified list.
    The agent instruction tells the model when to use tools from each server.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.user_id = "seller_agent"

        self._agent: Optional[LlmAgent] = None
        self._runner: Optional[Runner] = None
        self._session_service: Optional[InMemorySessionService] = None
        self._pricing_toolset: Optional[MCPToolset] = None
        self._inventory_toolset: Optional[MCPToolset] = None
        self._round = 0

    async def _append_state_delta(self, state_delta: dict) -> None:
        if self._session_service is None:
            return
        session = await self._session_service.get_session(
            app_name=APP_NAME,
            user_id=self.user_id,
            session_id=self.session_id,
        )
        if session is None:
            return
        await self._session_service.append_event(
            session=session,
            event=Event(author=self.user_id, actions=EventActions(stateDelta=state_delta)),
        )

    async def __aenter__(self) -> "SellerAgentADK":
        """
        Initialize with connections to BOTH MCP servers.

        ADK CONCEPT — DUAL MCP CONNECTION:
        We create two MCPToolsets and merge their tools into one list.
        The LlmAgent receives tools from both servers as if they're unified.
        """
        print("   [Seller ADK] Connecting to pricing MCP server...")

        # Toolset 1: Pricing server (shared with buyer)
        # Stored as instance variable so __aexit__ can close the subprocess.
        self._pricing_toolset = MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                )
            )
        )
        pricing_tools = await self._pricing_toolset.get_tools()
        pricing_names = [t.name for t in pricing_tools if hasattr(t, 'name')]
        print(f"   [Seller ADK] Pricing tools: {pricing_names if pricing_names else 'none'}")

        print("   [Seller ADK] Connecting to inventory MCP server...")

        # Toolset 2: Inventory server (seller ONLY)
        # Stored as instance variable so __aexit__ can close the subprocess.
        self._inventory_toolset = MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_INVENTORY_SERVER],
                )
            )
        )
        inventory_tools = await self._inventory_toolset.get_tools()
        inventory_names = [t.name for t in inventory_tools if hasattr(t, 'name')]
        print(f"   [Seller ADK] Inventory tools: {inventory_names if inventory_names else 'none'}")

        # Merge tools from both MCP servers so the model can choose among them
        # in a single ADK tool-calling loop.
        all_tools = list(pricing_tools) + list(inventory_tools)
        print(f"   [Seller ADK] Total tools available: {len(all_tools)}")
        print(f"   [Seller ADK] KEY: Seller has get_minimum_acceptable_price; Buyer does NOT")

        # Create agent with all tools
        self._agent = LlmAgent(
            name="seller_agent",
            model=OPENAI_MODEL,
            description=f"Real estate seller agent for {PROPERTY_ADDRESS}",
            instruction=SELLER_INSTRUCTION,
            tools=all_tools,
        )

        self._session_service = InMemorySessionService()
        self._runner = Runner(
            agent=self._agent,
            app_name=APP_NAME,
            session_service=self._session_service,
        )

        await self._session_service.create_session(
            app_name=APP_NAME,
            user_id=self.user_id,
            session_id=self.session_id,
            state={"round": 0, "status": "negotiating", "last_message_type": "NONE"},
        )

        print(f"   [Seller ADK] Agent ready. Model: {OPENAI_MODEL}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close both MCP server subprocesses."""
        for toolset in (self._pricing_toolset, self._inventory_toolset):
            if toolset is not None:
                try:
                    await toolset.close()
                except Exception:
                    pass
        print("   [Seller ADK] MCP connections closed.")

    async def _run_agent(self, prompt: str) -> str:
        """Execute one agent turn and return text response."""
        from google.genai.types import Content, Part

        content = Content(parts=[Part(text=prompt)])

        # Collect final response text after any intermediate tool-call events.
        final_response = ""
        async for event in self._runner.run_async(
            user_id=self.user_id,
            session_id=self.session_id,
            new_message=content,
        ):
            # Show tool calls for educational visibility
            if hasattr(event, 'tool_calls') and event.tool_calls:
                for tc in event.tool_calls:
                    print(f"   [Seller ADK] Calling tool: {tc.function.name}")

            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        final_response += part.text

        return final_response

    async def respond_to_offer_envelope(self, buyer_message: dict) -> dict:
        """Respond to buyer JSON envelope and return seller JSON envelope."""
        self._round = int(buyer_message.get("round", 1))
        buyer_price = float(buyer_message.get("price") or 0)

        print(f"\n[Seller ADK] Round {self._round}: Responding to offer ${buyer_price:,.0f}...")

        prompt = _format_buyer_envelope_for_seller(buyer_message, self._round)

        # Add explicit instruction to use all tools to preserve information asymmetry
        # behavior and ensure floor-price checks happen every round.
        prompt += f"""

IMPORTANT: Before responding, call these tools in order:
1. get_market_price("{PROPERTY_ADDRESS}", "single_family")
2. get_inventory_level("78701")
3. get_minimum_acceptable_price("{PROPERTY_ID}")

Then formulate your counter-offer or acceptance.
Remember: if buyer's ${buyer_price:,.0f} meets your minimum, ACCEPT.
Return ONLY JSON. No markdown fences. No prose outside JSON."""

        raw_response = await self._run_agent(prompt)
        print(f"   [Seller ADK] Raw response length: {len(raw_response)} chars")

        parsed = _parse_strict_json_output(raw_response)
        if parsed.accept:
            agreed_price = parsed.agreed_price or buyer_price
            envelope = SellerEnvelope(
                session_id=buyer_message.get("session_id", self.session_id),
                round=self._round,
                message_type="ACCEPT",
                price=float(agreed_price),
                message=parsed.message,
                conditions=parsed.conditions,
                closing_timeline_days=parsed.closing_timeline_days,
                in_reply_to=buyer_message.get("message_id"),
            )
            status = "agreed"
        else:
            counter_price = parsed.counter_price or parsed.counter_offer or parsed.price or 477_000.0
            counter_price = max(float(counter_price), float(MINIMUM_PRICE))
            envelope = SellerEnvelope(
                session_id=buyer_message.get("session_id", self.session_id),
                round=self._round,
                message_type="COUNTER_OFFER",
                price=counter_price,
                message=parsed.message,
                conditions=parsed.conditions or ["As-is condition"],
                closing_timeline_days=parsed.closing_timeline_days or 30,
                in_reply_to=buyer_message.get("message_id"),
            )
            status = "negotiating"

        await self._append_state_delta(
            {
                "round": self._round,
                "status": status,
                "last_message_type": envelope.message_type,
                "last_counter_price": envelope.price,
            }
        )

        if envelope.price is not None:
            print(f"   [Seller ADK] Counter: ${envelope.price:,.0f} | type={envelope.message_type}")

        return envelope.model_dump(mode="json")

