"""
Finite State Machine for Negotiation
======================================
Solves failure modes #3, #4, and #6 from naive_negotiation.py:
  #3 -- No state machine (while True loop)
  #4 -- No turn limits
  #6 -- No termination guarantees

THE CORE IDEA:
  naive_negotiation.py:  while True: ...  <- no guarantee it ever stops
  this file:             while not fsm.is_terminal(): ...  <- MUST stop

WHY IT MUST STOP:
  1. Terminal states (AGREED, FAILED) have empty transition sets -- no way out.
  2. Every non-terminal turn increments turn_count, which is capped at max_turns.
  So the loop either reaches a terminal state or hits the cap. Both stop it.

HOW TO RUN:
  python m1_baseline/state_machine.py

CONNECTION TO THE REST OF THE WORKSHOP:
  naive_negotiation.py  ->  state_machine.py  ->  m3_adk_multiagents/
  (while True)             (FSM guarantee)        (ADK LoopAgent / workflow agents = FSM at agent scale)
"""

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# STATES
# ─────────────────────────────────────────────────────────────────────────────

class NegotiationState(Enum):
    IDLE        = auto()    # Not started yet
    NEGOTIATING = auto()    # Offers being exchanged
    AGREED      = auto()    # Terminal: deal reached ✓
    FAILED      = auto()    # Terminal: no deal ✗
    # ── Exercise 1: Uncomment the line below ──────────────────────────────
    # TIMEOUT     = auto()    # Terminal: wall-clock deadline exceeded


class FailureReason(Enum):
    MAX_TURNS_EXCEEDED  = auto()    # Ran out of rounds
    REJECTED_BY_BUYER   = auto()    # Buyer walked away
    REJECTED_BY_SELLER  = auto()    # Seller walked away
    # ── Exercise 1: Uncomment the line below ──────────────────────────────
    # WALL_CLOCK_TIMEOUT  = auto()    # Total negotiation time exceeded


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT  (data that travels with the FSM)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FSMContext:
    turn_count:        int                      = 0
    max_turns:         int                      = 5
    agreed_price:      Optional[float]          = None
    failure_reason:    Optional[FailureReason]   = None
    # ── Exercise 1: Uncomment the two lines below ─────────────────────────
    # deadline_seconds:  float                    = 60.0
    # start_time:        float                    = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# THE FSM
# ─────────────────────────────────────────────────────────────────────────────

