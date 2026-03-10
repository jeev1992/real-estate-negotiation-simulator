"""
BASELINE SYSTEM: Naive Real Estate Negotiation
===============================================

This file intentionally demonstrates how most first-attempt agent systems fail.
It represents the "obvious" implementation that seems reasonable but breaks down
in practice.

╔══════════════════════════════════════════════════════════════════════════════╗
║  THIS CODE IS INTENTIONALLY BROKEN -- IT IS THE PROBLEM WE'RE SOLVING        ║
╚══════════════════════════════════════════════════════════════════════════════╝

INTENTIONAL PROBLEMS IN THIS CODE:
1. Raw string communication between agents
2. No schema validation -- messages can be anything
3. No state machine -- just a while True loop
4. No turn limits -- can loop forever
5. Ambiguous parsing -- regex on free-form text
6. No termination guarantees
7. Silent failures when parsing goes wrong
8. No grounded context -- prices are hardcoded (should come from MCP)
9. No observability -- can't see what happened
10. No evaluation -- can't measure quality

This is the MOTIVATING FAILURE that drives the entire architecture:
  MCP    -> solves problem #8  (grounded context)
  A2A    -> solves problems #1, #2, #5 (structured messages, schema validation)
  FSM    -> solves problems #3, #4, #6 (state machine + termination guarantee)
  LangGraph -> solves problems #3, #9 (workflow graph + observability)

HOW TO RUN:
  python m1_baseline/naive_negotiation.py

WHAT TO WATCH FOR:
  • Demo 1: "Works by luck" -- notice how fragile the success is
  • Demo 2: Impossible agreement -- loop runs until emergency exit
  • Failure mode demos -- see all 4 ways the regex parser breaks

COMPARE WITH:
    python m3_langgraph_multiagents/main_langgraph_multiagent.py   ← The fixed version (MCP + typed messages + LangGraph)
"""

import re
from typing import Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# PROPERTY CONTEXT (hardcoded -- PROBLEM #8)
# In the real version these come from MCP servers (pricing_server.py,
# inventory_server.py). Hardcoded values go stale and can't be validated.
# ─────────────────────────────────────────────────────────────────────────────

PROPERTY_ADDRESS = "742 Evergreen Terrace, Austin, TX 78701"
LISTING_PRICE = 485_000          # Should come from MCP get_market_price()
BUYER_MAX_PRICE = 460_000        # Budget -- should inform via A2A, not hardcoded
SELLER_MIN_PRICE = 445_000       # Floor -- should come from MCP get_minimum_acceptable_price()
SELLER_ASKING_PRICE = 477_000    # Initial counter -- should be informed by MCP data


# ─────────────────────────────────────────────────────────────────────────────
# NAIVE BUYER AGENT
# ─────────────────────────────────────────────────────────────────────────────

