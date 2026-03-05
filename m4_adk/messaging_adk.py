"""
ADK Messaging Utilities
========================
Communication helpers for the Google ADK version of the negotiation simulator.

A2A IN ADK:
  In the simple Python version, agents exchange A2AMessage objects directly
  via the A2AMessageBus (in-memory queue).

  In the ADK version, agents are stateful LlmAgents with their own session.
  "Communication" works differently:
  - Each agent runs in its own Runner with its own session
  - The orchestrator (main_adk.py) mediates by passing the output of
    one agent as the input to the other
  - We still use the same A2AMessage schema for structure

THIS FILE PROVIDES:
  • parse_agent_response()   — extract structured data from Gemini output
  • format_for_agent()       — format A2AMessage into a prompt for the other agent
  • NegotiationSession       — tracks ADK-version negotiation state
  • print_round_summary()    — display results
"""

import json
import re
from typing import Optional

from m3_agents.a2a_simple import (
    A2AMessage,
    NegotiationStatus,
    create_offer,
    create_counter_offer,
    create_acceptance,
    create_withdrawal,
)


# ─── ADK Response Parsing ─────────────────────────────────────────────────────

def parse_buyer_response(
    raw_response: str,
    session_id: str,
    round_num: int,
    in_reply_to: Optional[str] = None
) -> A2AMessage:
    """
    Parse Gemini's raw text response into a structured A2AMessage (buyer).

    ADK TEACHING POINT:
    Unlike in the simple version where we use response_format=json_object,
    Gemini in ADK returns free-form text. We need to parse the JSON
    embedded in its response.

    PATTERN:
    We ask Gemini to include JSON in its response (in the instruction prompt).
    This function extracts it using regex or JSON detection.

    Args:
        raw_response: The text string returned by the ADK runner
        session_id: Current negotiation session ID
        round_num: Current round number
        in_reply_to: message_id of the message being replied to

    Returns:
        Parsed A2AMessage or a withdrawal if parsing fails
    """
    # Try to extract JSON from the response
    parsed = _extract_json(raw_response)

    if not parsed:
        # Fallback: if we can't parse JSON, create a safe withdrawal
        print(f"   [ADK Messaging] Warning: Could not parse buyer JSON response")
        print(f"   [ADK Messaging] Raw: {raw_response[:200]}")
        return create_withdrawal(
            session_id=session_id,
            round_num=round_num,
            reason="Agent response parsing failed. Withdrawing as safety measure.",
            in_reply_to=in_reply_to
        )

    # Check for walk-away
    if parsed.get("walk_away", False):
        return create_withdrawal(
            session_id=session_id,
            round_num=round_num,
            reason=parsed.get("walk_away_reason", "Offer exceeds budget."),
            in_reply_to=in_reply_to
        )

    # Extract offer price
    offer_price = _safe_float(parsed.get("offer_price") or parsed.get("price"))
    if not offer_price:
        return create_withdrawal(
            session_id=session_id,
            round_num=round_num,
            reason="Could not determine offer price from agent response.",
            in_reply_to=in_reply_to
        )

    # Build the A2A offer message
    return create_offer(
        session_id=session_id,
        round_num=round_num,
        price=offer_price,
        message=parsed.get("message", raw_response[:500]),
        conditions=parsed.get("conditions", [
            "Contingent on home inspection",
            "Financing contingency (30 days)"
        ]),
        closing_days=parsed.get("closing_timeline_days", 45),
        in_reply_to=in_reply_to
    )


