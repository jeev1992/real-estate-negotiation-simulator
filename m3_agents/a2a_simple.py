"""
A2A Simple — Agent-to-Agent Messaging Protocol
================================================
Defines the message schema and message bus for agent-to-agent communication
in the simple Python version of the negotiation simulator.

A2A CONCEPT:
  Agents communicate via structured JSON messages — not raw text.
  This ensures:
  1. Clear intent (OFFER vs COUNTER_OFFER vs ACCEPT)
  2. Structured data (price is always a number, not buried in text)
  3. Trackable history (each message has ID, round, timestamp)
  4. Validatable schema (Pydantic catches malformed messages)

COMPARISON TO MCP:
  MCP  = Agent ↔ External Tool/Data
  A2A  = Agent ↔ Agent

  They complement each other:
  - Agent uses MCP to get market data
  - Agent uses A2A to send offer to other agent

WHAT'S IN THIS FILE:
  • A2AMessage — the message schema (Pydantic model)
  • NegotiationPayload — the message content
  • A2AMessageBus — in-process routing of messages between agents
  • Helper functions for creating common message types
"""

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─── Types ────────────────────────────────────────────────────────────────────

AgentName = Literal["buyer", "seller"]

MessageType = Literal[
    "OFFER",           # Buyer submits an offer
    "COUNTER_OFFER",   # Seller responds with counter
    "ACCEPT",          # Either party accepts the current price
    "REJECT",          # Either party rejects and ends negotiation
    "WITHDRAW",        # Buyer withdraws their offer (walk-away)
    "INFO",            # Informational message (e.g., error, status)
]

NegotiationStatus = Literal[
    "negotiating",    # Active
    "agreed",         # Deal reached
    "deadlocked",     # Max rounds exceeded, no deal
    "buyer_walked",   # Buyer withdrew
    "seller_rejected",# Seller rejected outright
    "error",          # System error
]


# ─── Message Schema ───────────────────────────────────────────────────────────

class NegotiationPayload(BaseModel):
    """
    The actual content of a negotiation message.

    DESIGN CHOICE: We separate payload (what) from metadata (who/when/how).
    This makes it easy to log, audit, and debug messages.
    """

    price: Optional[float] = Field(
        default=None,
        description="Offer or counter-offer price in USD"
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="List of offer conditions (e.g., 'Contingent on inspection')"
    )
    closing_timeline_days: Optional[int] = Field(
        default=None,
        description="Proposed closing timeline in days from acceptance"
    )
    concessions: list[str] = Field(
        default_factory=list,
        description="Seller concessions being requested or offered"
    )
    message: str = Field(
        description=(
            "Human-readable explanation. This is what the other agent's LLM reads. "
            "Should include justification, market data references, and strategy."
        )
    )