class NaiveBuyer:
    """
    A naive buyer agent that communicates via raw strings.

    PROBLEMS:
    - No structured message format (strings, not Pydantic models)
    - State is implicit (just self.current_offer) and easy to corrupt
    - Strategy is entangled with parsing logic -- hard to change either
    - No access to market data -- relies on hardcoded BUYER_MAX_PRICE
    - Can't express conditions, closing timeline, or concessions
    """

    def __init__(self, name: str, max_price: float):
        self.name = name
        self.max_price = max_price
        self.current_offer = None

    def make_initial_offer(self) -> str:
        """Generate initial offer as raw string."""
        # Start at about 87% of max price (roughly $425K for our $460K budget)
        self.current_offer = self.max_price * 0.923
        return (
            f"I'd like to purchase {PROPERTY_ADDRESS}. "
            f"My offer is ${self.current_offer:,.2f}. "
            f"This is contingent on home inspection."
        )

    def respond_to_counter(self, seller_message: str) -> str:
        """
        Parse seller's response and decide next action.

        PROBLEM #5: This regex parsing is fragile and will fail on:
        - Different number formats ($477,000 vs $477K vs 477000)
        - Typos ("$477,00" vs "$477,000")
        - Unexpected message structures
        - Multiple prices in one message ("I paid $350K, now asking $477K")
        - Non-English responses

        PROBLEM #7: Silent failure -- if we can't parse, we just repeat our offer
        and the negotiation continues without either side knowing something broke.
        """
        # Try to extract price from seller's message
        # ╔══════════════════════════════════════════════════════════════════╗
        # ║ PROBLEM: This regex matches the FIRST number it finds.           ║
        # ║ In "I paid $350K renovating, so my counter is $477,000" it       ║
        # ║ extracts $350,000 -- the WRONG price!                              ║
        # ╚══════════════════════════════════════════════════════════════════╝
        price_match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', seller_message)

        if not price_match:
            # ╔═══════════════════════════════════════════════════════════╗
            # ║  SILENT FAILURE (Problem #7): We don't know what the      ║
            # ║  seller said, but we'll just keep going. This is a bug.   ║
            # ╚═══════════════════════════════════════════════════════════╝
            return f"I'm confused by your response. My offer remains ${self.current_offer:,.2f}."

        seller_price = float(price_match.group(1).replace(',', ''))

        # Accept if seller came down to or below our max
        if seller_price <= self.max_price:
            return f"ACCEPT: I'll purchase the property at ${seller_price:,.2f}."

        # Increase our offer by 10% but never exceed max
        self.current_offer = min(self.current_offer * 1.10, self.max_price)

        if self.current_offer >= self.max_price:
            return (
                f"My final offer is ${self.current_offer:,.2f}. "
                "That is my absolute maximum. Take it or leave it."
            )

        return (
            f"I can increase my offer to ${self.current_offer:,.2f}. "
            "I hope we can find a middle ground."
        )


# ─────────────────────────────────────────────────────────────────────────────
# NAIVE SELLER AGENT
# ─────────────────────────────────────────────────────────────────────────────

class NaiveSeller:
    """
    A naive seller agent that communicates via raw strings.

    PROBLEMS:
    - No access to grounded context (pricing rules, inventory, CRM)
    - min_price and asking_price are hardcoded (should come from MCP)
    - No validation of buyer's messages -- can be manipulated by malformed input
    - Can't express conditions, timeline requirements, or contingency rejections
    - Mixed parsing and business logic makes both harder to change
    """

    def __init__(self, name: str, min_price: float, asking_price: float):
        self.name = name
        self.min_price = min_price      # PROBLEM #8: Should come from MCP get_minimum_acceptable_price()
        self.asking_price = asking_price
        self.current_price = asking_price

    def respond_to_offer(self, buyer_message: str) -> str:
        """
        Parse buyer's offer and respond.

        PROBLEM #5: Extremely brittle parsing.
        PROBLEM #8: No market data -- just mechanically reducing the asking price.
        """
        # Check for acceptance keywords (PROBLEM: keyword matching is fragile)
        if "ACCEPT" in buyer_message.upper():
            price_match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', buyer_message)
            if price_match:
                accepted_price = float(price_match.group(1).replace(',', ''))
                return f"DEAL! We have a sale at ${accepted_price:,.2f}. Congratulations!"

        # Try to extract offered price
        price_match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', buyer_message)

        if not price_match:
            # ╔═══════════════════════════════════════════════════════════╗
            # ║  SILENT FAILURE (Problem #7): Can't parse, but we         ║
            # ║  continue anyway -- the negotiation proceeds on bad data.  ║
            # ╚═══════════════════════════════════════════════════════════╝
            return f"I didn't catch your offer. The property is listed at ${self.current_price:,.2f}."

        offered_price = float(price_match.group(1).replace(',', ''))

        # Accept if at or above our minimum
        if offered_price >= self.min_price:
            return f"DEAL! I accept ${offered_price:,.2f}. We have a sale!"

        # Reduce by 5% each round (mechanical -- no market reasoning)
        # PROBLEM #8: In reality, the seller should query inventory levels,
        # days-on-market, and comparable sales via MCP to justify each counter
        self.current_price = max(self.current_price * 0.95, self.min_price)

        if "final" in buyer_message.lower() or "maximum" in buyer_message.lower():
            # PROBLEM: We're relying on detecting "final" in the buyer's message
            # This is easily gamed: "This is NOT my final offer, but it's $430K"
            if offered_price >= self.min_price * 0.95:
                return f"DEAL! Given your commitment, I'll accept ${offered_price:,.2f}."
            return (
                f"I cannot go that low. My minimum is ${self.min_price:,.2f}. "
                "I'm afraid we can't make this work. REJECT."
            )

        return (
            f"Thank you for your offer. I can counter at ${self.current_price:,.2f}. "
            "The property has had significant recent renovations."
        )


