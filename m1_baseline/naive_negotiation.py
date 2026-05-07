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
  MCP       -> solves problem #8  (grounded context)
  FSM       -> solves problems #3, #4, #6 (state machine + termination guarantee)
  ADK       -> solves problems #3, #9 (workflow agents + event/streaming observability)
  A2A       -> solves problems #1, #2, #5 (structured messages, schema validation)

HOW TO RUN:
  python m1_baseline/naive_negotiation.py

WHAT TO WATCH FOR:
  • Demo 1: "Works by luck" -- but notice the LLM's response format is unpredictable
  • Demo 2: Impossible agreement -- watch whether it loops or exits early by accident
  • Failure mode demos -- see all 4 ways the regex parser breaks on real LLM output

COMPARE WITH:
  adk web m3_adk_multiagents/negotiation_agents/  <- The fixed version
"""

import os
import re
from typing import Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# LLM CLIENT
# One shared client -- no retry logic, no error handling (PROBLEM #7)
# ─────────────────────────────────────────────────────────────────────────────

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _call_llm(prompt: str) -> str:
    """
    Naive LLM call -- raw string in, raw string out.

    PROBLEM #1: No response_format, no JSON schema, no structured output.
                The model returns whatever it wants. We have to parse it.
    PROBLEM #2: No validation. If the model hallucinates a price or omits one,
                the caller has no way to know.
    PROBLEM #7: Exceptions propagate uncaught -- one bad API call can crash
                the entire negotiation with no recovery.
    """
    response = _client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,   # non-zero temp = non-deterministic output
    )
    return response.choices[0].message.content  # raw string, no parsing


# ─────────────────────────────────────────────────────────────────────────────
# PROPERTY CONTEXT (hardcoded -- PROBLEM #8)
# In the real version these come from MCP servers (pricing_server.py,
# inventory_server.py). Hardcoded values go stale and can't be validated.
# ─────────────────────────────────────────────────────────────────────────────

PROPERTY_ADDRESS     = "742 Evergreen Terrace, Austin, TX 78701"  # used in display/headers only
PROPERTY_FOR_PROMPTS = "a residential property in Austin, TX"       # used in LLM prompts -- no street number
                                                                     # (street number in prompts causes regex
                                                                     # to extract 742 as price -- see BUG CAUGHT)
LISTING_PRICE    = 485_000   # Should come from MCP get_market_price()
BUYER_MAX_PRICE  = 460_000   # Budget -- should inform via A2A, not hardcoded
SELLER_MIN_PRICE = 445_000   # Floor -- should come from MCP get_minimum_acceptable_price()
SELLER_ASKING_PRICE = 477_000


# ─────────────────────────────────────────────────────────────────────────────
# NAIVE BUYER AGENT
# ─────────────────────────────────────────────────────────────────────────────

class NaiveBuyer:
    """
    A naive buyer agent that calls an LLM and communicates via raw strings.

    PROBLEMS:
    - Prompt asks for free-form text -- no JSON, no price field, no message_type
    - The LLM might mention other dollar amounts (comps, renovation costs) that
      confuse the regex parser downstream
    - The LLM might phrase acceptance as "I agree" instead of "ACCEPT" -- the
      termination check in run_naive_negotiation() will miss it
    - max_price is baked into the prompt -- visible to anyone who reads the code
    - No memory: each call gets a fresh prompt with no prior context
    """

    def __init__(self, name: str, max_price: float):
        self.name = name
        self.max_price = max_price
        self.current_offer = max_price * 0.923   # start ~12% below max

    def make_initial_offer(self) -> str:
        """Ask the LLM to open negotiations. Returns a raw string."""
        prompt = f"""You are a home buyer. Send a short negotiation message to the seller.
