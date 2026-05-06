"""
Solution — Exercise 11: Memory-bounded context window
=======================================================

Negotiation orchestrator that implements **memory compression** to prevent
the context window from overflowing during long-running negotiations.

When negotiation_memory exceeds MAX_DETAILED_ROUNDS entries, a
before_model_callback on the buyer summarizes old rounds into compact
aggregate statistics and keeps only the most recent rounds in full detail.

ADK CONCEPTS:
  - before_model_callback: intercept and modify context before LLM call
  - State mutation in callbacks: compress, summarize, and evict memory
  - Incremental summarization: append to existing summary each time
  - Observability: track compression count for monitoring

To demo:

    adk web m3_adk_multiagents/solution/ex11_memory_bounded_context/

    Pick `negotiation`, send: "Start the negotiation for 742 Evergreen Terrace."

    With max_iterations=10 and a tight price gap, the negotiation runs
    many rounds. After round 4+ you'll see "[memory] Compressed ..."
    log lines and memory_summary appearing in the State tab.
"""

import re
import sys
from pathlib import Path

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from google.adk.tools.tool_context import ToolContext

MODEL = "openai/gpt-4o"

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")
_INVENTORY_SERVER = str(_REPO_ROOT / "m2_mcp" / "inventory_server.py")

# ─── Memory compression settings ─────────────────────────────────────────────

MAX_DETAILED_ROUNDS = 4   # compress when memory exceeds this many entries
KEEP_RECENT = 3           # always keep the last N rounds in full detail

# ─── Tool allowlists ─────────────────────────────────────────────────────────

_BUYER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_property_tax_estimate",
}

_SELLER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_inventory_level",
    "get_minimum_acceptable_price",
    "submit_decision",
}


def _enforce_buyer_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the buyer"}
    return None


def _enforce_seller_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
    if tool.name not in _SELLER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the seller"}
    return None


# ─── submit_decision ──────────────────────────────────────────────────────────

def submit_decision(action: str, price: int, tool_context: ToolContext) -> dict:
    """Submit the seller's decision for this round.

    Args:
        action: Exactly "ACCEPT" or "COUNTER".
        price: The price in dollars.
    """
    action_upper = action.strip().upper()
    if action_upper not in ("ACCEPT", "COUNTER"):
        return {"error": f"action must be ACCEPT or COUNTER, got: {action}"}
    tool_context.state["seller_decision"] = {"action": action_upper, "price": price}
    return {"recorded": action_upper, "price": price}


# ─── Price extraction helper ─────────────────────────────────────────────────

_PRICE_RE = re.compile(r"\$?(\d{3,}(?:[,.\s]\d{3})*)")


def _extract_price(text: str) -> int | None:
    """Extract the largest plausible price from free text."""
    if not isinstance(text, str):
        return None
    candidates = []
    for match in _PRICE_RE.finditer(text):
        raw = match.group(1).replace(",", "").replace(" ", "").replace(".", "")
        try:
            n = int(raw)
        except ValueError:
            continue
        if 100_000 <= n <= 1_000_000:
            candidates.append(n)
    return max(candidates) if candidates else None


# ─── Memory accumulation callback (runs after seller each round) ─────────────

def _accumulate_memory_and_check(callback_context: CallbackContext):
    """After the seller: check for ACCEPT, then build structured memory entry."""
    state = callback_context.state

    # Check for acceptance → escalate
    decision = state.get("seller_decision")
    if isinstance(decision, dict) and decision.get("action") == "ACCEPT":
        callback_context.actions.escalate = True
        return None

    # Build memory entry
    memory = list(state.get("negotiation_memory", []))
    round_num = len(memory) + 1

    buyer_price = _extract_price(state.get("buyer_offer", ""))
    seller_price = decision.get("price") if isinstance(decision, dict) else None

    seller_concession = 0
    concession_rate = 0.0
    if memory and seller_price is not None:
        prev_seller = memory[-1].get("seller_counter")
        if prev_seller is not None and prev_seller > 0:
            seller_concession = prev_seller - seller_price
            concession_rate = round(seller_concession / prev_seller, 4)

    gap = (seller_price - buyer_price) if (seller_price and buyer_price) else None

    entry = {
        "round": round_num,
        "buyer_offer": buyer_price,
        "seller_counter": seller_price,
        "seller_concession": seller_concession,
        "concession_rate": concession_rate,
        "gap": gap,
    }
    memory.append(entry)
    state["negotiation_memory"] = memory

    print(
        f"[memory] Round {round_num}: buyer=${buyer_price:,}" if buyer_price else f"[memory] Round {round_num}: buyer=?",
        end="",
    )
    print(
        f" seller=${seller_price:,} concession=${seller_concession:,} gap=${gap:,}"
        if seller_price and gap else ""
    )
    return None