class NegotiationFSM:

    # The transition table.
    # Read as: "from state X, you may move to any state in set Y"
    #
    # AGREED and FAILED have empty sets -- once you're in them, you can't leave.
    # That emptiness is the termination guarantee.
    TRANSITIONS: dict[NegotiationState, set[NegotiationState]] = {
        NegotiationState.IDLE:        {NegotiationState.NEGOTIATING, NegotiationState.FAILED},
        NegotiationState.NEGOTIATING: {NegotiationState.NEGOTIATING, NegotiationState.AGREED,
                                       NegotiationState.FAILED},
        # ── Exercise 1: Add NegotiationState.TIMEOUT to the NEGOTIATING set above ──
        NegotiationState.AGREED:      set(),   # <-- TERMINAL
        NegotiationState.FAILED:      set(),   # <-- TERMINAL
        # ── Exercise 1: Uncomment the line below ───────────────────────────────────
        # NegotiationState.TIMEOUT:     set(),   # <-- TERMINAL
    }

    def __init__(self, max_turns: int = 5):
        # ── Exercise 1: Change signature to include deadline_seconds: float = 60.0 ──
        self.state   = NegotiationState.IDLE
        self.context = FSMContext(max_turns=max_turns)
        # ── Exercise 1: Pass deadline_seconds=deadline_seconds to FSMContext above ──

    # ── State checks ──────────────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self.state == NegotiationState.NEGOTIATING

    def is_terminal(self) -> bool:
        return self.state in {NegotiationState.AGREED, NegotiationState.FAILED}
        # ── Exercise 1: Add NegotiationState.TIMEOUT to the set above ─────

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """IDLE -> NEGOTIATING. Returns False if already started."""
        if self.state != NegotiationState.IDLE:
            return False
        self.state = NegotiationState.NEGOTIATING
        # ── Exercise 1: Uncomment the line below ──────────────────────────
        # self.context.start_time = time.time()
        return True

    def process_turn(self) -> bool:
        """
        Record one turn. Returns False and transitions to FAILED when max_turns hit.
        This is what makes the loop bounded -- turn_count can't grow forever.
        """
        if not self.is_active:
            return False

        # ── Exercise 1: Uncomment the block below ─────────────────────────
        # # Wall-clock timeout check
        # elapsed = time.time() - self.context.start_time
        # if elapsed > self.context.deadline_seconds:
        #     self.state = NegotiationState.TIMEOUT
        #     self.context.failure_reason = FailureReason.WALL_CLOCK_TIMEOUT
        #     return False

        self.context.turn_count += 1
        if self.context.turn_count >= self.context.max_turns:
            self.state = NegotiationState.FAILED
            self.context.failure_reason = FailureReason.MAX_TURNS_EXCEEDED
            return False
        return True

    def accept(self, price: float) -> bool:
        """NEGOTIATING -> AGREED."""
        if not self.is_active:
            return False
        self.state = NegotiationState.AGREED
        self.context.agreed_price = price
        return True

    def reject(self, by_buyer: bool = True) -> bool:
        """NEGOTIATING -> FAILED."""
        if not self.is_active:
            return False
        self.state = NegotiationState.FAILED
        self.context.failure_reason = (
            FailureReason.REJECTED_BY_BUYER if by_buyer
            else FailureReason.REJECTED_BY_SELLER
        )
        return True

    # ── Invariant check ───────────────────────────────────────────────────────

    def check_invariants(self) -> bool:
        """Verify FSM is in a consistent state. Raises AssertionError if not."""
        assert self.context.turn_count <= self.context.max_turns
        if self.state == NegotiationState.AGREED:
            assert self.context.agreed_price is not None
        if self.state == NegotiationState.FAILED:
            assert self.context.failure_reason is not None
        # ── Exercise 1: Uncomment the block below ─────────────────────────
        # if self.state == NegotiationState.TIMEOUT:
        #     assert self.context.failure_reason is not None, (
        #         "TIMEOUT state requires failure_reason to be set"
        #     )
        if self.is_terminal():
            assert len(self.TRANSITIONS[self.state]) == 0
        return True

    def __repr__(self) -> str:
        return (
            f"NegotiationFSM(state={self.state.name}, "
            f"turn={self.context.turn_count}/{self.context.max_turns})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────────────────────

def demo_fsm() -> None:
    print("=" * 65)
    print("NegotiationFSM -- Termination Guarantee Demo")
    print("Property: 742 Evergreen Terrace, Austin, TX 78701")
    print("=" * 65)

    # ── Scenario 1: Deal reached ───────────────────────────────────────────────
    print("\n--- Scenario 1: Deal Reached ---")
    fsm = NegotiationFSM(max_turns=5)
    print(f"Initial:        {fsm}")
    fsm.start()
    print(f"After start():  {fsm}")

    for round_num in range(1, 4):
        still_going = fsm.process_turn()
        print(f"Round {round_num}:        {fsm}  ->  continues={still_going}")

    fsm.accept(price=449_000)
    print(f"After accept(): {fsm}")
    print(f"is_terminal():  {fsm.is_terminal()}")
    print(f"agreed_price:   ${fsm.context.agreed_price:,.0f}")
    fsm.check_invariants()
    print("Invariants: PASS")

    # ── Scenario 2: Buyer walks away ───────────────────────────────────────────
    print("\n--- Scenario 2: Buyer Walks Away ---")
    fsm2 = NegotiationFSM(max_turns=5)
    fsm2.start()
    fsm2.process_turn()
    fsm2.process_turn()
    fsm2.reject(by_buyer=True)
    print(f"After reject(): {fsm2}")
    print(f"is_terminal():  {fsm2.is_terminal()}")
    print(f"failure_reason: {fsm2.context.failure_reason.name}")

    # Terminal states are sticky -- trying to accept after rejection returns False
    result = fsm2.accept(price=440_000)
    print(f"accept() after reject: returned {result}  <-- state is locked")
    fsm2.check_invariants()
    print("Invariants: PASS")

    # ── Scenario 3: Max turns exceeded ────────────────────────────────────────
    print("\n--- Scenario 3: Max Turns Exceeded (No Agreement Possible) ---")
    fsm3 = NegotiationFSM(max_turns=5)
    fsm3.start()

    for i in range(1, 10):  # Try 9 rounds -- FSM stops at 5
        result = fsm3.process_turn()
        print(f"  Round {i}: returned={result}, state={fsm3.state.name}")
        if fsm3.is_terminal():
            print(f"  -> Terminated at round {i}")
            break

    print(f"\nFinal:          {fsm3}")
    print(f"failure_reason: {fsm3.context.failure_reason.name}")
    fsm3.check_invariants()
    print("Invariants: PASS")

    # ── Exercise 1: Uncomment Scenario 4 after adding TIMEOUT state ────────
    # print("\n--- Scenario 4: Wall-Clock Timeout ---")
    # fsm4 = NegotiationFSM(max_turns=10, deadline_seconds=0.001)
    # fsm4.start()
    # time.sleep(0.01)  # Wait just past the deadline
    # result = fsm4.process_turn()
    # print(f"process_turn() returned: {result}")
    # print(f"Final:          {fsm4}")
    # print(f"state:          {fsm4.state.name}")
    # print(f"failure_reason: {fsm4.context.failure_reason.name}")
    # print(f"is_terminal():  {fsm4.is_terminal()}")
    # fsm4.check_invariants()
    # print("Invariants: PASS")
    # # Verify TIMEOUT is sticky
    # result = fsm4.accept(price=440_000)
    # print(f"accept() after TIMEOUT: returned {result}  <-- state is locked")

    # ── Key takeaway ───────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("KEY TAKEAWAY")
    print("=" * 65)
    print("""
TRANSITIONS[AGREED]  = set()   <- empty = no way out
TRANSITIONS[FAILED]  = set()   <- empty = no way out

Once in a terminal state, the FSM cannot move. Combined with the
turn cap, the loop MUST end.

--- Exercise 1 adds TIMEOUT: ---
TRANSITIONS[TIMEOUT] = set()   <- empty = no way out
Adding TIMEOUT does NOT break the termination guarantee because:
1. TIMEOUT has an empty transition set -- once entered, cannot be exited.
2. The deadline check provides an ADDITIONAL path to a terminal state,
   which can only make termination happen sooner, never later.

NEXT:
  python m3_adk_multiagents/a2a_protocol_seller_server.py
    """)


if __name__ == "__main__":
    demo_fsm()
