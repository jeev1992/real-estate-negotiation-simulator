# Module 3 — LangGraph Multi-Agent Workflow (`m3_langgraph_multiagents`)

**Requires:** `OPENAI_API_KEY`

This is the first version of the negotiation that actually *works end-to-end*: real LLM agents, real MCP data, real negotiation logic, all connected by a LangGraph workflow.

---

## What this module teaches

In Module 1 we had a `while True` loop with no structure. In Module 2 we had MCP tools but no agents to use them.

Module 3 brings it all together:

| What | How |
|---|---|
| Structured turn-taking | LangGraph `StateGraph` — not a manual loop |
| Typed messages between agents | `TypedDict` with explicit `price`, `message_type`, `conditions` fields |
| Real market data for every offer | MCP calls to `pricing_server.py` and `inventory_server.py` |
| Termination guarantee | Conditional edges route to `END` when a deal is reached or rounds run out |
| Observability | Full message history in LangGraph state — you can see every round |

---

## File breakdown

### `negotiation_types.py` — The message contract

Before any agents run, this file defines what a negotiation message *is*. Both the buyer and seller speak this format.

```python
NegotiationMessage = TypedDict("NegotiationMessage", {
    "message_type": str,      # "offer", "counter_offer", "acceptance", "withdrawal"
    "price": float,           # always a number, never a string
    "message": str,           # human-readable explanation
    "conditions": list,       # e.g. ["45-day close", "inspection contingency"]
    "closing_timeline_days": int,
})
```

This is what fixes failure modes #1, #2, and #5 from Module 1: no more raw strings, no more regex on free-form text. Every message has a price field — no ambiguity about which number is the offer.

**Factory functions** make it easy to create valid messages:

```python
create_offer(session_id, round_num, price, message, conditions)
create_counter_offer(...)
create_acceptance(...)
create_withdrawal(...)
```

### `buyer_simple.py` — Buyer agent (GPT-4o)

The buyer's job: start below asking price and negotiate up only as far as necessary, staying under budget ($460,000).

**How it works each round:**
1. On first call, discovers available tools via `list_tools()` on the pricing MCP server
2. GPT-4o acts as a planner — decides which discovered tools to call this turn
3. Calls `get_market_price` and/or `calculate_discount` from `pricing_server.py`
4. GPT-4o uses that data to decide on a price and write a justification
5. Returns a `NegotiationMessage` dict for LangGraph state

The buyer never connects to `inventory_server.py` — it doesn't know the seller's floor price.

### `seller_simple.py` — Seller agent (GPT-4o)

The seller's job: start at asking price and come down only as far as their minimum ($445,000).

**How it differs from the buyer:**
- Connects to **both** `pricing_server.py` and `inventory_server.py`
- Uses `get_minimum_acceptable_price` to set a hard floor — any offer above it gets accepted immediately without calling GPT-4o
- The floor enforcement is hardcoded: the LLM cannot override it

This is the information asymmetry from Module 2 in action: the seller knows their floor; the buyer has to figure it out through negotiation.

### `langgraph_flow.py` — The negotiation graph

This is where LangGraph comes in. Instead of a `while True` loop, the negotiation is a **directed graph**:

```
START
  |
  v
init (set up state)
  |
  v
buyer_node (buyer takes a turn)
  |
  +-- offer was accepted or withdrawn? --> END
  |
  v
seller_node (seller responds)
  |
  +-- seller accepted or max rounds? --> END
  |
  v
buyer_node (loop back)
```

**The LangGraph state:**

```python
class NegotiationState(TypedDict):
    history: Annotated[list[dict], operator.add]   # all messages, auto-appended
    status: str                                     # "negotiating", "agreed", "failed"
    agreed_price: float
    current_round: int
    max_rounds: int
```

The `Annotated[list, operator.add]` reducer means each node just returns new messages — LangGraph automatically appends them to history. No node needs to read the old list and write a new one.

**Conditional edges** replace the `if/elif` chain you'd write manually:

```python
graph.add_conditional_edges("buyer", route_after_buyer, {
    "to_seller": "seller",
    "end": END,
})
```

---

## How to run

```bash
# Full negotiation (needs OPENAI_API_KEY)
python m3_langgraph_multiagents/main_langgraph_multiagent.py

# Options
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 3     # fewer rounds
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 5     # default
```

**What to expect:**
- Both agents start up and connect to MCP servers
- You'll see each round printed: buyer offer, seller counter, prices converging
- Final result: AGREED at some price, or DEADLOCKED if max rounds hit
- The buyer should land somewhere between $425K (start) and $460K (budget)
- The seller should hold above $445K (floor)

---

## Exercises

| Exercise | Difficulty | Task |
|---|---|---|
| `ex01_trace_graph_flow.md` | `[Core]` | Add a deadlock-breaker conditional edge that detects stale prices and ends early |
| `ex02_run_two_rounds.md` | `[Core]` | Add automatic convergence accept — if offers are within 2%, agree at midpoint |
| `ex03_stretch_state_persistence.md` | `[Stretch]` | Add SQLite-based state persistence so negotiations can be paused and resumed |
| `ex04_capstone_inspector_agent.md` | `[Stretch]` | **Capstone**: Add an inspector agent with a new MCP server and LangGraph node — ties all modules together |

Solutions are in `m3_langgraph_multiagents/solution/`. Each exercise includes a reflection question.

---

## Quick mental model
- If you want to see buyer/seller decision logic, open `buyer_simple.py` or `seller_simple.py`.
- If you want to see how the turn loop works, open `langgraph_flow.py` and look at the graph edges.
- The MCP servers (`m2_mcp/pricing_server.py` + `m2_mcp/inventory_server.py`) are started automatically — you don't need to run them separately.

---

## How Module 3 compares to Module 1

| | Module 1 | Module 3 |
|---|---|---|
| Turn control | `while True` | LangGraph `StateGraph` |
| Messages | Raw strings | `TypedDict` with typed fields |
| Prices | Hardcoded | MCP tools (`get_market_price`) |
| Termination | Emergency exit at 100 turns | Conditional edge to `END` |
| Observability | None | Full history in LangGraph state |
| LLM | None | GPT-4o (buyer + seller) |
