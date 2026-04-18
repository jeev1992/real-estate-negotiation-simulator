"""
Buyer Agent — ADK + OpenAI Version
====================================
Real estate buyer agent built with Google ADK and OpenAI GPT-4o.

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
    - OpenAI GPT-4o model family

HOW ADK HANDLES MCP:
  MCPToolset connects to the MCP server and discovers all tools automatically.
    The tools are presented to the LLM as function-calling tools.
    When the model decides to call a tool, ADK executes it and feeds the
  result back into the conversation — all automatically.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Literal, Optional

# Google ADK imports
from google.adk.agents import LlmAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from google.adk.tools.tool_context import ToolContext
from pydantic import BaseModel, Field, ValidationError

# Buyer is allowed to call only pricing tools — never the seller-private
# inventory tools (information asymmetry enforced via callback, not trust).
_BUYER_ALLOWED_TOOLS = {"get_market_price", "calculate_discount", "get_property_tax_estimate"}


def _enforce_buyer_tool_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
    """before_tool_callback — block any tool not on the buyer allowlist.

    Returning a dict short-circuits the tool call and feeds the result back
    to the model as if the tool had run. None means "allow the call".
    """
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the buyer agent"}
    return None

# Absolute path to pricing server — safe regardless of working directory
_PRICING_SERVER = str(Path(__file__).parent.parent / "m2_mcp" / "pricing_server.py")


# ─── Configuration ────────────────────────────────────────────────────────────

PROPERTY_ADDRESS = "742 Evergreen Terrace, Austin, TX 78701"
LISTING_PRICE = 485_000
BUYER_BUDGET = 460_000

# ADK provider-style model id.
# Important: plain "gpt-4o" is not resolved by ADK registry in this setup.
OPENAI_MODEL = "openai/gpt-4o"

APP_NAME = "real_estate_negotiation_buyer"


# ─── Pydantic models for strict LLM output parsing ───────────────────────────
#
# TWO MODELS, TWO ROLES:
#
#   BuyerStructuredOutput  (INTERNAL — permissive)
#     What GPT-4o returns as raw text. Has fallback field names
#     (offer_price, price) because the LLM's naming varies.
#     Also has private fields like `reasoning` that never leave this process.
#
#   BuyerEnvelope  (EXTERNAL — strict)
#     What gets sent to the seller over the A2A HTTP boundary.
#     Has exactly ONE price field. Has a strict Literal message_type.
#     No reasoning field (private notes stay internal).
#
# The conversion happens in make_initial_offer_envelope() / respond_to_counter_envelope():
#   GPT-4o text → BuyerStructuredOutput → business logic → BuyerEnvelope → dict
#
# Why two models instead of one?
# - The LLM can't be trusted to use consistent field names
# - Business rules (budget cap) must run BETWEEN parse and send
# - Private fields (reasoning) must never cross the agent boundary
#

class BuyerStructuredOutput(BaseModel):
    """Schema for the raw JSON that GPT-4o returns inside runner.run_async()."""
    offer_price: Optional[float] = None       # the buyer's proposed price
    price: Optional[float] = None             # fallback field (LLM sometimes uses this name)
    message: str                              # human-readable justification for the offer
    reasoning: Optional[str] = None           # private strategy notes (not shown to seller)
    walk_away: bool = False                   # True = buyer is withdrawing from negotiation
    walk_away_reason: Optional[str] = None    # explanation if walking away
    conditions: list[str] = Field(default_factory=list)  # e.g. ["inspection contingency"]
    closing_timeline_days: Optional[int] = None


class BuyerEnvelope(BaseModel):
    """The structured message sent to the seller (over the A2A HTTP boundary).

    This is the A2A-compatible contract — a strict envelope with a typed
    `message_type` and a single `price` field, so the seller always receives
    a predictable, validated payload.
    """
    session_id: str                                    # ties all rounds together
    round: int                                         # 1-indexed round number
    from_agent: Literal["buyer"] = "buyer"              # always "buyer" (typed, not a free string)
    to_agent: Literal["seller"] = "seller"              # always "seller"
    message_type: Literal["OFFER", "WITHDRAW"]          # explicit action — no string matching
    price: Optional[float] = None                      # the offer amount (None only on WITHDRAW)
    message: str                                       # human-readable text for the seller
    conditions: list[str] = Field(default_factory=list) # contingencies (inspection, financing)
    closing_timeline_days: Optional[int] = None        # proposed close window
    in_reply_to: Optional[str] = None                  # message_id of the seller's last message


def _parse_strict_json_output(raw_text: str) -> BuyerStructuredOutput:
    """Parse LLM output into a validated Pydantic model, or raise immediately.

    Why strict? In A2A systems, one agent's output is another agent's input.
    If we silently accept malformed JSON, the seller receives corrupt data
    and the negotiation produces meaningless results with no error trace.
    Fail-fast here means bugs surface at the source, not downstream.
    """
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Model output is not valid JSON: {error}") from error

    try:
        return BuyerStructuredOutput.model_validate(parsed)
    except ValidationError as error:
        raise ValueError(f"Model output failed BuyerStructuredOutput validation: {error}") from error


def _format_seller_envelope_for_buyer(seller_message: dict, round_num: int) -> str:
    """Convert the seller's JSON envelope into a readable prompt for GPT-4o.

    The seller sends structured JSON (price, conditions, message_type).
    GPT-4o works better with natural-language context, so we render the
    envelope fields into a formatted prompt that the buyer agent can reason about.
    """
    price = seller_message.get("price")
    price_str = f"${price:,.0f}" if isinstance(price, (int, float)) else "N/A"
    conditions_list = seller_message.get("conditions")
    conditions = ", ".join(conditions_list) if isinstance(conditions_list, list) and conditions_list else "Standard terms"
    days = seller_message.get("closing_timeline_days") or 30
    seller_type = seller_message.get("message_type", "COUNTER_OFFER")
    seller_text = seller_message.get("message", "")
    return f"""SELLER'S RESPONSE (Round {round_num}):