Your opening offer is ${self.current_offer:,.0f}. Do not reveal your maximum budget.
Reply in plain prose, 1-2 sentences, no salutation. Mention only your offer price."""
        return _call_llm(prompt)

    def respond_to_counter(self, seller_message: str) -> str:
        """
        Parse the seller's counter and decide the next move.

        PROBLEM #5: This regex is fragile and will fail on:
        - Different number formats ($477K vs $477,000 vs 477000)
        - Multiple prices in one message ("Comps show $430K, I'm asking $470K")
        - Written-out numbers ("four hundred and seventy thousand")
        - Non-English responses

        PROBLEM #7: Silent failure -- if parsing returns None we just repeat
        our offer and the negotiation continues on corrupted data.
        """
        # ╔══════════════════════════════════════════════════════════════════╗
        # ║ PROBLEM: Grabs the FIRST number found.                           ║
        # ║ "Comps in the area sold for $430K; my counter is $470,000"       ║
        # ║ extracts $430,000 -- the wrong price!                            ║
        # ╚══════════════════════════════════════════════════════════════════╝
        price_match = re.search(r'\$?(\d[\d,]*(?:\.\d{2})?)', seller_message)

        if not price_match:
            # ╔════════════════════════════════════════════════════════════╗
            # ║ SILENT FAILURE: We don't know the seller's price but we    ║
            # ║ keep going. The negotiation proceeds on bad data.           ║
            # ╚════════════════════════════════════════════════════════════╝
            return f"I'm not sure I understood your counter. My offer stands at ${self.current_offer:,.0f}."

        raw = price_match.group(1).replace(',', '')
        if not raw:
            return f"I'm not sure I understood your counter. My offer stands at ${self.current_offer:,.0f}."
        seller_price = float(raw)

        if seller_price <= self.max_price:
            accept_prompt = f"""You are a home buyer. The seller has come down to ${seller_price:,.0f},
which is within your budget. Write a 1-sentence acceptance message.
Start your message with the word ACCEPT."""
            return _call_llm(accept_prompt)

        # Increase offer by 10% but never exceed max
        self.current_offer = min(self.current_offer * 1.10, self.max_price)

        prompt = f"""You are a home buyer in a real estate negotiation.
Your counter-offer is ${self.current_offer:,.0f}. Do not reveal your maximum budget.
{"This is your absolute final offer -- say so firmly." if self.current_offer >= self.max_price else "Express willingness to keep negotiating."}
Write 2-3 sentences. Mention only your new offer price."""
        return _call_llm(prompt)


# ─────────────────────────────────────────────────────────────────────────────
# NAIVE SELLER AGENT
# ─────────────────────────────────────────────────────────────────────────────

class NaiveSeller:
    """
    A naive seller agent that calls an LLM and communicates via raw strings.

    PROBLEMS:
    - min_price is baked into the prompt -- leaks the floor to anyone reading code
    - No market data: the LLM reasons purely from the hardcoded asking price
    - Free-form response means the buyer's parser may extract the wrong number
    - The LLM might accept without saying "DEAL" -- termination check misses it
    """

    def __init__(self, name: str, min_price: float, asking_price: float):
        self.name = name
        self.min_price = min_price         # PROBLEM #8: should come from MCP
        self.asking_price = asking_price
        self.current_price = asking_price

    def respond_to_offer(self, buyer_message: str) -> str:
        """
        Parse buyer's offer and respond via LLM.

        PROBLEM #5 + #6: We check for "ACCEPT" in the buyer's message to decide
        whether to close. But the LLM might write "I'd be happy to accept" or
        "this is acceptable" -- neither triggers our check.
        """
        # ╔══════════════════════════════════════════════════════════════════╗
        # ║ PROBLEM: Keyword check is easily fooled by LLM phrasing.         ║
        # ║ "I cannot accept anything below $450K" contains "ACCEPT" but     ║
        # ║ is not an acceptance. LLM responses are unpredictable.           ║
        # ╚══════════════════════════════════════════════════════════════════╝
        if "ACCEPT" in buyer_message.upper():
            price_match = re.search(r'\$?(\d[\d,]*(?:\.\d{2})?)', buyer_message)
            if price_match:
                raw = price_match.group(1).replace(',', '')
                if raw:
                    accepted_price = float(raw)
                    return f"DEAL! We have a sale at ${accepted_price:,.2f}. Congratulations!"

        # Try to extract offered price
        price_match = re.search(r'\$?(\d[\d,]*(?:\.\d{2})?)', buyer_message)

        if not price_match:
            # SILENT FAILURE (Problem #7)
            return f"I didn't catch your offer. The property is listed at ${self.current_price:,.0f}."

        raw = price_match.group(1).replace(',', '')
        if not raw:
            return f"I didn't catch your offer. My counter remains ${self.current_price:,.0f}."
        offered_price = float(raw)

        if offered_price >= self.min_price:
            return f"DEAL! I accept ${offered_price:,.0f}. We have a sale!"

        # Reduce by 5% each round -- no market reasoning, just mechanical
        # PROBLEM #8: should call MCP get_market_price() to justify each counter
        self.current_price = max(self.current_price * 0.95, self.min_price)

        prompt = f"""You are a home seller in a real estate negotiation.