def parse_seller_response(
    raw_response: str,
    session_id: str,
    round_num: int,
    buyer_offer_price: float,
    minimum_price: float,
    in_reply_to: Optional[str] = None
) -> A2AMessage:
    """
    Parse Gemini's raw text response into a structured A2AMessage (seller).

    Args:
        raw_response: The text string returned by the ADK runner
        session_id: Current negotiation session ID
        round_num: Current round number
        buyer_offer_price: The price the buyer offered (used for acceptance check)
        minimum_price: Seller's floor price (enforce it regardless of LLM output)
        in_reply_to: message_id being replied to

    Returns:
        Parsed A2AMessage
    """
    parsed = _extract_json(raw_response)

    if not parsed:
        print(f"   [ADK Messaging] Warning: Could not parse seller JSON response")
        # Return a high counter-offer as fallback
        return create_counter_offer(
            session_id=session_id,
            round_num=round_num,
            price=475_000.0,
            message="We cannot accept this offer. We counter at $475,000.",
            in_reply_to=in_reply_to
        )

    # Check for acceptance
    if parsed.get("accept", False):
        agreed_price = _safe_float(parsed.get("agreed_price")) or buyer_offer_price
        return create_acceptance(
            session_id=session_id,
            round_num=round_num,
            from_agent="seller",
            agreed_price=agreed_price,
            message=parsed.get("message", f"We accept your offer of ${agreed_price:,.0f}!"),
            in_reply_to=in_reply_to
        )

    # Extract counter price
    counter_price = _safe_float(
        parsed.get("counter_price") or parsed.get("price") or parsed.get("counter_offer")
    )

    if not counter_price:
        counter_price = 477_000.0  # fallback to initial counter

    # ENFORCE FLOOR: never allow LLM to go below minimum
    if counter_price < minimum_price:
        print(f"   [ADK Messaging] Enforcing floor: ${counter_price:,.0f} → ${minimum_price:,.0f}")
        counter_price = minimum_price

    return create_counter_offer(
        session_id=session_id,
        round_num=round_num,
        price=counter_price,
        message=parsed.get("message", f"We counter at ${counter_price:,.0f}."),
        conditions=parsed.get("conditions", ["As-is condition"]),
        closing_days=parsed.get("closing_timeline_days", 30),
        in_reply_to=in_reply_to
    )


# ─── Prompt Formatting ────────────────────────────────────────────────────────

def format_seller_message_for_buyer(seller_message: A2AMessage, round_num: int) -> str:
    """
    Format a seller's A2A message into a prompt string for the buyer agent.

    ADK TEACHING POINT:
    In ADK, we don't have a shared message bus. Instead, the orchestrator
    takes the seller's output and constructs a new input for the buyer.
    This is the "messaging layer" in the ADK multi-agent pattern.
    """
    price_str = f"${seller_message.payload.price:,.0f}" if seller_message.payload.price else "N/A"

    return f"""SELLER'S RESPONSE (Round {round_num}):

Message type: {seller_message.message_type}
Counter-offer price: {price_str}
Conditions: {', '.join(seller_message.payload.conditions) if seller_message.payload.conditions else 'Standard terms'}
Closing timeline: {seller_message.payload.closing_timeline_days} days
Seller's message: "{seller_message.payload.message}"

This is round {round_num} of 5 maximum rounds.

Please respond with your next offer or decision.
Remember to call get_market_price and calculate_discount before making your offer.
Respond with a JSON object containing: offer_price, message, reasoning, walk_away, walk_away_reason."""


def format_buyer_message_for_seller(buyer_message: A2AMessage, round_num: int) -> str:
    """
    Format a buyer's A2A message into a prompt string for the seller agent.
    """
    price_str = f"${buyer_message.payload.price:,.0f}" if buyer_message.payload.price else "N/A"

    return f"""BUYER'S OFFER (Round {round_num}):

Message type: {buyer_message.message_type}
Offer price: {price_str}
Conditions: {', '.join(buyer_message.payload.conditions) if buyer_message.payload.conditions else 'Standard terms'}
Closing timeline: {buyer_message.payload.closing_timeline_days} days
Buyer's justification: "{buyer_message.payload.message}"

This is round {round_num} of 5 maximum rounds.

Please evaluate this offer and respond.
Remember to call get_market_price, get_inventory_level, and get_minimum_acceptable_price.
Respond with a JSON object: counter_price, message, reasoning, accept, reject."""


# ─── Session State Tracker ────────────────────────────────────────────────────