Message type: {seller_type}
Counter-offer price: {price_str}
Conditions: {conditions}
Closing timeline: {days} days
Seller's message: "{seller_text}"

This is round {round_num} of 5 maximum rounds.

Please respond with your next offer or decision.
Remember to call your available MCP tools before making your offer.
Respond with a JSON object containing: offer_price, message, reasoning, walk_away, walk_away_reason.
Return ONLY JSON. No markdown fences. No prose outside JSON."""

BUYER_INSTRUCTION_TEMPLATE = f"""You are an expert real estate buyer agent representing a client
purchasing {PROPERTY_ADDRESS} (listed at ${LISTING_PRICE:,}).

YOUR CLIENT'S CONSTRAINTS:
- Maximum budget: ${BUYER_BUDGET:,} (NEVER offer above this — absolute ceiling)
- Target acquisition price: $445,000–$455,000
- Walk-away price: If seller won't go below ${BUYER_BUDGET:,}
- Can close in 30–45 days
- Pre-approved for financing

YOUR STRATEGY:
- BEFORE every offer, call your available MCP tools to get market data
- Round 1: Offer ~12% below asking ($425,000)
- Each subsequent round: Increase by 2–4%
- Use market data to justify EVERY offer
- Emphasize your financing approval as a strength
- Walk away (set walk_away: true) if seller won't go below ${BUYER_BUDGET:,}

AVAILABLE MCP TOOLS (auto-discovered from pricing server):
{{tools_section}}

RESPONSE FORMAT — always respond with valid JSON:
{{{{
    "offer_price": <integer — your offer in dollars>,
    "message": "<professional message to seller with market data justification>",
    "reasoning": "<internal notes — your strategy>",
    "walk_away": <true/false>,
    "walk_away_reason": "<optional — only if walk_away is true>",
    "conditions": ["<list of offer conditions>"],
    "closing_timeline_days": <integer>
}}}}

