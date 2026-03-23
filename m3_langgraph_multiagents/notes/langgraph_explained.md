# LangGraph Explained
## Orchestrating Multi-Agent Workflows with State Machines

See also: [LangGraph vs Google ADK vs A2A](../../m4_adk_multiagents/notes/langgraph_adk_a2a_comparison.md) for a cross-framework comparison index.

---

## Table of Contents

1. [Why Orchestration Is Needed](#1-why-orchestration-is-needed)
2. [What LangGraph Is](#2-what-langgraph-is)
3. [Core Concepts: State, Nodes, Edges](#3-core-concepts-state-nodes-edges)
4. [Building Your First Graph](#4-building-your-first-graph)
5. [Conditional Routing](#5-conditional-routing)
6. [Shared State Design](#6-shared-state-design)
7. [Cycles and Loops](#7-cycles-and-loops)
8. [Persistence and Checkpointing](#8-persistence-and-checkpointing)
9. [Error Handling and Retry](#9-error-handling-and-retry)
10. [Our Negotiation Graph (Detailed)](#10-our-negotiation-graph-detailed)
11. [LangGraph vs Alternatives](#11-langgraph-vs-alternatives)
12. [Common Misconceptions](#12-common-misconceptions)

---

## 1. Why Orchestration Is Needed

### The Problem with Raw Agent Loops

When you build multi-agent systems, you quickly run into problems that raw Python loops can't solve cleanly:

```python
# The naive approach — what everyone tries first
async def run_negotiation():
    round = 0
    buyer_offer = 425000
    seller_counter = None

    while round < 5:
        # Call buyer LLM
        buyer_response = await call_openai(buyer_prompt)
        # Parse the response (what if it's malformed?)
        # What if the LLM says "I walk away" but doesn't set a flag?
        # How do we handle the state across rounds?
        # What if we need to pause and resume?
        # What if we need to add a mediator agent?
        # What if step 3 depends on a condition at step 1?

        seller_response = await call_openai(seller_prompt)
        round += 1

    # This doesn't scale. This becomes spaghetti code.
```

**Problems this code has**:
1. **No structured state** — variables scattered everywhere
2. **No clear routing** — what happens if buyer walks away in round 2?
3. **No persistence** — if the process crashes, you lose everything
4. **No observability** — hard to debug what happened in which step
5. **No extensibility** — adding a mediator agent means rewriting the loop
6. **No parallelism** — can't run buyer research and seller research concurrently

LangGraph solves all of these by modeling your agent workflow as a **directed graph**.

---

## 2. What LangGraph Is

LangGraph is a library built on top of LangChain that lets you build **stateful, cyclical multi-agent workflows** as graphs.

### Key Properties

| Property | Detail |
|---|---|
| **Built by** | LangChain team |
| **Underlying model** | Directed graph (nodes + edges) with shared state |
| **Supports cycles** | Yes (unlike DAGs) — enables agent loops |
| **State management** | Typed state with reducers |
| **Persistence** | Built-in checkpointing via checkpointers |
| **Streaming** | Stream tokens and events in real-time |
| **Human-in-loop** | Interrupt and resume at any node |
| **Multi-agent** | First-class support for multiple agents |

### The Mental Model

```
LangGraph Workflow = State Machine

State Machine Components:
  • States   → The shared data all nodes can read/write (NegotiationState)
  • Nodes    → The agents/functions that transform state (buyer_node, seller_node)
  • Edges    → The transitions between nodes (buyer → seller → check → buyer)
  • Guards   → Conditions that determine which edge to take (is_agreement_reached?)
```

Compare to a traffic system:
- **State** = current traffic conditions (speeds, queue lengths)
- **Nodes** = traffic lights (they take action)
- **Edges** = roads between intersections
- **Guards** = traffic sensors (determine which light turns green)

---

## 3. Core Concepts: State, Nodes, Edges

### State — The Shared Memory

State is the single source of truth that all nodes can read from and write to.

```python
from typing import TypedDict, Optional, Annotated
import operator

class NegotiationState(TypedDict):
    """
    The shared state for the entire negotiation workflow.
    Every node reads from this and returns updates to it.

    TypedDict is used instead of a class because LangGraph needs
    to understand the structure for serialization/checkpointing.
    """

    # Property being negotiated
    property_address: str
    listing_price: float

    # Agent constraints (immutable)
    buyer_budget: float
    seller_minimum: float

    # Current negotiation positions
    buyer_current_offer: float
    seller_current_counter: float

    # Progress tracking
    round_number: int
    max_rounds: int
    status: str  # "negotiating" | "agreed" | "deadlocked" | "buyer_walked"

    # Result
    agreed_price: Optional[float]

    # Conversation history (uses reducer to append, not overwrite)
    history: Annotated[list[dict], operator.add]

    # LLM conversation context (kept separate per agent)
    buyer_context: list[dict]   # OpenAI messages format for buyer LLM
    seller_context: list[dict]  # OpenAI messages format for seller LLM
```

#### Annotated Reducers

Notice `history: Annotated[list[dict], operator.add]`. This is a **reducer** — it tells LangGraph how to merge state updates from nodes.

```python
# WITHOUT reducer (default: last-write-wins)
history = []
node_1_update = {"history": ["msg_1"]}  # node 1 returns this
node_2_update = {"history": ["msg_2"]}  # node 2 returns this
# Result: history = ["msg_2"]  ← msg_1 was LOST!

# WITH reducer (operator.add = list concatenation)
history: Annotated[list, operator.add] = []
node_1_update = {"history": ["msg_1"]}
node_2_update = {"history": ["msg_2"]}
# Result: history = ["msg_1", "msg_2"]  ← both preserved!
```

### Nodes — The Processing Units

Nodes are **Python functions** (sync or async) that take the current state and return a partial update.

```python
async def buyer_node(state: NegotiationState) -> dict:
    """
    The buyer agent node.

    Contract:
    - INPUT: full NegotiationState
    - OUTPUT: dict with ONLY the fields this node changes
    - MUST NOT: mutate state directly
    - MUST: return a dictionary (partial state update)
    """
    # Read from state
    round_num = state["round_number"]
    seller_counter = state["seller_current_counter"]
    buyer_context = state["buyer_context"]

    # Do the agent's work
    new_offer, new_context, message = await call_buyer_llm(
        round_num=round_num,
        seller_counter=seller_counter,
        context=buyer_context,
        budget=state["buyer_budget"]
    )

    # Return ONLY what changed
    return {
        "buyer_current_offer": new_offer,
        "buyer_context": new_context,
        "round_number": round_num + 1,
        "history": [{"round": round_num, "from": "buyer", "offer": new_offer, "message": message}]
        #            ↑ This APPENDS to history (because of the reducer)
    }
```

**Critical rule**: Nodes return a **dictionary of updates**, not the full state. LangGraph merges this into the existing state automatically.

### Node Types Taxonomy

> From [LangGraph — Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph):
> *"Start by identifying the distinct steps in your process. Each step will become a node."*

Not all nodes are LLM calls. The docs identify four node types:

| Type | Purpose | Example in our workshop |
|---|---|---|
| **LLM step** | Understanding, reasoning, decisions | `buyer_node` — GPT-4o decides the offer price |
| **Data step** | Fetch external information | MCP tool call inside `call_pricing_mcp()` |
| **Action step** | External operations with side effects | Sending an A2A message |
| **User input step** | Human review / approval point | `interrupt()` for human-in-the-loop |

Finer-grained nodes (one type per node) provide:
- More frequent checkpoints — less re-execution on failure
- Isolated retry policies — can retry just the data step, not the LLM step
- Better observability — you can inspect state between every step
- Easier testing — each node is a pure function you can unit-test

In our workshop, `buyer_node` combines LLM + data + action into one node for simplicity. In production, you'd split these apart.

Implementation note (current repo): Module 3 runs in strict planner mode for MCP — the buyer/seller agents first call `list_tools()` to discover available tools from their MCP servers, then use GPT-4o to select which of those discovered tools to call for the turn. Only selected calls are executed (no automatic fallback tool calls). The tool list in the planner prompt is built dynamically from the server's live schemas, not hardcoded.

### Edges — The Connections

Edges define which node runs after the current one.

```python
# Simple edge — always goes to seller after buyer
workflow.add_edge("buyer", "seller")

# Conditional edge — the next node depends on state
workflow.add_conditional_edges(
    "seller",               # source node
    route_after_seller,     # function that decides next node
    {
        "continue": "buyer",      # if route returns "continue"
        "agreed": END,            # if route returns "agreed"
        "deadlocked": END,        # if route returns "deadlocked"
        "buyer_walked": END,      # if route returns "buyer_walked"
    }
)
```

---

## 4. Building Your First Graph

Here's the complete pattern for building a LangGraph workflow:

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

# Step 1: Define State
class SimpleState(TypedDict):
    count: int
    messages: list[str]

# Step 2: Define Nodes
def increment_node(state: SimpleState) -> dict:
    """Simple counter node."""
    return {
        "count": state["count"] + 1,
        "messages": [f"Count is now {state['count'] + 1}"]
    }

def check_node(state: SimpleState) -> dict:
    """Evaluation node — doesn't change state, just reads."""
    print(f"Current count: {state['count']}")
    return {}  # no state change

# Step 3: Define Router
def should_continue(state: SimpleState) -> str:
    """Decides next step based on state."""
    if state["count"] >= 5:
        return "done"
    return "continue"

# Step 4: Build the Graph
workflow = StateGraph(SimpleState)

# Add nodes
workflow.add_node("increment", increment_node)
workflow.add_node("check", check_node)

# Set entry point
workflow.set_entry_point("increment")

# Add edges
workflow.add_edge("increment", "check")
workflow.add_conditional_edges(
    "check",
    should_continue,
    {
        "continue": "increment",  # loop back
        "done": END               # terminate
    }
)

# Step 5: Compile the graph
graph = workflow.compile()

# Step 6: Run it
final_state = graph.invoke({"count": 0, "messages": []})
print(final_state)
# Output: {"count": 5, "messages": ["Count is now 1", ..., "Count is now 5"]}
```

### Visualizing the Graph

```python
# LangGraph can generate visual representations
print(graph.get_graph().draw_mermaid())
```

Output:
```
flowchart TD
    __start__ --> increment
    increment --> check
    check -->|continue| increment
    check -->|done| __end__
```

Which renders as:
```
START
  │
  ▼
INCREMENT ◄──────────┐
  │                  │
  ▼                  │
CHECK ── continue ───┘
  │
  └── done ──► END
```

---

## 5. Conditional Routing

Conditional routing is what makes LangGraph powerful — it allows the workflow to branch based on the current state.

### Router Function Pattern

```python
def route_after_seller(state: NegotiationState) -> str:
    """
    Router function — called after seller node runs.
    Returns a string key that maps to the next node.

    This function ONLY reads state — it makes no LLM calls.
    Routing decisions should be deterministic and fast.
    """

    # Check for terminal conditions first
    if state["status"] == "agreed":
        return "agreed"

    if state["status"] == "buyer_walked":
        return "buyer_walked"

    # Check round limit
    if state["round_number"] >= state["max_rounds"]:
        return "deadlocked"

    # Seller rejected the offer outright
    if state["status"] == "rejected":
        return "rejected"

    # Otherwise, continue negotiating
    return "continue"
```

### Complex Multi-Branch Routing

```python
def route_after_buyer(state: NegotiationState) -> str:
    """More complex routing with multiple conditions."""

    # Buyer walked away
    if state["buyer_current_offer"] == 0:
        return "buyer_walked"

    # Buyer accepted seller's last counter
    if (state.get("buyer_accepted_counter")
            and state["buyer_current_offer"] >= state["seller_current_counter"]):
        return "agreed"

    # Buyer went over budget (shouldn't happen, but guard against it)
    if state["buyer_current_offer"] > state["buyer_budget"]:
        return "buyer_walked"

    # Offer crossed seller's minimum — automatic agreement territory
    if state["buyer_current_offer"] >= state["seller_minimum"]:
        return "potential_agreement"

    # Continue normally
    return "continue"

# Register with multiple targets
workflow.add_conditional_edges(
    "buyer",
    route_after_buyer,
    {
        "continue": "seller",
        "agreed": "finalize",
        "buyer_walked": END,
        "potential_agreement": "fast_accept",  # shortcut node
    }
)
```

### Command Objects (Modern Routing Pattern)

> Source: [LangGraph — Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)

Modern LangGraph also supports **`Command` objects** — a newer pattern where nodes specify their own destination, rather than relying on external router functions. This makes control flow explicit and traceable inside node logic.

```python
from typing import Literal
from langgraph.types import Command

def classify_buyer_intent(state: NegotiationState) -> Command[Literal["make_offer", "walk_away", "request_info"]]:
    """
    Node that reads buyer intent and routes to the appropriate next node.
    The routing logic lives INSIDE the node — not in a separate router function.
    """
    # ... classify the buyer's intent ...
    if state["buyer_current_offer"] == 0:
        return Command(
            update={"status": "buyer_walked"},
            goto="walk_away"
        )
    elif state["round_number"] == 1:
        return Command(
            update={"status": "negotiating"},
            goto="make_offer"
        )
    else:
        return Command(
            update={"status": "negotiating"},
            goto="make_offer"
        )
```

**When to use `Command` vs `add_conditional_edges`:**

| Approach | Best for |
|---|---|
| `add_conditional_edges` | Routing logic based on state fields; router is reusable across multiple source nodes |
| `Command` object | Routing logic is specific to one node; makes the flow self-documenting |

Both provide the same termination guarantees — the graph still has a terminal `END` node with no outgoing edges.

---

## 6. Shared State Design

Designing state well is the most important architectural decision in a LangGraph workflow.

### State Design Principles

#### 1. Include Only What's Needed

```python
# BAD — too much in state
class BadState(TypedDict):
    full_mls_database: dict           # Don't put large data in state
    raw_llm_responses: list[str]      # Don't store everything
    debug_logs: list[str]             # Use logging instead

# GOOD — focused on what agents need
class GoodState(TypedDict):
    buyer_offer: float                # Specific numeric value
    seller_counter: float             # Specific numeric value
    round_number: int                 # Simple counter
    status: str                       # Finite set of values
    history: Annotated[list, operator.add]  # Accumulated messages
```

#### 2. Use Clear Status Fields

```python
from typing import Literal

# Use Literal for finite state machines
NegotiationStatus = Literal[
    "negotiating",    # Active negotiation in progress
    "agreed",         # Deal reached
    "deadlocked",     # Max rounds with no agreement
    "buyer_walked",   # Buyer withdrew
    "seller_rejected" # Seller rejected all offers
]

class NegotiationState(TypedDict):
    status: NegotiationStatus  # Always know where you are
```

#### 3. Separate Agent Memory from Shared State

```python
class NegotiationState(TypedDict):
    # SHARED — both agents and orchestrator see this
    round_number: int
    buyer_current_offer: float
    seller_current_counter: float
    status: str
    history: Annotated[list, operator.add]

    # PRIVATE — only buyer's LLM conversation context
    buyer_llm_messages: list[dict]

    # PRIVATE — only seller's LLM conversation context
    seller_llm_messages: list[dict]
```

---

## 7. Cycles and Loops

Unlike most workflow tools (which only support DAGs — Directed Acyclic Graphs), LangGraph explicitly supports **cycles**. This is the key feature that enables agent loops.

```
DAG (most workflow tools):        CYCLIC GRAPH (LangGraph):
──────────────────────────        ──────────────────────────────────
START → A → B → C → END          START → BUYER → SELLER → (check)
                                              ↑               │
Only moves forward                            └───────────────┘
                                     Can loop until condition met
```

### How to Create a Loop

```python
workflow = StateGraph(NegotiationState)

workflow.add_node("buyer", buyer_node)
workflow.add_node("seller", seller_node)
workflow.add_node("check_status", check_status_node)

workflow.set_entry_point("buyer")

workflow.add_edge("buyer", "seller")
workflow.add_edge("seller", "check_status")

# THIS CREATES THE LOOP:
workflow.add_conditional_edges(
    "check_status",
    should_continue_negotiation,
    {
        "continue": "buyer",   # ← loops back to buyer!
        "stop": END
    }
)
```

### Loop Guard — Preventing Infinite Loops

**Always have a termination condition**. In our case, `max_rounds = 5`:

```python
def should_continue_negotiation(state: NegotiationState) -> str:
    # Termination conditions (prevent infinite loops)
    if state["status"] != "negotiating":
        return "stop"

    if state["round_number"] >= state["max_rounds"]:
        return "stop"

    # Check if prices have converged
    gap = state["seller_current_counter"] - state["buyer_current_offer"]
    if gap <= 0:  # offers crossed — deal!
        return "stop"

    return "continue"
```

---

## 8. Persistence and Checkpointing

LangGraph can **save state** between node executions. This enables:
- Resume from where you left off after a crash
- Human-in-the-loop (pause, let a human review, resume)
- Time-travel debugging (replay from any checkpoint)

### Basic Checkpointing

```python
from langgraph.checkpoint.memory import MemorySaver

# In-memory checkpointer (for development)
checkpointer = MemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

# Run with a thread_id (enables resume)
config = {"configurable": {"thread_id": "negotiation_001"}}
result = graph.invoke(initial_state, config=config)

# Resume from checkpoint
result = graph.invoke(None, config=config)  # None = resume from last checkpoint
```

### Production Checkpointing

```python
from langgraph.checkpoint.postgres import PostgresSaver

# PostgreSQL checkpointer (for production)
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:pass@localhost/negotiation_db"
)
```

### Human-in-the-Loop

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["seller"]  # Pause BEFORE seller node runs
)

config = {"configurable": {"thread_id": "review_001"}}

# Run until the interrupt
state = graph.invoke(initial_state, config=config)
# Execution stops before seller_node
# Human can review buyer's offer here...

print(f"Buyer just offered: ${state['buyer_current_offer']:,.0f}")
approval = input("Approve? (y/n): ")

if approval == "y":
    # Resume execution
    final_state = graph.invoke(None, config=config)
```

---

## 9. Error Handling and Retry

### Error Categories — Who Handles What?

> From [LangGraph — Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph):
> Four distinct error types each require a different handling strategy:

| Error Type | Examples | Handler | Strategy |
|---|---|---|---|
| **Transient** | Network timeout, rate limit | System | Automatic retry with exponential backoff |
| **LLM-recoverable** | Tool call fails, bad JSON format | LLM | Store error in state, loop back with clearer prompt |
| **User-fixable** | Missing information, ambiguous intent | Human | Pause with `interrupt()`, wait for human input |
| **Unexpected** | Logic bug, assertion failure | Developer | Let it bubble up — don't silently swallow it |

The key insight: **don't retry everything the same way**. A rate limit error needs a different strategy than an LLM giving a malformed response.

In our negotiation simulator, the most common errors are:
- `openai.RateLimitError` → transient, retry with backoff
- `ValueError: bad JSON` → LLM-recoverable, retry with clearer prompt
- `buyer_offer > buyer_budget` → logic bug, let it surface as an error

Also from the docs: *"When combined with other operations in a node, `interrupt()` must come first"* — this prevents partial execution before the human checkpoint.

### Node-Level Error Handling

```python
async def buyer_node(state: NegotiationState) -> dict:
    """Buyer node with retry logic for LLM failures."""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await call_openai_with_timeout(
                messages=state["buyer_llm_messages"],
                timeout=30
            )
            return parse_buyer_response(response, state)

        except openai.RateLimitError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # exponential backoff
                continue
            raise

        except openai.APIError as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            # After max retries, mark negotiation as failed
            return {
                "status": "agent_error",
                "error_message": str(e)
            }

        except ValueError as e:
            # LLM returned malformed response
            if attempt < max_retries - 1:
                # Try again with a cleaner prompt
                state["buyer_llm_messages"].append({
                    "role": "user",
                    "content": "Please respond in valid JSON format only."
                })
                continue
            return {"status": "agent_error", "error_message": "Malformed LLM response"}
```

### Graph-Level Error Routing

```python
# Add an error handler node
async def error_handler_node(state: NegotiationState) -> dict:
    """Handles unexpected errors in the negotiation."""
    error = state.get("error_message", "Unknown error")
    print(f"❌ Negotiation failed: {error}")
    return {"status": "error", "agreed_price": None}

workflow.add_node("error_handler", error_handler_node)

# Route to error handler when things go wrong
def route_with_error_handling(state: NegotiationState) -> str:
    if state.get("status") == "agent_error":
        return "error"
    if state.get("round_number", 0) >= state.get("max_rounds", 5):
        return "deadlocked"
    if state.get("status") == "agreed":
        return "agreed"
    return "continue"
```

---

## 10. Our Negotiation Graph (Detailed)

This is the complete LangGraph workflow for our real estate negotiation simulator.

### State Definition

```python
class NegotiationState(TypedDict):
    # Property context
    property_address: str
    listing_price: float

    # Agent constraints
    buyer_budget: float
    seller_minimum: float

    # Current positions
    buyer_current_offer: float
    seller_current_counter: float

    # Tracking
    round_number: int
    max_rounds: int
    status: str

    # Result
    agreed_price: Optional[float]

    # History (appended by each round)
    history: Annotated[list[dict], operator.add]

    # Per-agent LLM context
    buyer_llm_messages: list[dict]
    seller_llm_messages: list[dict]
```

### Graph Topology

```
                    ┌─────────────────────────────────────┐
                    │         START                        │
                    │  (initial_state injected here)       │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │         BUYER NODE                   │
                    │                                      │
                    │  1. Reads seller's last counter      │
                    │  2. Queries MCP pricing server       │
                    │  3. Calls GPT-4o to decide offer     │
                    │  4. Updates buyer_current_offer      │
                    │  5. Appends to history               │
                    └──────────────┬──────────────────────┘
                                   │
                 ┌─────────────────┼──────────────────┐
                 │                 │                    │
           agreed          buyer_walked           continue
                 │                 │                    │
                 ▼                 ▼                    ▼
             AGREED ✅          DEADLOCK ❌        SELLER NODE
                                                        │
                                     ┌──────────────────┼──────────────┐
                                     │                  │               │
                                accepted           rejected         continue
                                     │                  │               │
                                     ▼                  ▼               │
                                  AGREED ✅          DEADLOCK ❌         │
                                                                         │
                                                           ┌─────────────┘
                                                           │
                                                     (if round < 5)
                                                           │
                                                           ▼
                                                      BUYER NODE ◄─── (loop)
                                                           │
                                                    (if round >= 5)
                                                           │
                                                           ▼
                                                      DEADLOCK ❌
```

### Complete Graph Code

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(NegotiationState)

# Add all nodes
workflow.add_node("buyer", buyer_node)
workflow.add_node("seller", seller_node)

# Entry point
workflow.set_entry_point("buyer")

# Buyer → Check → branch
workflow.add_conditional_edges(
    "buyer",
    route_after_buyer,
    {
        "to_seller": "seller",
        "agreed": END,
        "buyer_walked": END,
    }
)

# Seller → Check → branch
workflow.add_conditional_edges(
    "seller",
    route_after_seller,
    {
        "continue": "buyer",
        "agreed": END,
        "deadlocked": END,
        "rejected": END,
    }
)

# Compile
graph = workflow.compile()
```

See `m3_langgraph_multiagents/langgraph_flow.py` for the complete implementation.

---

## 11. LangGraph vs Alternatives

### Comparison Table

```
┌────────────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ Feature            │ LangGraph    │ Raw Python   │ Prefect      │ Temporal     │
├────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Cycles/loops       │ ✅ Native    │ ✅ Manual    │ ❌ No        │ ✅ Yes       │
│ Agent memory       │ ✅ Built-in  │ 🔶 DIY      │ ❌ No        │ ❌ No        │
│ Streaming          │ ✅ Yes       │ 🔶 DIY      │ ❌ Limited   │ ✅ Yes       │
│ Human-in-loop      │ ✅ Built-in  │ 🔶 DIY      │ 🔶 Via hooks │ ✅ Yes       │
│ Persistence        │ ✅ Multiple  │ 🔶 DIY      │ ✅ Built-in  │ ✅ Built-in  │
│ LLM integration    │ ✅ Native    │ 🔶 DIY      │ ❌ No        │ ❌ No        │
│ Learning curve     │ Medium       │ Low          │ Low          │ High         │
│ Production ready   │ ✅ Yes       │ 🔶 Depends  │ ✅ Yes       │ ✅ Yes       │
└────────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

### When to Choose LangGraph

✅ **Use LangGraph when**:
- Building multi-agent workflows with LLMs
- Need stateful loops that persist across turns
- Want human-in-the-loop capabilities
- Team is already using LangChain ecosystem

❌ **Don't use LangGraph when**:
- Simple single-agent tasks (just call the LLM directly)
- Pure data pipelines (use Prefect or Airflow)
- Non-AI orchestration (use Temporal or Celery)
- Team has no Python experience

---

## 12. Common Misconceptions

### ❌ "LangGraph is for DAGs only"

**Reality**: LangGraph explicitly supports cycles. This is its key differentiator from most workflow tools.

### ❌ "Each node runs its own LLM"

**Reality**: Nodes are just Python functions. They CAN call LLMs, but they can also call APIs, read files, do math — or do nothing. Not every node needs an LLM.

### ❌ "State is like a database"

**Reality**: State is an in-memory dict that lives for the duration of one graph execution. It's not persistent unless you add a checkpointer. Think of it like a function's local variables, not a database.

### ❌ "LangGraph manages the LLM conversation"

**Reality**: LangGraph manages the WORKFLOW state. You still manage LLM conversation history (the messages array) yourself within the state object and within your node functions.

### ❌ "Conditional edges are like if-statements"

**Reality**: Conditional edges are more like router functions in a state machine. They don't execute business logic — they just read state and return a string key indicating the next node. Keep them pure and fast.

---

## Summary

| Concept | Key Takeaway |
|---|---|
| **Why LangGraph** | Structured state, cycles, persistence, extensibility |
| **State** | TypedDict shared across all nodes; use reducers for accumulation |
| **Nodes** | Python functions that take full state, return partial updates |
| **Edges** | Simple (always) or conditional (route based on state) |
| **Cycles** | The key feature — enables agent loops with termination guards |
| **Checkpointing** | Persist state for resume, human-in-loop, debugging |
| **Error handling** | Retry in nodes, error routing in edges |
| **vs alternatives** | Best for LLM-powered cyclic multi-agent workflows |

---

*← [A2A Protocols](../../m4_adk_multiagents/notes/a2a_protocols.md)*
*→ [Google ADK Overview](../../m4_adk_multiagents/notes/google_adk_overview.md)*