# ─── Memory compression ──────────────────────────────────────────────────────

def _build_summary(old_rounds: list[dict], existing_summary: str) -> str:
    """Compress old round entries into aggregate statistics text."""
    if not old_rounds:
        return existing_summary

    first_round = old_rounds[0]["round"]
    last_round = old_rounds[-1]["round"]

    buyer_prices = [r["buyer_offer"] for r in old_rounds if r.get("buyer_offer")]
    seller_prices = [r["seller_counter"] for r in old_rounds if r.get("seller_counter")]
    concession_rates = [r["concession_rate"] for r in old_rounds if r.get("concession_rate")]

    lines = []

    # Append to any existing compressed summary
    if existing_summary:
        lines.append(existing_summary.rstrip())
        lines.append("")

    lines.append(f"Rounds {first_round}-{last_round} summary:")

    if buyer_prices:
        buyer_movement = buyer_prices[-1] - buyer_prices[0]
        avg_buyer_increase = buyer_movement / max(len(buyer_prices) - 1, 1)
        lines.append(
            f"  Buyer: ${buyer_prices[0]:,} → ${buyer_prices[-1]:,} "
            f"(avg increase ${avg_buyer_increase:,.0f}/round)"
        )

    if seller_prices:
        seller_movement = seller_prices[0] - seller_prices[-1]
        avg_seller_decrease = seller_movement / max(len(seller_prices) - 1, 1)
        lines.append(
            f"  Seller: ${seller_prices[0]:,} → ${seller_prices[-1]:,} "
            f"(avg decrease ${avg_seller_decrease:,.0f}/round)"
        )

    if concession_rates:
        avg_rate = sum(concession_rates) / len(concession_rates)
        trend = "declining" if len(concession_rates) >= 2 and concession_rates[-1] < concession_rates[0] else "steady"
        lines.append(
            f"  Seller concession rate: avg {avg_rate:.1%}, trend {trend}"
        )

    if buyer_prices and seller_prices:
        initial_gap = seller_prices[0] - buyer_prices[0]
        final_gap = seller_prices[-1] - buyer_prices[-1]
        lines.append(f"  Gap: ${initial_gap:,} → ${final_gap:,}")

    return "\n".join(lines)


def _compress_memory(callback_context: CallbackContext):
    """before_model_callback on buyer: compress old rounds when memory is large."""
    state = callback_context.state
    memory = state.get("negotiation_memory", [])

    if len(memory) <= MAX_DETAILED_ROUNDS:
        return None  # no compression needed, proceed normally

    # Split: old rounds → summarize, recent rounds → keep
    old_rounds = memory[:-KEEP_RECENT]
    recent_rounds = memory[-KEEP_RECENT:]

    # Build summary (appends to any existing summary)
    existing_summary = state.get("memory_summary", "")
    summary = _build_summary(old_rounds, existing_summary)

    # Update state
    state["memory_summary"] = summary
    state["negotiation_memory"] = recent_rounds
    state["memory_compressions"] = state.get("memory_compressions", 0) + 1

    old_count = len(old_rounds)
    kept_count = len(recent_rounds)
    compressions = state["memory_compressions"]
    print(
        f"[memory] Compressed {old_count} old rounds into summary "
        f"(now {kept_count} detailed + summary, compression #{compressions})"
    )

    return None  # allow the model call to proceed


