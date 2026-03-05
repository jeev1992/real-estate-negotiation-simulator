"""
Tests for the Negotiation FSM (Module 1).

These tests verify the termination guarantee that is the whole point of
m1_baseline/state_machine.py. No API keys required.

Run: pytest tests/test_fsm.py -v
"""
import pytest
from m1_baseline.state_machine import (
    NegotiationFSM,
    NegotiationState,
    FailureReason,
)


# ─── Basic lifecycle ──────────────────────────────────────────────────────────

class TestFSMLifecycle:
    def test_initial_state_is_idle(self):
        fsm = NegotiationFSM()
        assert fsm.get_state() == NegotiationState.IDLE
        assert not fsm.is_terminal()
        assert not fsm.is_active

    def test_start_transitions_to_negotiating(self):
        fsm = NegotiationFSM()
        result = fsm.start()
        assert result is True
        assert fsm.get_state() == NegotiationState.NEGOTIATING
        assert fsm.is_active

    def test_start_returns_false_if_already_started(self):
        fsm = NegotiationFSM()
        fsm.start()
        result = fsm.start()
        assert result is False
        assert fsm.get_state() == NegotiationState.NEGOTIATING

    def test_accept_transitions_to_agreed(self):
        fsm = NegotiationFSM()
        fsm.start()
        result = fsm.accept(price=449_000.0)
        assert result is True
        assert fsm.get_state() == NegotiationState.AGREED
        assert fsm.is_terminal()
        assert fsm.context.agreed_price == 449_000.0

    def test_reject_transitions_to_failed_buyer(self):
        fsm = NegotiationFSM()
        fsm.start()
        fsm.reject(by_buyer=True)
        assert fsm.get_state() == NegotiationState.FAILED
        assert fsm.context.failure_reason == FailureReason.REJECTED_BY_BUYER

    def test_reject_transitions_to_failed_seller(self):
        fsm = NegotiationFSM()
        fsm.start()
        fsm.reject(by_buyer=False)
        assert fsm.context.failure_reason == FailureReason.REJECTED_BY_SELLER


# ─── Termination guarantee ────────────────────────────────────────────────────

class TestTerminationGuarantee:
    """
    These tests verify the core mathematical guarantee:
    The FSM MUST reach a terminal state in finite steps.
    """

    def test_max_turns_triggers_failed(self):
        """process_turn() at max_turns must auto-transition to FAILED."""
        fsm = NegotiationFSM(max_turns=3)
        fsm.start()

        assert fsm.process_turn() is True   # turn 1
        assert fsm.process_turn() is True   # turn 2
        assert fsm.process_turn() is False  # turn 3 = max -> FAILED

        assert fsm.get_state() == NegotiationState.FAILED
        assert fsm.context.failure_reason == FailureReason.MAX_TURNS_EXCEEDED

    def test_terminal_state_blocks_further_transitions(self):
        """Once AGREED, no further transitions are possible."""
        fsm = NegotiationFSM()
        fsm.start()
        fsm.accept(price=450_000.0)

        # All transition methods must return False from terminal state
        assert fsm.accept(price=440_000.0) is False
        assert fsm.reject() is False
        assert fsm.process_turn() is False

        # State must not have changed
        assert fsm.get_state() == NegotiationState.AGREED
        assert fsm.context.agreed_price == 450_000.0

    def test_failed_state_blocks_further_transitions(self):
        """Once FAILED, no further transitions are possible."""
        fsm = NegotiationFSM()
        fsm.start()
        fsm.reject()

        assert fsm.accept(price=440_000.0) is False
        assert fsm.get_state() == NegotiationState.FAILED

    def test_empty_transition_sets_for_terminal_states(self):
        """Terminal states must have empty transition sets (core FSM property)."""
        assert len(NegotiationFSM.TRANSITIONS[NegotiationState.AGREED]) == 0
        assert len(NegotiationFSM.TRANSITIONS[NegotiationState.FAILED]) == 0

    def test_process_turn_beyond_max_does_nothing(self):
        """Calling process_turn() after FSM is terminal must be a no-op."""
        fsm = NegotiationFSM(max_turns=2)
        fsm.start()
        fsm.process_turn()
        fsm.process_turn()  # triggers FAILED

        turn_count_before = fsm.context.turn_count
        fsm.process_turn()  # should be ignored
        assert fsm.context.turn_count == turn_count_before


# ─── Invariant checking ───────────────────────────────────────────────────────

class TestInvariants:
    def test_invariants_pass_after_agreement(self):
        fsm = NegotiationFSM(max_turns=5)
        fsm.start()
        fsm.process_turn()
        fsm.accept(price=451_000.0)
        assert fsm.check_invariants() is True

    def test_invariants_pass_after_rejection(self):
        fsm = NegotiationFSM(max_turns=5)
        fsm.start()
        fsm.reject()
        assert fsm.check_invariants() is True

    def test_invariants_pass_after_max_turns(self):
        fsm = NegotiationFSM(max_turns=3)
        fsm.start()
        for _ in range(3):
            fsm.process_turn()
        assert fsm.check_invariants() is True

    def test_agreed_requires_price(self):
        """AGREED state without a price should fail invariant check."""
        fsm = NegotiationFSM()
        fsm.start()
        fsm.accept(price=450_000.0)
        # Manually corrupt state to verify invariant catches it
        fsm.context.agreed_price = None
        with pytest.raises(AssertionError, match="agreed_price"):
            fsm.check_invariants()


# ─── Repr ─────────────────────────────────────────────────────────────────────

class TestRepr:
    def test_repr_includes_state_and_turn(self):
        fsm = NegotiationFSM(max_turns=5)
        fsm.start()
        fsm.process_turn()
        r = repr(fsm)
        assert "NEGOTIATING" in r
        assert "1/5" in r