# ─────────────────────────────────────────────────────────────────────────────
# THE MAIN LOOP (The Biggest Problem)
# ─────────────────────────────────────────────────────────────────────────────

def run_naive_negotiation(
    buyer: NaiveBuyer,
    seller: NaiveSeller,
    verbose: bool = True
) -> Tuple[bool, Optional[float], int]:
    """
    Run a naive negotiation between buyer and seller.

    THE CORE PROBLEMS IN THIS FUNCTION:

    Problem #3 -- No state machine:
        The code has no explicit states. When is it "buyer's turn"? When is it
        "seller's turn"? We track this with a boolean flag (is_buyer_turn)
        which is error-prone and doesn't scale to 3+ agents.

    Problem #4 -- No turn limits (the while True):
        If buyer max_price ($460K) < seller min_price ($500K), there is NO
        possible agreement. The loop will run forever. The "emergency exit"
        at 100 turns is a band-aid, not a fix.

    Problem #6 -- No termination guarantee:
        We check for "DEAL" and "REJECT" in the string output. What if the
        LLM says "We have a DEAL-breaker here"? It matches "DEAL"! What if
        it spells "REJECT" as "Rejected"? We miss it!

    Problem #9 -- Zero observability:
        There's no structured log. You can't easily reconstruct what happened,
        calculate convergence rate, or audit why a deal failed.

    Returns:
        (success: bool, final_price: Optional[float], turns: int)
    """
    # LEARNER NOTE:
    # This function is the runtime engine for one negotiation session.
    # Inputs: buyer + seller agent objects.
    # Output: (did_we_get_a_deal, final_price_if_any, number_of_turns)
    if verbose:
        print("\n" + "=" * 65)
        print("NAIVE REAL ESTATE NEGOTIATION (Intentionally Broken)")
        print(f"Property: {PROPERTY_ADDRESS}")
        print(f"Listing: ${LISTING_PRICE:,.0f}  |  Buyer max: ${buyer.max_price:,.0f}  |  Seller min: ${seller.min_price:,.0f}")
        print("=" * 65 + "\n")

    # turn counts total messages exchanged AFTER buyer's opening message.
    turn = 0
    current_message = buyer.make_initial_offer()
    # Control flag for turn-taking. This is a fragile stand-in for a real FSM state.
    is_buyer_turn = False  # Buyer just went, so seller goes next

    if verbose:
        print(f"[Turn {turn}] {buyer.name}: {current_message}")

    # ╔════════════════════════════════════════════════════════════════════╗
    # ║  DANGER: while True with no guaranteed exit condition!             ║
    # ║  If buyer max < seller min, agents can NEVER agree.               ║
    # ║  This will run FOREVER without the emergency exit at 100 turns.   ║
    # ║                                                                    ║
    # ║  FIX: Use NegotiationFSM from m1_baseline/state_machine.py           ║
    # ║  BETTER FIX: Use LangGraph from m3_langgraph_multiagents/langgraph_flow.py   ║
    # ╚════════════════════════════════════════════════════════════════════╝
    while True:
        turn += 1

        # ── Emergency exit (band-aid, not a fix) ──────────────────────────────
        if turn > 100:
            if verbose:
                print(f"\n[EMERGENCY] Exceeded 100 turns -- forcing exit without agreement")
            return False, None, turn

        # ── Take a turn ────────────────────────────────────────────────────────
        # The same string variable (current_message) keeps getting overwritten.
        # There is no typed event history, so debugging later is difficult.
        if is_buyer_turn:
            current_message = buyer.respond_to_counter(current_message)
            speaker = buyer.name
        else:
            current_message = seller.respond_to_offer(current_message)
            speaker = seller.name

        if verbose:
            print(f"[Turn {turn}] {speaker}: {current_message}")

        # ── Check termination via STRING MATCHING (Problem #6) ─────────────────
        # FRAGILE: "DEAL-breaker", "DEAL with the renovation costs", etc. all match
        # LEARNER NOTE:
        # This is "keyword protocol" — outcome control based on text tokens.
        # In robust systems, this should be explicit state transitions.
        if "DEAL" in current_message.upper():
            price_match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', current_message)
            final_price = float(price_match.group(1).replace(',', '')) if price_match else None
            if verbose:
                status = f"${final_price:,.2f}" if final_price else "unknown price"
                print(f"\n[OK] Deal reached at {status} after {turn} turns")
            return True, final_price, turn

        if "REJECT" in current_message.upper():
            if verbose:
                print(f"\nFAILED: Negotiation failed after {turn} turns -- seller rejected")
            return False, None, turn

        # Flip turn for the next loop iteration.
        is_buyer_turn = not is_buyer_turn