class A2AMessage(BaseModel):
    """
    A complete A2A message between negotiation agents.

    EDUCATIONAL NOTE:
    This schema demonstrates proper A2A message design:
    1. Identity: who sent it, who should receive it
    2. Temporal: when was it sent, which round, what's it replying to
    3. Intent: what type of message is this
    4. Content: the actual negotiation payload
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    message_id: str = Field(
        default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}",
        description="Unique message identifier for deduplication and reference"
    )
    session_id: str = Field(
        description="Identifies which negotiation session this belongs to"
    )
    from_agent: AgentName = Field(description="Agent that sent this message")
    to_agent: AgentName = Field(description="Agent that should receive this message")

    # ── Temporal context ──────────────────────────────────────────────────────
    round: int = Field(description="Negotiation round number (1-indexed)")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of when message was created"
    )
    in_reply_to: Optional[str] = Field(
        default=None,
        description="message_id of the message this is responding to"
    )

    # ── Intent ────────────────────────────────────────────────────────────────
    message_type: MessageType = Field(
        description="The type of negotiation message"
    )

    # ── Content ───────────────────────────────────────────────────────────────
    payload: NegotiationPayload = Field(
        description="The actual negotiation content"
    )

    def is_terminal(self) -> bool:
        """Returns True if this message ends the negotiation."""
        return self.message_type in ("ACCEPT", "REJECT", "WITHDRAW")

    def to_summary(self) -> str:
        """Returns a human-readable one-line summary."""
        price_str = f"${self.payload.price:,.0f}" if self.payload.price else "N/A"
        return (
            f"[Round {self.round}] {self.from_agent.upper()} → {self.to_agent.upper()} | "
            f"{self.message_type} @ {price_str}"
        )


# ─── State Machine Validation ─────────────────────────────────────────────────

# Defines which message types are valid responses to each message type
VALID_RESPONSES: dict[MessageType, list[MessageType]] = {
    "OFFER":         ["COUNTER_OFFER", "ACCEPT", "REJECT"],
    "COUNTER_OFFER": ["OFFER", "ACCEPT", "REJECT", "WITHDRAW"],
    "ACCEPT":        [],   # terminal — no valid responses
    "REJECT":        [],   # terminal — no valid responses
    "WITHDRAW":      [],   # terminal — no valid responses
    "INFO":          ["OFFER", "COUNTER_OFFER", "INFO"],
}


def validate_message_transition(
    last_type: Optional[MessageType],
    new_type: MessageType,
    current_round: int,
    max_rounds: int
) -> tuple[bool, str]:
    """
    Validate that a new message type is valid given the last message type.

    Returns:
        (is_valid, reason_if_invalid)
    """
    # Terminal messages are always valid (to end deadlock)
    if new_type in ("ACCEPT", "REJECT", "WITHDRAW"):
        return True, "OK"

    # First message must be an OFFER or INFO
    if last_type is None:
        if new_type in ("OFFER", "INFO"):
            return True, "OK"
        return False, f"First message must be OFFER or INFO, not {new_type}"

    # Check round limit
    if current_round >= max_rounds and new_type not in ("ACCEPT", "REJECT", "WITHDRAW"):
        return False, f"Max rounds ({max_rounds}) reached. Only terminal messages allowed."

    # Check valid transition
    valid_next = VALID_RESPONSES.get(last_type, [])
    if new_type not in valid_next:
        return False, (
            f"Cannot send {new_type} after {last_type}. "
            f"Valid responses: {valid_next}"
        )

    return True, "OK"


# ─── Message Bus ──────────────────────────────────────────────────────────────

class A2AMessageBus:
    """
    In-process message bus for agent-to-agent communication.

    In this simple version, both agents run in the same Python process
    so we use a simple in-memory queue.

    In production, this would be replaced by:
    - HTTP endpoints (each agent has a REST API)
    - Message queue (Kafka, RabbitMQ, Redis Pub/Sub)
    - gRPC streams

    CONCEPT: The message bus is the "infrastructure" layer of A2A.
    It routes messages, validates them, and maintains history.
    The agents themselves don't know HOW messages are delivered —
    they just call send() and receive().
    """

    def __init__(self, session_id: str, max_rounds: int = 5):
        self.session_id = session_id
        self.max_rounds = max_rounds

        # Per-agent message queues
        self._queues: dict[str, list[A2AMessage]] = {
            "buyer": [],
            "seller": []
        }

        # Full conversation history
        self.history: list[A2AMessage] = []

        # State machine tracking
        self._last_message_type: Optional[MessageType] = None
        self._current_round: int = 0
        self._is_terminal: bool = False

    def send(self, message: A2AMessage) -> None:
        """
        Send a message from one agent to another.

        Validates the message against the state machine before accepting it.
        Raises ValueError if the message is not valid at this point.
        """
        if self._is_terminal:
            raise ValueError("Cannot send message: negotiation has already concluded")

        # Validate state machine transition
        is_valid, reason = validate_message_transition(
            last_type=self._last_message_type,
            new_type=message.message_type,
            current_round=self._current_round,
            max_rounds=self.max_rounds
        )

        if not is_valid:
            raise ValueError(f"Invalid A2A message: {reason}")

        # Ensure session_id matches
        if message.session_id != self.session_id:
            raise ValueError(
                f"Message session_id '{message.session_id}' "
                f"doesn't match bus session_id '{self.session_id}'"
            )

        # Route to recipient's queue
        self._queues[message.to_agent].append(message)

        # Update history and state
        self.history.append(message)
        self._last_message_type = message.message_type

        # Track rounds (a round increments when buyer sends)
        if message.from_agent == "buyer" and message.message_type in ("OFFER", "WITHDRAW"):
            self._current_round += 1

        # Mark as terminal if needed
        if message.is_terminal():
            self._is_terminal = True

    def receive(self, agent_name: AgentName) -> Optional[A2AMessage]:
        """
        Receive the next message for an agent.

        Returns None if no messages are waiting.
        This is a non-blocking call.
        """
        queue = self._queues.get(agent_name, [])
        if queue:
            return queue.pop(0)
        return None

    def has_messages(self, agent_name: AgentName) -> bool:
        """Check if an agent has messages waiting."""
        return len(self._queues.get(agent_name, [])) > 0

    def is_concluded(self) -> bool:
        """Returns True if the negotiation has reached a terminal state."""
        return self._is_terminal

    def get_outcome(self) -> NegotiationStatus:
        """Returns the current negotiation outcome."""
        if not self._is_terminal:
            if self._current_round >= self.max_rounds:
                return "deadlocked"
            return "negotiating"

        last = self.history[-1] if self.history else None
        if not last:
            return "negotiating"

        if last.message_type == "ACCEPT":
            return "agreed"
        elif last.message_type == "REJECT":
            return "seller_rejected"
        elif last.message_type == "WITHDRAW":
            return "buyer_walked"

        return "negotiating"

    def get_agreed_price(self) -> Optional[float]:
        """Returns the agreed price if negotiation concluded with ACCEPT."""
        if self.get_outcome() == "agreed" and self.history:
            last = self.history[-1]
            return last.payload.price
        return None

    def print_history(self) -> None:
        """Print a formatted negotiation transcript."""
        print("\n" + "=" * 60)
        print(f"NEGOTIATION TRANSCRIPT — Session: {self.session_id}")
        print("=" * 60)

        for msg in self.history:
            print(f"\n{msg.to_summary()}")
            if msg.payload.price:
                print(f"  Price: ${msg.payload.price:,.0f}")
            if msg.payload.conditions:
                print(f"  Conditions: {', '.join(msg.payload.conditions)}")
            print(f"  Message: {msg.payload.message[:120]}...")

        outcome = self.get_outcome()
        agreed_price = self.get_agreed_price()

        print("\n" + "─" * 60)
        print(f"OUTCOME: {outcome.upper()}")
        if agreed_price:
            print(f"AGREED PRICE: ${agreed_price:,.0f}")
        print("=" * 60 + "\n")


# ─── Message Factory Functions ────────────────────────────────────────────────

def create_offer(
    session_id: str,
    round_num: int,
    price: float,
    message: str,
    conditions: Optional[list[str]] = None,
    closing_days: Optional[int] = None,
    in_reply_to: Optional[str] = None
) -> A2AMessage:
    """Create a buyer OFFER message."""
    return A2AMessage(
        session_id=session_id,
        from_agent="buyer",
        to_agent="seller",
        round=round_num,
        in_reply_to=in_reply_to,
        message_type="OFFER",
        payload=NegotiationPayload(
            price=price,
            conditions=conditions or ["Contingent on home inspection", "Financing contingency (30 days)"],
            closing_timeline_days=closing_days or 45,
            message=message
        )
    )


def create_counter_offer(
    session_id: str,
    round_num: int,
    price: float,
    message: str,
    conditions: Optional[list[str]] = None,
    closing_days: Optional[int] = None,
    in_reply_to: Optional[str] = None
) -> A2AMessage:
    """Create a seller COUNTER_OFFER message."""
    return A2AMessage(
        session_id=session_id,
        from_agent="seller",
        to_agent="buyer",
        round=round_num,
        in_reply_to=in_reply_to,
        message_type="COUNTER_OFFER",
        payload=NegotiationPayload(
            price=price,
            conditions=conditions or ["As-is condition", "Standard contingencies"],
            closing_timeline_days=closing_days or 30,
            message=message
        )
    )


def create_acceptance(
    session_id: str,
    round_num: int,
    from_agent: AgentName,
    agreed_price: float,
    message: str,
    in_reply_to: Optional[str] = None
) -> A2AMessage:
    """Create an ACCEPT message."""
    to_agent: AgentName = "seller" if from_agent == "buyer" else "buyer"
    return A2AMessage(
        session_id=session_id,
        from_agent=from_agent,
        to_agent=to_agent,
        round=round_num,
        in_reply_to=in_reply_to,
        message_type="ACCEPT",
        payload=NegotiationPayload(
            price=agreed_price,
            message=message
        )
    )


def create_withdrawal(
    session_id: str,
    round_num: int,
    reason: str,
    in_reply_to: Optional[str] = None
) -> A2AMessage:
    """Create a buyer WITHDRAW message (walk-away)."""
    return A2AMessage(
        session_id=session_id,
        from_agent="buyer",
        to_agent="seller",
        round=round_num,
        in_reply_to=in_reply_to,
        message_type="WITHDRAW",
        payload=NegotiationPayload(
            message=f"We are withdrawing from this negotiation. {reason}"
        )
    )