CRITICAL: Always call MCP tools BEFORE deciding your offer price.
CRITICAL: Never include commas in numeric values in JSON.
CRITICAL OUTPUT RULE: Return ONLY one JSON object with no extra text or markdown fences."""


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
        self._tool_names: list[str] = []  # populated in __aenter__ after discovery

    async def _append_state_delta(self, state_delta: dict) -> None:
        # Persist lightweight turn metadata in ADK session state for observability.
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

    async def __aenter__(self) -> "BuyerAgentADK":
        """
        Initialize the ADK agent with MCP tools.

        ADK TEACHING POINT:
        This is where MCPToolset connects to the MCP server, discovers
        all available tools, and makes them available to the LlmAgent.
        The LlmAgent can then call these tools automatically.
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
        # These tools are then formatted for model function-calling
        tools = await self._pricing_toolset.get_tools()

        # Safe tool name extraction — handles empty list without IndexError
        tool_names = [t.name for t in tools if hasattr(t, 'name')]
        self._tool_names = tool_names
        print(f"   [Buyer ADK] Discovered MCP tools: {tool_names if tool_names else 'none'}")

        # Build the instruction dynamically with discovered tool names.
        # The tool list in the prompt is informational coaching — ADK already
        # gives the LLM function-calling access to all tools. But naming them
        # in the instruction helps the LLM use them strategically.
        tools_section = "\n".join(f"- {name}" for name in tool_names) if tool_names else "(none discovered)"
        buyer_instruction = BUYER_INSTRUCTION_TEMPLATE.format(tools_section=tools_section)

        # Create the LlmAgent with discovered MCP tools.
        # before_tool_callback enforces the buyer's tool allowlist so the
        # model can never accidentally invoke a seller-only inventory tool.
        self._agent = LlmAgent(
            name="buyer_agent",
            model=OPENAI_MODEL,
            description=f"Real estate buyer agent for {PROPERTY_ADDRESS}",
            instruction=buyer_instruction,
            tools=tools,
            before_tool_callback=_enforce_buyer_tool_allowlist,
        )

        # Create session service (manages conversation history)
        self._session_service = InMemorySessionService()

        # Create runner (executes the agent)
        self._runner = Runner(
            agent=self._agent,
            app_name=APP_NAME,
            session_service=self._session_service,
        )

        # Create the session for this negotiation.
        # The "user:" prefix scopes max_budget to the user_id so it survives
        # across sessions for the same buyer — useful when the same buyer
        # negotiates on multiple properties.
        await self._session_service.create_session(
            app_name=APP_NAME,
            user_id=self.user_id,
            session_id=self.session_id,
            state={
                "round": 0,
                "status": "negotiating",
                "last_message_type": "NONE",
                "user:max_budget": BUYER_BUDGET,
            },
        )

        print(f"   [Buyer ADK] Agent ready. Model: {OPENAI_MODEL}")
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

        # ADK emits many events (tool call, tool result, partial text, final text).
        # We keep collecting until the final response event is emitted.
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

            # Capture final response text parts only.
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        final_response += part.text

        print("   [Buyer ADK] Raw response text:")
        print(final_response)
        return final_response

    async def make_initial_offer_envelope(self) -> dict:
        """Make the opening offer and return A2A JSON envelope."""
        self._round = 1
        print(f"\n[Buyer ADK] Round {self._round}: Making initial offer...")

        # Prompt intentionally instructs tool calls first so pricing is data-grounded.
        tool_list = ", ".join(self._tool_names) if self._tool_names else "your available MCP tools"
        prompt = f"""You are making your INITIAL offer on {PROPERTY_ADDRESS} (listed at ${LISTING_PRICE:,}).

INSTRUCTIONS:
1. First, call your available MCP tools ({tool_list}) to get market data
2. Based on this data, formulate your opening offer (start ~12% below asking)
3. Return your response as JSON with: offer_price, message, reasoning, walk_away, conditions, closing_timeline_days

This is Round 1 of 5. Make a strong opening offer backed by market data.
Return ONLY JSON. No markdown fences. No prose outside JSON."""

        raw_response = await self._run_agent(prompt)
        print(f"   [Buyer ADK] Raw response length: {len(raw_response)} chars")

        parsed = _parse_strict_json_output(raw_response)

        if parsed.walk_away:
            envelope = BuyerEnvelope(
                session_id=self.session_id,
                round=self._round,
                message_type="WITHDRAW",
                message=f"We are withdrawing from this negotiation. {parsed.walk_away_reason or 'Offer exceeds budget.'}",
                conditions=parsed.conditions,
                closing_timeline_days=parsed.closing_timeline_days,
            )
        else:
            offer_price = parsed.offer_price or parsed.price
            if offer_price is None:
                raise ValueError("Structured output missing offer_price for non-withdrawal response.")
            envelope = BuyerEnvelope(
                session_id=self.session_id,
                round=self._round,
                message_type="OFFER",
                price=float(offer_price),
                message=parsed.message,
                conditions=parsed.conditions or [
                    "Contingent on home inspection",
                    "Financing contingency (30 days)",
                ],
                closing_timeline_days=parsed.closing_timeline_days or 45,
            )

        await self._append_state_delta(
            {
                "round": self._round,
                "status": "buyer_walked" if envelope.message_type == "WITHDRAW" else "negotiating",
                "last_message_type": envelope.message_type,
                "last_offer_price": envelope.price,
            }
        )

        if envelope.price is not None:
            print(f"   [Buyer ADK] Offer: ${envelope.price:,.0f}")
        else:
            print(f"   [Buyer ADK] Decision: {envelope.message_type}")
        return envelope.model_dump(mode="json")

    async def respond_to_counter_envelope(self, seller_message: dict) -> dict:
        """Respond to seller envelope and return buyer envelope JSON."""
        self._round = int(seller_message.get("round", 1))
        seller_price = seller_message.get("price") or 0
        print(f"\n[Buyer ADK] Round {self._round}: Responding to counter ${float(seller_price):,.0f}...")

        prompt = _format_seller_envelope_for_buyer(seller_message, self._round)

        raw_response = await self._run_agent(prompt)
        print(f"   [Buyer ADK] Raw response length: {len(raw_response)} chars")

        parsed = _parse_strict_json_output(raw_response)
        next_round = self._round + 1

        if parsed.walk_away:
            envelope = BuyerEnvelope(
                session_id=self.session_id,
                round=next_round,
                message_type="WITHDRAW",
                message=f"We are withdrawing from this negotiation. {parsed.walk_away_reason or 'Offer exceeds budget.'}",
                conditions=parsed.conditions,
                closing_timeline_days=parsed.closing_timeline_days,
                in_reply_to=seller_message.get("message_id"),
            )
        else:
            offer_price = parsed.offer_price or parsed.price
            if offer_price is None:
                raise ValueError("Structured output missing offer_price for non-withdrawal response.")
            envelope = BuyerEnvelope(
                session_id=self.session_id,
                round=next_round,
                message_type="OFFER",
                price=float(offer_price),
                message=parsed.message,
                conditions=parsed.conditions or [
                    "Contingent on home inspection",
                    "Financing contingency (30 days)",
                ],
                closing_timeline_days=parsed.closing_timeline_days or 45,
                in_reply_to=seller_message.get("message_id"),
            )

        await self._append_state_delta(
            {
                "round": next_round,
                "status": "buyer_walked" if envelope.message_type == "WITHDRAW" else "negotiating",
                "last_message_type": envelope.message_type,
                "last_offer_price": envelope.price,
            }
        )

        if envelope.price is not None:
            print(f"   [Buyer ADK] Next offer: ${envelope.price:,.0f}")
        else:
            print(f"   [Buyer ADK] Decision: {envelope.message_type}")

        return envelope.model_dump(mode="json")