# ─────────────────────────────────────────────────────────────────────────────
# FAILURE MODE DEMONSTRATIONS
# ─────────────────────────────────────────────────────────────────────────────

def demonstrate_failure_modes() -> None:
    """
    Demonstrate each failure mode explicitly so learners can see the problems.
    These are NOT edge cases -- they happen regularly in production.
    """
    print("\n" + "=" * 70)
    print("FAILURE MODE DEMONSTRATIONS")
    print("=" * 70)

    # ── Failure Mode 1: Ambiguous price extraction ─────────────────────────────
    print("\n--- FAILURE 1: Ambiguous Message Parsing ---")
    message = "I spent $350,000 on renovations, but my counter-offer is $477,000"
    price_match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', message)
    print(f"Seller says: '{message}'")
    print(f"Regex extracts: ${price_match.group(1) if price_match else 'None'}")
    print(f"PROBLEM: Extracted $350,000 (renovation cost) but the offer was $477,000!")
    print(f"FIX: Use structured negotiation messages with explicit 'price' field (negotiation_types.py)")

    # ── Failure Mode 2: Infinite loop risk ─────────────────────────────────────
    print("\n--- FAILURE 2: No Agreement Possible (No ZOPA) ---")
    print(f"Buyer max price:  $430,000")
    print(f"Seller min price: $450,000")
    print(f"Gap:              $20,000 -- these agents can NEVER agree!")
    print(f"Without the 100-turn emergency exit, this loop would run FOREVER.")
    print(f"FIX: NegotiationFSM.process_turn() guarantees exit at max_turns")

    # ── Failure Mode 3: Silent parsing failure ─────────────────────────────────
    print("\n--- FAILURE 3: Silent Parsing Failure ---")
    message = "I'd like to offer four hundred and thirty thousand dollars"
    price_match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', message)
    print(f"Buyer says: '{message}'")
    print(f"Regex extracts: {price_match}")
    print(f"PROBLEM: Agent silently continues -- seller doesn't know buyer's price!")
    print(f"FIX: Pydantic schema (NegotiationPayload) enforces 'price: float' field")

    # ── Failure Mode 4: Hardcoded prices instead of MCP ───────────────────────
    print("\n--- FAILURE 4: Hardcoded Prices (No MCP) ---")
    print(f"NaiveSeller.min_price = {SELLER_MIN_PRICE:,.0f} -- hardcoded in source code")
    print(f"In production this should come from:")
    print(f"  -> MCP call: get_minimum_acceptable_price('742 Evergreen Terrace...')")
    print(f"  -> MCP call: get_market_price('742 Evergreen Terrace...')")
    print(f"  -> MCP call: get_inventory_level('78701')")
    print(f"PROBLEM: Hardcoded prices go stale and differ from real market conditions")
    print(f"FIX: MCP servers (m2_mcp/pricing_server.py, inventory_server.py)")

    # ── Failure Mode 5: State corruption ──────────────────────────────────────
    print("\n--- FAILURE 5: Implicit State (Easy to Corrupt) ---")
    print("NaiveBuyer tracks state in self.current_offer -- a single float.")
    print("If you called make_initial_offer() twice, state gets corrupted.")
    print("If you add a 3rd agent (mediator), the is_buyer_turn boolean breaks.")
    print("FIX: LangGraph NegotiationState TypedDict + LangGraph graph management")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN -- Run all demos
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Run demonstration of naive negotiation -- both when it works and when it fails.

    LEARNING OBJECTIVE:
    After running this, you should understand WHY each component of the
    full architecture (MCP, A2A, FSM, LangGraph) exists. Every component
    solves a specific failure mode shown here.
    """

    # LEARNER NOTE:
    # The three demos below are intentionally staged in teaching order:
    #   Demo 1 -> optimistic case (appears to work)
    #   Demo 2 -> impossible case (reveals control-flow weakness)
    #   Demo 3 -> targeted failure examples (root-cause visibility)

    # ── Demo 1: Successful negotiation (when it "works" by luck) ──────────────
    print("\n" + "=" * 65)
    print("DEMO 1: When It Works (By Luck -- Fragile!)")
    print("=" * 65)
    print("Buyer max $460K vs Seller min $445K -- there IS a ZOPA here.")
    print("This 'works', but notice how fragile and arbitrary the process is.\n")

    # Create agents with overlapping ranges (ZOPA exists):
    # buyer max (460k) >= seller min (445k)
    buyer = NaiveBuyer("Alice (Buyer)", max_price=BUYER_MAX_PRICE)
    seller = NaiveSeller("Bob (Seller)", min_price=SELLER_MIN_PRICE, asking_price=SELLER_ASKING_PRICE)

    # Run one full negotiation session.
    success, price, turns = run_naive_negotiation(buyer, seller)

    if success:
        print(f"\n-> Deal at ${price:,.2f} in {turns} turns")
        if price:
            savings = LISTING_PRICE - price
            print(f"-> Buyer saved ${savings:,.0f} from listing price of ${LISTING_PRICE:,.0f}")
    else:
        print(f"\n-> No deal after {turns} turns")

    # ── Demo 2: Impossible agreement (demonstrates infinite loop risk) ─────────
    print("\n" + "=" * 65)
    print("DEMO 2: Impossible Agreement (No ZOPA)")
    print("=" * 65)
    print("Buyer max $420K vs Seller min $450K -- gap of $30K, NO deal possible.")
    print("Watch the loop run until the emergency exit at 100 turns.\n")

    # Create agents with NON-overlapping ranges (no ZOPA):
    # buyer max (420k) < seller min (450k)
    buyer2 = NaiveBuyer("Alice (Buyer)", max_price=420_000)
    seller2 = NaiveSeller("Bob (Seller)", min_price=450_000, asking_price=477_000)

    success2, price2, turns2 = run_naive_negotiation(buyer2, seller2, verbose=False)
    print(f"Result: success={success2}, price={price2}, turns={turns2}")
    print(f"PROBLEM: Ran for {turns2} turns with ZERO chance of success!")
    print(f"FIX: FSM process_turn() would exit at max_turns=5, not 100")

    # ── Demo 3: Failure mode demonstrations ────────────────────────────────────
    demonstrate_failure_modes()

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("WHY THIS MATTERS -- The Full Architecture Solution")
    print("=" * 65)
    print("""
Each problem maps to a specific solution in the workshop:

    Problem #1  Raw strings          -> Typed message helpers (negotiation_types.py)
  Problem #2  No schema            -> Pydantic NegotiationPayload
  Problem #3  No state machine     -> NegotiationFSM (m1_baseline/state_machine.py)
  Problem #4  No turn limits       -> FSM.process_turn() + LangGraph max_rounds
  Problem #5  Fragile regex        -> Structured price field in A2AMessage
  Problem #6  No term. guarantee   -> FSM terminal states + LangGraph routing
  Problem #7  Silent failures      -> Pydantic validation exceptions
  Problem #8  Hardcoded prices     -> MCP servers (pricing_server.py)
    Problem #9  No observability     -> LangGraph state history + message IDs
  Problem #10 No evaluation        -> Session analytics, agreed price tracking

RUN THE FIXED VERSION:
    python m3_langgraph_multiagents/main_langgraph_multiagent.py   # OpenAI GPT-4o + MCP + typed messages + LangGraph
  python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102  # Gemini + ADK + true A2A protocol
    """)


if __name__ == "__main__":
    main()