class NegotiationSession:
    """
    Tracks the state of an ADK negotiation session.

    ADK TEACHING POINT:
    Unlike LangGraph which has built-in shared state, the ADK version
    doesn't automatically share state between agents. We track negotiation
    state here in the orchestrator and pass relevant information to each
    agent via their prompt.

    This is a common pattern when building multi-agent systems with ADK:
    the orchestrating code maintains a "meta-state" that coordinates
    independently-running agents.
    """

    def __init__(
        self,
        session_id: str,
        property_address: str,
        listing_price: float,
        buyer_budget: float,
        seller_minimum: float,
        max_rounds: int = 5
    ):
        self.session_id = session_id
        self.property_address = property_address
        self.listing_price = listing_price
        self.buyer_budget = buyer_budget
        self.seller_minimum = seller_minimum
        self.max_rounds = max_rounds

        self.current_round = 0
        self.buyer_current_offer: Optional[float] = None
        self.seller_current_counter: Optional[float] = None
        self.status: NegotiationStatus = "negotiating"
        self.agreed_price: Optional[float] = None
        self.message_history: list[A2AMessage] = []

    def record_message(self, message: A2AMessage) -> None:
        """Record a message and update session state."""
        self.message_history.append(message)

        if message.from_agent == "buyer":
            self.current_round = message.round
            if message.payload.price:
                self.buyer_current_offer = message.payload.price
            if message.message_type == "WITHDRAW":
                self.status = "buyer_walked"
            elif message.message_type == "ACCEPT":
                self.status = "agreed"
                self.agreed_price = message.payload.price

        elif message.from_agent == "seller":
            if message.payload.price:
                self.seller_current_counter = message.payload.price
            if message.message_type == "ACCEPT":
                self.status = "agreed"
                self.agreed_price = self.buyer_current_offer
            elif message.message_type == "REJECT":
                self.status = "seller_rejected"

        # Check for deadlock
        if self.current_round >= self.max_rounds and self.status == "negotiating":
            self.status = "deadlocked"

    def is_concluded(self) -> bool:
        """Returns True if the negotiation has ended."""
        return self.status != "negotiating"

    def get_round_summary(self) -> str:
        """Returns a summary of the current negotiation state."""
        buyer_str = f"${self.buyer_current_offer:,.0f}" if self.buyer_current_offer else "N/A"
        seller_str = f"${self.seller_current_counter:,.0f}" if self.seller_current_counter else "N/A"
        gap = (
            f"${self.seller_current_counter - self.buyer_current_offer:,.0f}"
            if self.buyer_current_offer and self.seller_current_counter
            else "N/A"
        )

        return (
            f"Round {self.current_round}/{self.max_rounds} | "
            f"Buyer: {buyer_str} | Seller: {seller_str} | Gap: {gap} | "
            f"Status: {self.status}"
        )


# ─── Display Utilities ────────────────────────────────────────────────────────

def print_round_summary(session: NegotiationSession, message: A2AMessage) -> None:
    """Print a formatted summary of a negotiation round."""
    price_str = f"${message.payload.price:,.0f}" if message.payload.price else "N/A"
    agent_label = message.from_agent.upper()

    print(f"\n  {'─' * 55}")
    print(f"  [{agent_label}] {message.message_type} @ {price_str}")
    print(f"  {session.get_round_summary()}")
    print(f"  Message: {message.payload.message[:100]}...")


def print_final_result(session: NegotiationSession) -> None:
    """Print the final negotiation outcome."""
    print("\n" + "═" * 60)
    print("NEGOTIATION COMPLETE (ADK Version)")
    print("═" * 60)
    print(f"Status: {session.status.upper()}")

    if session.agreed_price:
        savings = session.listing_price - session.agreed_price
        savings_pct = savings / session.listing_price * 100
        print(f"Agreed Price: ${session.agreed_price:,.0f}")
        print(f"Listed Price: ${session.listing_price:,.0f}")
        print(f"Buyer Saved: ${savings:,.0f} ({savings_pct:.1f}% below listing)")

    print(f"Rounds Used: {session.current_round} of {session.max_rounds}")
    print(f"Messages Exchanged: {len(session.message_history)}")
    print("═" * 60)


# ─── Private Helpers ──────────────────────────────────────────────────────────

def _extract_json(text: str) -> Optional[dict]:
    """
    Extract JSON from a Gemini response string.

    Gemini may wrap JSON in markdown code blocks or include it inline.
    This function tries multiple extraction strategies.
    """
    if not text:
        return None

    # Strategy 1: Direct JSON parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code block ```json ... ```
    code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find first { ... } block in the text
    brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    # Strategy 4: Extract price and boolean values using JSON-context patterns
    # Looks for "key": value patterns rather than free-text to avoid false matches
    price_match = re.search(r'"(?:offer_price|counter_price|price)"\s*:\s*(\d+)', text)
    if price_match:
        price = int(price_match.group(1))
        # Use precise key:value regex to avoid "true" appearing in unrelated text
        walk_away_match = re.search(r'"walk_away"\s*:\s*(true|false)', text, re.IGNORECASE)
        accept_match = re.search(r'"accept"\s*:\s*(true|false)', text, re.IGNORECASE)
        return {
            "offer_price": price,
            "counter_price": price,
            "message": text[:200],
            "walk_away": walk_away_match.group(1).lower() == "true" if walk_away_match else False,
            "accept": accept_match.group(1).lower() == "true" if accept_match else False,
        }

    return None


def _safe_float(value) -> Optional[float]:
    """Safely convert a value to float."""
    if value is None:
        return None
    try:
        # Handle string numbers with commas (e.g., "425,000")
        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").strip()
        return float(value)
    except (ValueError, TypeError):
        return None
