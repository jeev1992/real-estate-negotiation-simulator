"""
Tests for A2A message schema and bus validation (Module 3).

Verifies that the A2A state machine correctly enforces message-type
sequences and rejects invalid transitions. No API keys required.

Run: pytest tests/test_a2a.py -v
"""
import pytest
from m3_agents.a2a_simple import (
    A2AMessage,
    A2AMessageBus,
    NegotiationPayload,
    create_offer,
    create_counter_offer,
    create_acceptance,
    create_withdrawal,
    validate_message_transition,
)

SESSION = "test_session_001"


# ─── Message creation helpers ─────────────────────────────────────────────────

def make_offer(round_num: int = 1, price: float = 425_000.0, reply_to=None) -> A2AMessage:
    return create_offer(
        session_id=SESSION,
        round_num=round_num,
        price=price,
        message="Test offer",
        in_reply_to=reply_to,
    )


def make_counter(round_num: int = 1, price: float = 477_000.0, reply_to=None) -> A2AMessage:
    return create_counter_offer(
        session_id=SESSION,
        round_num=round_num,
        price=price,
        message="Test counter",
        in_reply_to=reply_to,
    )


def make_acceptance(round_num: int = 1, price: float = 451_000.0, from_agent="seller") -> A2AMessage:
    return create_acceptance(
        session_id=SESSION,
        round_num=round_num,
        from_agent=from_agent,
        agreed_price=price,
        message="We have a deal.",
    )


# ─── Message schema ───────────────────────────────────────────────────────────

class TestMessageSchema:
    def test_offer_message_fields(self):
        msg = make_offer(price=425_000.0)
        assert msg.from_agent == "buyer"
        assert msg.to_agent == "seller"
        assert msg.message_type == "OFFER"
        assert msg.payload.price == 425_000.0
        assert msg.session_id == SESSION

    def test_counter_offer_fields(self):
        msg = make_counter(price=477_000.0)
        assert msg.from_agent == "seller"
        assert msg.to_agent == "buyer"
        assert msg.message_type == "COUNTER_OFFER"

    def test_message_id_is_unique(self):
        msg1 = make_offer()
        msg2 = make_offer()
        assert msg1.message_id != msg2.message_id

    def test_is_terminal_for_accept(self):
        msg = make_acceptance()
        assert msg.is_terminal() is True

    def test_is_terminal_for_offer(self):
        msg = make_offer()
        assert msg.is_terminal() is False

    def test_withdrawal_is_terminal(self):
        msg = create_withdrawal(session_id=SESSION, round_num=1, reason="Too expensive.")
        assert msg.is_terminal() is True

    def test_to_summary_format(self):
        msg = make_offer(round_num=2, price=435_000.0)
        summary = msg.to_summary()
        assert "Round 2" in summary
        assert "BUYER" in summary
        assert "435,000" in summary


# ─── Transition validation ────────────────────────────────────────────────────

class TestTransitionValidation:
    def test_first_message_must_be_offer(self):
        valid, _ = validate_message_transition(None, "OFFER", 0, 5)
        assert valid is True

    def test_counter_offer_not_valid_as_first_message(self):
        valid, reason = validate_message_transition(None, "COUNTER_OFFER", 0, 5)
        assert valid is False
        assert "First message" in reason

    def test_counter_valid_after_offer(self):
        valid, _ = validate_message_transition("OFFER", "COUNTER_OFFER", 1, 5)
        assert valid is True

    def test_offer_valid_after_counter(self):
        valid, _ = validate_message_transition("COUNTER_OFFER", "OFFER", 1, 5)
        assert valid is True

    def test_accept_always_valid(self):
        for last_type in ("OFFER", "COUNTER_OFFER", None):
            valid, _ = validate_message_transition(last_type, "ACCEPT", 1, 5)
            assert valid is True

    def test_max_rounds_blocks_non_terminal(self):
        valid, reason = validate_message_transition("COUNTER_OFFER", "OFFER", 5, 5)
        assert valid is False
        assert "Max rounds" in reason

    def test_max_rounds_allows_terminal(self):
        valid, _ = validate_message_transition("OFFER", "ACCEPT", 5, 5)
        assert valid is True


# ─── Message bus ─────────────────────────────────────────────────────────────

class TestA2AMessageBus:
    def test_basic_send_and_receive(self):
        bus = A2AMessageBus(session_id=SESSION, max_rounds=5)
        offer = make_offer()
        bus.send(offer)

        received = bus.receive("seller")
        assert received is not None
        assert received.message_id == offer.message_id

    def test_no_message_returns_none(self):
        bus = A2AMessageBus(session_id=SESSION, max_rounds=5)
        assert bus.receive("buyer") is None

    def test_bus_rejects_invalid_first_message(self):
        bus = A2AMessageBus(session_id=SESSION, max_rounds=5)
        counter = make_counter()
        with pytest.raises(ValueError, match="First message"):
            bus.send(counter)

    def test_bus_rejects_wrong_session_id(self):
        bus = A2AMessageBus(session_id=SESSION, max_rounds=5)
        msg = make_offer()
        msg = msg.model_copy(update={"session_id": "wrong_session"})
        with pytest.raises(ValueError, match="session_id"):
            bus.send(msg)

    def test_bus_terminates_on_accept(self):
        bus = A2AMessageBus(session_id=SESSION, max_rounds=5)
        bus.send(make_offer(round_num=1))
        bus.send(make_acceptance(round_num=1))
        assert bus.is_concluded() is True

    def test_bus_blocks_after_terminal(self):
        bus = A2AMessageBus(session_id=SESSION, max_rounds=5)
        bus.send(make_offer(round_num=1))
        bus.send(make_acceptance(round_num=1))
        with pytest.raises(ValueError, match="already concluded"):
            bus.send(make_offer(round_num=2))

    def test_get_outcome_agreed(self):
        bus = A2AMessageBus(session_id=SESSION, max_rounds=5)
        bus.send(make_offer(round_num=1, price=451_000.0))
        bus.send(make_acceptance(round_num=1, price=451_000.0))
        assert bus.get_outcome() == "agreed"
        assert bus.get_agreed_price() == 451_000.0

    def test_get_outcome_buyer_walked(self):
        bus = A2AMessageBus(session_id=SESSION, max_rounds=5)
        bus.send(make_offer(round_num=1))
        bus.send(make_counter(round_num=1, reply_to=make_offer().message_id))
        withdrawal = create_withdrawal(session_id=SESSION, round_num=2, reason="Too high.")
        bus.send(withdrawal)
        assert bus.get_outcome() == "buyer_walked"

    def test_history_records_all_messages(self):
        bus = A2AMessageBus(session_id=SESSION, max_rounds=5)
        o = make_offer(round_num=1)
        c = make_counter(round_num=1)
        bus.send(o)
        bus.send(c)
        assert len(bus.history) == 2
        assert bus.history[0].message_id == o.message_id
        assert bus.history[1].message_id == c.message_id