# ─── Round-1 state init ──────────────────────────────────────────────────────

def _init_round_state(callback_context: CallbackContext):
    if "seller_response" not in callback_context.state:
        callback_context.state["seller_response"] = "(No seller response yet — this is round 1)"
    if "negotiation_memory" not in callback_context.state:
        callback_context.state["negotiation_memory"] = []
    if "memory_summary" not in callback_context.state:
        callback_context.state["memory_summary"] = ""
    return None


# ─── The agents ───────────────────────────────────────────────────────────────

buyer = LlmAgent(
    name="buyer",
    model=MODEL,
    instruction=(
        "You are an expert real estate buyer agent representing a client "
        "purchasing 742 Evergreen Terrace, Austin, TX 78701 (listed at $485,000).\n\n"
        "YOUR CLIENT'S CONSTRAINTS:\n"
        "- Maximum budget: $460,000 (NEVER offer above this)\n"
        "- Target acquisition price: $450,000–$458,000\n\n"
        "NEGOTIATION HISTORY SUMMARY (older rounds):\n"
        "{memory_summary}\n\n"
        "RECENT ROUNDS (full detail):\n"
        "{negotiation_memory}\n\n"
        "STRATEGY:\n"
        "- Call MCP pricing tools BEFORE every offer for market data\n"
        "- Round 1: offer ~10%% below asking (~$435,000)\n"
        "- Each subsequent round: increase by 1–3%% based on seller movement\n"
        "- If seller is barely conceding, increase slowly\n"
        "- If seller is conceding well, push harder (smaller increases)\n"
        "- If there is a summary of older rounds, use the trends to inform strategy\n"
        "- Read {seller_response} and adjust.\n"
        "- Walk away if seller won't go below $460,000\n\n"
        "Write your offer as a dollar amount with brief justification."
    ),
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                )
            )
        ),
    ],
    before_tool_callback=_enforce_buyer_allowlist,
    before_model_callback=_compress_memory,
    output_key="buyer_offer",
    before_agent_callback=_init_round_state,
)

seller = LlmAgent(
    name="seller",
    model=MODEL,
    instruction=(
        "You are an expert listing agent for 742 Evergreen Terrace, "
        "Austin, TX 78701 (listed at $485,000).\n\n"
        "PROPERTY HIGHLIGHTS:\n"
        "  • Kitchen renovated 2023 ($45k), new roof 2022 ($18k), HVAC 2021 ($12k)\n"
        "  • Total upgrades: $75,000+\n\n"
        "STRATEGY:\n"
        "- Call your MCP tools for market data, inventory, and your floor price\n"
        "- Start counter at $477,000\n"
        "- Drop ONLY $2k–$4k per round (move slowly to extend the negotiation)\n"
        "- NEVER go below your minimum (from get_minimum_acceptable_price)\n"
        "- If buyer offers at or above your minimum, accept immediately\n"
        "- Emphasize $75,000 in upgrades to justify premium pricing\n\n"
        "Read {buyer_offer}.\n"
        "IMPORTANT: After writing your response, you MUST call submit_decision "
        "with action='ACCEPT' or action='COUNTER' and the price."
    ),
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                )
            )
        ),
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_INVENTORY_SERVER],
                )
            )
        ),
        submit_decision,
    ],
    before_tool_callback=_enforce_seller_allowlist,
    output_key="seller_response",
    after_agent_callback=_accumulate_memory_and_check,
)

negotiation_round = SequentialAgent(name="round", sub_agents=[buyer, seller])

root_agent = LoopAgent(
    name="negotiation",
    description=(
        "Multi-round negotiation with memory compression. "
        "Runs up to 10 rounds with a tight price gap. "
        "The buyer's before_model_callback compresses old rounds "
        "into aggregate summaries to prevent context overflow."
    ),
    sub_agents=[negotiation_round],
    max_iterations=10,
)