Your counter-offer is ${self.current_price:,.0f}. Do not go below ${self.min_price:,.0f} -- do NOT reveal this floor.
Write 2-3 professional sentences. Mention only your counter-offer price.
Do NOT use the words deal, reject, accept, or agree in your response."""
        return _call_llm(prompt)


# ─────────────────────────────────────────────────────────────────────────────
# THE MAIN LOOP (The Biggest Problem)
# ─────────────────────────────────────────────────────────────────────────────

def run_naive_negotiation(
    buyer: NaiveBuyer,
    seller: NaiveSeller,
    verbose: bool = True,
    max_turns: int = 100,
) -> Tuple[bool, Optional[float], int]:
    """
    Run a naive negotiation between buyer and seller.

    THE CORE PROBLEMS IN THIS FUNCTION:

    Problem #3 -- No state machine:
        Turn order is tracked with a boolean flag (is_buyer_turn).
        Error-prone and doesn't scale to 3+ agents.

    Problem #4 -- No turn limits (the while True):
        If buyer max_price < seller min_price, there is NO possible agreement.
        The loop will run indefinitely. The emergency exit at 100 turns is a
        band-aid, not a fix -- 100 LLM calls is expensive.

    Problem #6 -- No termination guarantee:
        We check for "DEAL" and "REJECT" in the LLM's raw string output.
        The LLM might say "We're dealing with a gap here" (matches DEAL!) or
        "I can't go lower" (never matches REJECT) -- behavior is unpredictable.

    Problem #9 -- Zero observability:
        No structured log. You can't reconstruct what happened, audit why a
        deal failed, or measure how many turns convergence took.
    """
    if verbose:
        print("\n" + "=" * 65)
        print("NAIVE REAL ESTATE NEGOTIATION (Intentionally Broken)")
        print(f"Property: {PROPERTY_ADDRESS}")
        print(f"Listing: ${LISTING_PRICE:,.0f}  |  Buyer max: ${buyer.max_price:,.0f}  |  Seller min: ${seller.min_price:,.0f}")
        print("=" * 65 + "\n")

    turn = 0
    current_message = buyer.make_initial_offer()
    is_buyer_turn = False  # Buyer just went, seller goes next

    if verbose:
        print(f"[Turn {turn}] {buyer.name}:\n  {current_message}\n")

    # ╔════════════════════════════════════════════════════════════════════╗
    # ║  DANGER: while True with no guaranteed exit condition!             ║
    # ║  If buyer max < seller min, agents can NEVER agree.               ║
    # ║  This will run until the 100-turn emergency exit -- 100 LLM calls.║
    # ║                                                                    ║
    # ║  FIX: NegotiationFSM (state_machine.py)                           ║
    # ║  BETTER FIX: ADK workflow agents (m3_adk_multiagents/)             ║
    # ╚════════════════════════════════════════════════════════════════════╝
    while True:
        turn += 1

        # ── Emergency exit (band-aid, not a fix) ──────────────────────────
        if turn > max_turns:
            if verbose:
                print(f"\n[EMERGENCY] Exceeded {max_turns} turns -- forcing exit without agreement")
            return False, None, turn

        # ── Take a turn ────────────────────────────────────────────────────
        if is_buyer_turn:
            current_message = buyer.respond_to_counter(current_message)
            speaker = buyer.name
        else:
            current_message = seller.respond_to_offer(current_message)
            speaker = seller.name

        if verbose:
            print(f"[Turn {turn}] {speaker}:\n  {current_message}\n")

        # ── Check termination via STRING MATCHING (Problem #6) ─────────────
        # FRAGILE: LLM output is free-form. "DEAL-breaker", "I can deal with
        # that", "dealing with renovations" all contain "DEAL".
        # "I simply cannot accept" contains neither "DEAL" nor "REJECT".
        if "DEAL" in current_message.upper():
            price_match = re.search(r'\$?(\d[\d,]*(?:\.\d{2})?)', current_message)
            if price_match:
                raw = price_match.group(1).replace(',', '')
                final_price = float(raw) if raw else None
            else:
                final_price = None
            if verbose:
                status = f"${final_price:,.2f}" if final_price else "unknown price"
                print(f"\n[OK] Deal reached at {status} after {turn} turns")
                # ── Sanity check: catch the silent corruption (Problem #5 + #7) ──
                if final_price is not None and final_price < 10_000:
                    print(f"\n{'!'*65}")
                    print(f"  BUG CAUGHT: 'Deal' price ${final_price:,.0f} is clearly wrong.")
                    print(f"  The property is listed at ${LISTING_PRICE:,.0f}.")
                    print(f"")
                    print(f"  What happened (Failure Mode #5):")
                    print(f"  The regex r'\\$?([\\d,]+)' has an OPTIONAL dollar sign.")
                    print(f"  It grabbed '{int(final_price)}' -- the first number it found --")
                    print(f"  instead of the actual counter-offer price.")
                    print(f"  This could be a house number, a year, a room count,")
                    print(f"  or any digit the LLM happened to mention first.")
                    print(f"")
                    print(f"  The buyer saw seller_price={final_price:,.0f}, which is")
                    print(f"  under their max budget, and accepted. No error was raised.")
                    print(f"  The negotiation 'succeeded' on completely corrupted data.")
                    print(f"")
                    print(f"  FIX: price: float in NegotiationMessage TypedDict.")
                    print(f"  The LLM must return a structured object -- regex never runs.")
                    print(f"{'!'*65}\n")
            return True, final_price, turn

        if "REJECT" in current_message.upper():
            if verbose:
                print(f"\n[FAILED] Negotiation failed after {turn} turns")
            return False, None, turn

        is_buyer_turn = not is_buyer_turn


# ─────────────────────────────────────────────────────────────────────────────
# FAILURE MODE DEMONSTRATIONS (static -- no LLM needed)
# ─────────────────────────────────────────────────────────────────────────────

def demonstrate_failure_modes() -> None:
    """
    Demonstrate each failure mode with concrete examples.
    These use static strings to show exactly how the regex and string matching
    break -- no LLM needed because these are deterministic bugs.
    """
    print("\n" + "=" * 70)
    print("FAILURE MODE DEMONSTRATIONS")
    print("=" * 70)

    # ── Failure 1: Ambiguous price extraction ──────────────────────────────
    print("\n--- FAILURE 1: Ambiguous Message Parsing ---")
    message = "I spent $350,000 on renovations, but my counter-offer is $477,000"
    price_match = re.search(r'\$?(\d[\d,]*(?:\.\d{2})?)', message)
    print(f"LLM says:       '{message}'")
    print(f"Regex extracts: ${price_match.group(1) if price_match else 'None'}")
    print(f"PROBLEM: Got $350,000 (renovation cost) -- the offer was $477,000!")
    print(f"FIX: NegotiationMessage TypedDict with explicit 'price: float' field")

    # ── Failure 2: Written-out price (silent None) ─────────────────────────
    print("\n--- FAILURE 2: Silent Parsing Failure ---")
    message = "I'd like to offer four hundred and thirty thousand dollars"
    price_match = re.search(r'\$?(\d[\d,]*(?:\.\d{2})?)', message)
    print(f"LLM says:       '{message}'")
    print(f"Regex extracts: {price_match}")
    print(f"PROBLEM: Returns None -- negotiation silently continues on bad data!")
    print(f"FIX: Pydantic model_validate() raises immediately on missing price")

    # ── Failure 3: Infinite loop with no ZOPA ─────────────────────────────
    print("\n--- FAILURE 3: No Agreement Possible (No ZOPA) ---")
    print(f"Buyer max price:  $430,000")
    print(f"Seller min price: $450,000")
    print(f"Gap:              $20,000 -- these agents can NEVER agree!")
    print(f"Without the emergency exit, 'while True' runs forever.")
    print(f"FIX: FSM.process_turn() guarantees exit at max_turns=5")

    # ── Failure 4: Hardcoded prices instead of MCP ────────────────────────
    print("\n--- FAILURE 4: Hardcoded Prices (No MCP) ---")
    print(f"SELLER_MIN_PRICE = {SELLER_MIN_PRICE:,.0f} -- hardcoded in source code")
    print(f"Should come from:")
    print(f"  -> MCP: get_minimum_acceptable_price('742 Evergreen Terrace...')")
    print(f"  -> MCP: get_market_price('742 Evergreen Terrace...')")
    print(f"  -> MCP: get_inventory_level('78701')")
    print(f"PROBLEM: Stale values, visible to all, can't be updated without code change")
    print(f"FIX: MCP servers (m2_mcp/pricing_server.py, inventory_server.py)")

    # ── Failure 5: LLM termination is unreliable ──────────────────────────
    print("\n--- FAILURE 5: String-Match Termination Is Unreliable ---")
    cases = [
        ("DEAL-breaker -- I won't go lower",            True,  "false positive"),
        ("We have a DEAL at $452,000!",                 True,  "correct"),
        ("I simply cannot go lower",                    False, "missed rejection"),
        ("This offer is REJECTED outright",             True,  "correct REJECT"),
        ("I think we're close, let's finalize this",    False, "missed agreement"),
    ]
    for msg, matched, label in cases:
        hit = "DEAL" in msg.upper() or "REJECT" in msg.upper()
        flag = "BUG" if (hit != matched) or (hit and label == "false positive") else "OK"
        print(f"  [{flag}] '{msg[:55]}...' -> {'match' if hit else 'no match'} ({label})")
    print(f"FIX: message_type: Literal['OFFER','COUNTER_OFFER','ACCEPT','REJECT','WITHDRAW']")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Run three demos in teaching order:
      Demo 1 -> optimistic case (appears to work -- fragile)
      Demo 2 -> impossible case (reveals control-flow weakness)
      Demo 3 -> targeted failure examples (root-cause visibility)
    """

    # ── Demo 1: When it "works" ────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("DEMO 1: When It Works (By Luck -- Fragile!)")
    print("=" * 65)
    print("Buyer max $460K vs Seller min $445K -- there IS a ZOPA here.")
    print("This may succeed, but watch how unpredictable the path is.\n")

    buyer  = NaiveBuyer("Alice (Buyer)", max_price=BUYER_MAX_PRICE)
    seller = NaiveSeller("Bob (Seller)", min_price=SELLER_MIN_PRICE, asking_price=SELLER_ASKING_PRICE)

    success, price, turns = run_naive_negotiation(buyer, seller)

    if success:
        if price and price < 10_000:
            print(f"\n-> Reported 'deal' at ${price:,.2f} -- THIS IS A CORRUPTED PRICE, NOT A REAL DEAL.")
            print(f"-> The system has no way to detect this. It returned success=True with no error.")
        else:
            print(f"\n-> Deal at ${price:,.2f} in {turns} turns")
            if price:
                print(f"-> Buyer saved ${LISTING_PRICE - price:,.0f} from listing price of ${LISTING_PRICE:,.0f}")
    else:
        print(f"\n-> No deal after {turns} turns")

    # ── Demo 2: Impossible agreement -- infinite loop ─────────────────────
    DEMO2_MAX_TURNS = 8   # cap for the demo; real code uses 100
    print("\n" + "=" * 65)
    print("DEMO 2: Impossible Agreement (No ZOPA) -- The Infinite Loop")
    print("=" * 65)
    print("Buyer max $420K vs Seller min $450K -- gap of $30K, NO deal possible.")
    print("There is mathematically NO price both sides will accept.")
    print(f"Capped at {DEMO2_MAX_TURNS} turns here to save API calls. In production: runs to 100.\n")

    buyer2  = NaiveBuyer("Alice (Buyer)", max_price=420_000)
    seller2 = NaiveSeller("Bob (Seller)", min_price=450_000, asking_price=477_000)

    success2, price2, turns2 = run_naive_negotiation(
        buyer2, seller2, verbose=True, max_turns=DEMO2_MAX_TURNS
    )

    print(f"\nResult: success={success2}, price={price2}, turns={turns2}")
    if not success2 and turns2 >= DEMO2_MAX_TURNS:
        print(f"")
        print(f"PROBLEM: Ran all {turns2} turns with ZERO chance of success.")
        print(f"         Every single LLM call was wasted. In production the cap is 100")
        print(f"         turns -- potentially $1+ in API costs for a negotiation that")
        print(f"         was doomed from round 1.")
        print(f"")
        print(f"         The FSM exits at turn 5 by design, not by emergency.")
        print(f"         Cost: 0 LLM calls for the termination decision.")
        print(f"         Just one state transition: NEGOTIATING -> FAILED.")
    elif success2 and price2 and price2 < 10_000:
        print(f"NOTICE: Reported 'success' at ${price2:,.0f} -- same street-address regex bug.")
        print(f"        Buyer max was $420K, seller min was $450K -- no deal was possible.")
        print(f"        Yet the system returned success=True with no error.")
    else:
        print(f"NOTICE: LLM accidentally used 'DEAL' or 'REJECT' and triggered early exit.")
        print(f"        Stopped for the wrong reason -- Failure Mode #6 (string matching).")
    print(f"\nFIX: FSM process_turn() transitions to FAILED at max_rounds by design.")

    # ── Demo 3: Failure modes ──────────────────────────────────────────────
    demonstrate_failure_modes()

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("WHY THIS MATTERS -- The Full Architecture Solution")
    print("=" * 65)
    print("""
Each problem maps to a specific solution in the workshop:

  Problem #1   Raw strings          -> Pydantic NegotiationMessage at A2A boundary
  Problem #2   No schema            -> Pydantic / A2A DataPart with typed fields
  Problem #3   No state machine     -> NegotiationFSM (m1_baseline/state_machine.py)
  Problem #4   No turn limits       -> FSM.process_turn() + ADK LoopAgent max_iterations
  Problem #5   Fragile regex        -> price: float field -- no regex needed
  Problem #6   No term. guarantee   -> FSM terminal states + ADK workflow termination
  Problem #7   Silent failures      -> Pydantic model_validate() at A2A boundary
  Problem #8   Hardcoded prices     -> MCP servers (m2_mcp/pricing_server.py)
  Problem #9   No observability     -> ADK Event stream + A2A task lifecycle states
  Problem #10  No evaluation        -> Session analytics, agreed price tracking

RUN THE FIXED VERSION:
  adk web m3_adk_multiagents/negotiation_agents/
    """)


if __name__ == "__main__":
    main()
