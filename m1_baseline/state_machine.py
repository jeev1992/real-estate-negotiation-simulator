"""
Finite State Machine for Negotiation
======================================
Layer 7 of the 10-layer architecture -- solves the termination problem
that breaks naive_negotiation.py.

WHAT THIS SOLVES:
  naive_negotiation.py uses a while True loop with only an emergency
  exit at 100 turns. This FSM provides a MATHEMATICAL GUARANTEE of
  termination:

  1. States AGREED and FAILED have NO outgoing transitions (terminal)
  2. Turn count is bounded by max_turns
  3. Every transition either:
     a) Moves to a terminal state (no further transitions possible), OR
     b) Increments the turn count (bounded -- can't loop forever)
  Therefore, Termination is GUARANTEED.

HOW TO RUN (demo):
  python m1_m1_baseline/state_machine.py

HOW THIS CONNECTS TO THE REST OF THE WORKSHOP:
  ┌─────────────────────────────────────────────────────────────────┐
  │  naive_negotiation.py                                           │
  │    while True: ...  <-- no guarantee                             │
  │         ↓                                                       │
  │  state_machine.py (this file)                                   │
  │    NegotiationFSM   <-- termination guaranteed at code level      │
  │         ↓                                                       │
  │  m3_agents/langgraph_flow.py                                │
  │    StateGraph       <-- termination guaranteed at workflow level  │
  │    (LangGraph IS a state machine -- but for entire workflows)    │
  └─────────────────────────────────────────────────────────────────┘

  The progression shows WHY LangGraph exists: it provides the same
  FSM guarantees as NegotiationFSM, but for complex multi-step
  workflows with conditional routing and parallel agents.

CREDIT:
  Core FSM design adapted from jeev1992/Agent-Negotiation-System (04_fsm/),
  updated for the real estate workshop context (max_turns=5).
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# STATE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

class NegotiationState(Enum):
    """
    The finite set of states a negotiation can be in.

    KEY INSIGHT: There are exactly 4 states, and only 2 are terminal.
    This small, explicit set is what makes termination provable.
    Compare to naive_negotiation.py where state was implicit and unbounded.
    """
    IDLE        = auto()    # Not yet started -- waiting for first offer
    NEGOTIATING = auto()    # Active -- offers being exchanged
    AGREED      = auto()    # Terminal: deal reached ✓
    FAILED      = auto()    # Terminal: no deal ✗


class FailureReason(Enum):
    """
    Why a negotiation failed.

    Storing the reason enables:
    - Better user-facing messages
    - Analytics (which failure type is most common?)
    - Strategy adjustment in next session
    """
    MAX_TURNS_EXCEEDED  = auto()    # Ran out of rounds without agreement
    REJECTED_BY_BUYER   = auto()    # Buyer walked away
    REJECTED_BY_SELLER  = auto()    # Seller rejected outright
    POLICY_VIOLATION    = auto()    # Message violates negotiation rules
    INVALID_TRANSITION  = auto()    # Tried an impossible state transition


# ─────────────────────────────────────────────────────────────────────────────
# FSM CONTEXT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FSMContext:
    """
    Context tracked alongside the FSM state.

    This is similar to LangGraph's NegotiationState TypedDict -- it holds
    the data that persists across state transitions. The difference is that
    LangGraph's state is much richer (full message history, both agents'
    offers, etc.) while FSMContext just tracks what the FSM needs.
    """
    turn_count:     int                      = 0
    max_turns:      int                      = 5      # Match our workshop config (5 rounds)
    last_offer:     Optional[float]          = None   # Most recent price on the table
    agreed_price:   Optional[float]          = None   # Set when AGREED
    failure_reason: Optional[FailureReason]  = None   # Set when FAILED


# ─────────────────────────────────────────────────────────────────────────────
# THE FSM
# ─────────────────────────────────────────────────────────────────────────────

class NegotiationFSM:
    """
    Finite State Machine for negotiation lifecycle.

    TERMINATION GUARANTEE (informal proof):
    ─────────────────────────────────────────
    Define measure M = (is_terminal, turn_count).
    Ordering: terminal < non-terminal; lower turn_count < higher.

    Each call to process_turn():
      Case A: is_terminal becomes True  -> M strictly decreases (non-terminal -> terminal)
      Case B: turn_count increments     -> M strictly decreases (same category, lower count)

    Since M is bounded below (is_terminal=True is the minimum) and strictly
    decreasing, the FSM MUST reach a terminal state in finite steps. QED.

    CONTRAST WITH naive_negotiation.py:
      while True:
          if "DEAL" in message: break  <-- depends on string content; can be fooled
          if turn > 100: break         <-- emergency exit, not a guarantee

    WITH FSM:
      while not fsm.is_terminal():
          if not fsm.process_turn(): break  <-- guaranteed to terminate

    RELATIONSHIP TO LANGGRAPH:
      LangGraph provides the same guarantee at workflow level:
      - Terminal nodes (END) have no outgoing edges
      - Cycle detection prevents infinite loops
      - Max steps can be set in graph.compile()
    """

    # ── Transition table ───────────────────────────────────────────────────────
    # This is the heart of the FSM. Read it as:
    #   "From state X, you may transition to any state in the set Y"
    #
    # TERMINAL STATES (AGREED, FAILED) have EMPTY sets -- no outgoing transitions.
    # This is what guarantees they can never be exited once entered.
    TRANSITIONS: dict[NegotiationState, set[NegotiationState]] = {
        NegotiationState.IDLE:        {NegotiationState.NEGOTIATING, NegotiationState.FAILED},
        NegotiationState.NEGOTIATING: {NegotiationState.NEGOTIATING, NegotiationState.AGREED, NegotiationState.FAILED},
        NegotiationState.AGREED:      set(),    # <-- TERMINAL: no outgoing transitions
        NegotiationState.FAILED:      set(),    # <-- TERMINAL: no outgoing transitions
    }

    def __init__(self, max_turns: int = 5):
        self.state = NegotiationState.IDLE
        self.context = FSMContext(max_turns=max_turns)

    # ── Inspection ────────────────────────────────────────────────────────────

    def get_state(self) -> NegotiationState:
        """Return current state."""
        return self.state

    @property
    def is_active(self) -> bool:
        """True if negotiation is in progress (NEGOTIATING state)."""
        return self.state == NegotiationState.NEGOTIATING

    def is_terminal(self) -> bool:
        """
        True if in AGREED or FAILED -- no further transitions possible.
        Use this as the loop exit condition instead of checking strings.
        """
        return self.state in {NegotiationState.AGREED, NegotiationState.FAILED}

    def can_transition(self, to_state: NegotiationState) -> bool:
        """Check if a transition is valid without performing it."""
        return to_state in self.TRANSITIONS[self.state]

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """
        Begin the negotiation. Returns False if already started.
        IDLE -> NEGOTIATING
        """
        if self.state != NegotiationState.IDLE:
            return False
        self.state = NegotiationState.NEGOTIATING
        return True

    def process_turn(self) -> bool:
        """
        Record that a turn has occurred. Returns False if max turns exceeded.

        THIS IS THE KEY TO TERMINATION GUARANTEE:
        Every active turn increments turn_count.
        When turn_count >= max_turns, we transition to FAILED automatically.
        Since turn_count is an integer bounded by max_turns, it can never
        increment forever -- termination is guaranteed.

        Returns:
            True  -- turn recorded, negotiation continues
            False -- max turns exceeded, moved to FAILED
        """
        if not self.is_active:
            return False

        self.context.turn_count += 1

        if self.context.turn_count >= self.context.max_turns:
            # Auto-transition to FAILED -- no more turns allowed
            self.state = NegotiationState.FAILED
            self.context.failure_reason = FailureReason.MAX_TURNS_EXCEEDED
            return False

        return True

    def record_turn(self) -> None:
        """
        Alternative to process_turn() for use with external loop controllers
        (like LangGraph) that manage their own round counting.
        Does not enforce max_turns -- call process_turn() if you want that.
        """
        if self.is_active:
            self.context.turn_count += 1

    # ── Terminal transitions ───────────────────────────────────────────────────

    def accept(self, price: float) -> bool:
        """
        Both parties agree on a price.
        NEGOTIATING -> AGREED

        Returns False if not currently active.
        """
        if not self.is_active:
            return False
        self.state = NegotiationState.AGREED
        self.context.agreed_price = price
        return True

    def reject(self, by_buyer: bool = True) -> bool:
        """
        One party rejects -- ends negotiation without a deal.
        NEGOTIATING -> FAILED

        Returns False if not currently active.
        """
        if not self.is_active:
            return False
        self.state = NegotiationState.FAILED
        self.context.failure_reason = (
            FailureReason.REJECTED_BY_BUYER if by_buyer
            else FailureReason.REJECTED_BY_SELLER
        )
        return True

    def transition_to_failed(self, reason: FailureReason = FailureReason.POLICY_VIOLATION) -> bool:
        """Transition to FAILED for any reason (policy violation, error, etc.)."""
        if not self.is_active:
            return False
        self.state = NegotiationState.FAILED
        self.context.failure_reason = reason
        return True

    # ── Invariant checking ────────────────────────────────────────────────────

    def check_invariants(self) -> bool:
        """
        Assert that all FSM invariants hold.

        These should NEVER be violated. If they are, there's a bug in the
        FSM logic itself. Call this in tests and at key checkpoints.

        Raises AssertionError if any invariant is violated.
        """
        # Turn count must be non-negative
        assert self.context.turn_count >= 0, "Turn count cannot be negative"

        # Turn count cannot exceed max_turns (FSM should have stopped it)
        assert self.context.turn_count <= self.context.max_turns, (
            f"Turn count {self.context.turn_count} exceeds max {self.context.max_turns}"
        )

        # Terminal states must have required context data
        if self.state == NegotiationState.AGREED:
            assert self.context.agreed_price is not None, (
                "AGREED state requires agreed_price to be set"
            )

        if self.state == NegotiationState.FAILED:
            assert self.context.failure_reason is not None, (
                "FAILED state requires failure_reason to be set"
            )

        # Terminal states must have empty transition sets (the core guarantee)
        if self.is_terminal():
            assert len(self.TRANSITIONS[self.state]) == 0, (
                f"Terminal state {self.state} should have no outgoing transitions"
            )

        return True

    def __repr__(self) -> str:
        return (
            f"NegotiationFSM(state={self.state.name}, "
            f"turn={self.context.turn_count}/{self.context.max_turns})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# DEMO -- Run FSM through sample negotiation scenarios
# ─────────────────────────────────────────────────────────────────────────────

def demo_fsm() -> None:
    """
    Demonstrate the FSM with three scenarios:
    1. Successful negotiation (AGREED)
    2. Buyer rejection (FAILED: REJECTED_BY_BUYER)
    3. Max turns exceeded (FAILED: MAX_TURNS_EXCEEDED)
    """
    print("=" * 65)
    print("NegotiationFSM -- Termination Guarantee Demo")
    print("Property: 742 Evergreen Terrace, Austin, TX 78701")
    print("=" * 65)

    # ── Scenario 1: Successful agreement ──────────────────────────────────────
    print("\n--- Scenario 1: Deal Reached ---")
    fsm = NegotiationFSM(max_turns=5)
    print(f"Initial: {fsm}")

    fsm.start()
    print(f"After start(): {fsm}")

    # Simulate 3 rounds of negotiation
    for round_num in range(1, 4):
        still_going = fsm.process_turn()
        print(f"Round {round_num}: {fsm}  ->  continues={still_going}")

    # Agreement in round 3
    fsm.accept(price=449_000)
    print(f"After accept($449,000): {fsm}")
    print(f"is_terminal(): {fsm.is_terminal()}")
    print(f"agreed_price: ${fsm.context.agreed_price:,.0f}")

    fsm.check_invariants()
    print("Invariants: PASS")

    # ── Scenario 2: Buyer walks away ──────────────────────────────────────────
    print("\n--- Scenario 2: Buyer Walks Away ---")
    fsm2 = NegotiationFSM(max_turns=5)
    fsm2.start()
    fsm2.process_turn()   # Round 1
    fsm2.process_turn()   # Round 2
    fsm2.reject(by_buyer=True)
    print(f"After buyer rejection: {fsm2}")
    print(f"is_terminal(): {fsm2.is_terminal()}")
    print(f"failure_reason: {fsm2.context.failure_reason.name}")

    # Verify terminal state blocks further transitions
    result = fsm2.accept(price=440_000)
    print(f"Trying to accept after rejection: {result}  <-- Returns False, state unchanged")
    print(f"State is still: {fsm2.state.name}  <-- Cannot escape terminal state")

    fsm2.check_invariants()
    print("Invariants: PASS")

    # ── Scenario 3: Max turns exceeded ────────────────────────────────────────
    print("\n--- Scenario 3: Max Turns Exceeded (Deadlock) ---")
    fsm3 = NegotiationFSM(max_turns=5)
    fsm3.start()

    for i in range(1, 10):  # Try to run 9 rounds (past the limit of 5)
        result = fsm3.process_turn()
        print(f"  process_turn() round {i}: returned={result}, state={fsm3.state.name}")
        if fsm3.is_terminal():
            print(f"  -> FSM terminated at round {i} (max_turns={fsm3.context.max_turns})")
            break

    print(f"\nFinal: {fsm3}")
    print(f"failure_reason: {fsm3.context.failure_reason.name}")
    fsm3.check_invariants()
    print("Invariants: PASS")

    # ── Key takeaways ──────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("KEY TAKEAWAYS")
    print("=" * 65)
    print("""
1. TERMINAL STATES CAN NEVER BE EXITED
   TRANSITIONS[AGREED] = set()   <-- empty set = no way out
   TRANSITIONS[FAILED] = set()   <-- empty set = no way out

2. MAX TURNS GUARANTEES EXIT
   process_turn() auto-transitions to FAILED at max_turns.
   No 'while True' needed -- just 'while not fsm.is_terminal()'.

3. INVARIANTS ARE PROVABLE
   check_invariants() verifies correctness at any checkpoint.
   In production, run this after every state change.

4. COMPARE TO LANGGRAPH
   LangGraph's StateGraph provides the same guarantees at
   workflow scale -- the graph has a terminal END node with
   no outgoing edges, and conditional routing enforces the
   same termination properties.

NEXT STEP:
  python main_simple.py   <-- Full MCP + A2A + LangGraph version
    """)


if __name__ == "__main__":
    demo_fsm()
