# A2A Protocols
## Agent-to-Agent Communication: How Agents Talk to Each Other

---

## Table of Contents

1. [What A2A Actually Means](#1-what-a2a-actually-means)
2. [A2A vs MCP — The Critical Distinction](#2-a2a-vs-mcp--the-critical-distinction)
3. [Why No Universal Standard Yet](#3-why-no-universal-standard-yet)
4. [Message Schema Design Principles](#4-message-schema-design-principles)
5. [Our Real Estate A2A Protocol](#5-our-real-estate-a2a-protocol)
6. [Message Types and the Negotiation State Machine](#6-message-types-and-the-negotiation-state-machine)
7. [A2A Transport Options](#7-a2a-transport-options)
8. [Error Handling in A2A Communication](#8-error-handling-in-a2a-communication)
9. [Implementing A2A in Python](#9-implementing-a2a-in-python)
    - [Google ADK A2A Demo in This Repo](#91-google-adk-a2a-demo-in-this-repo)
10. [Production A2A Patterns](#10-production-a2a-patterns)
11. [Common Misconceptions](#11-common-misconceptions)

---

## 1. What A2A Actually Means

**A2A (Agent-to-Agent)** refers to any communication pattern where autonomous AI agents interact directly with each other — exchanging information, delegating tasks, negotiating, or coordinating.

Think of it like this:

```
HUMAN-TO-AI (H2A):
  You: "Search for Python real estate repos"
  Claude: "Here are 5 repos I found..."

API-TO-AI (Tool Call via MCP):
  Agent: get_market_price("742 Evergreen Terrace...")
  MCP Server: {"list_price": 485000, "estimated_value": 462000}

AGENT-TO-AGENT (A2A):
  Buyer Agent: "I offer $425,000 for the property at 742 Evergreen Terrace"
  Seller Agent: "I counter at $477,000. The kitchen was renovated in 2023."
  Buyer Agent: "Acknowledged. I increase my offer to $438,000..."
```

The key distinguishing features of A2A:
- **Both sides are autonomous AI agents** (not humans, not APIs)
- **Both sides maintain state and goals** across multiple exchanges
- **Messages carry context and intent**, not just data
- **Either side can initiate**, reject, or terminate the conversation

### The Phone Call Analogy

Think of MCP like checking a website for information (one-way, you request, server responds).
Think of A2A like a phone call between two people who both have goals and can say anything at any time.

```
MCP (website):              A2A (phone call):
───────────────────         ───────────────────────────────────────
You: GET /price             Buyer: "I'm offering $425K"
Server: {price: 485000}     Seller: "That's too low. $477K?"
                            Buyer: "Based on comps I've pulled, $438K"
Done. One request.          Seller: "I can do $465K if you close in 30 days"
                            Buyer: "Deal at $458K with 45-day close"
                            Seller: "Agreed."
                            [continues until agreement or deadlock]
```

---

## 2. A2A vs MCP — The Critical Distinction

This is one of the most common sources of confusion among new AI engineers.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MCP = Agent ↔ External System (Tools, Data, APIs)                     │
│                                                                         │
│  A2A = Agent ↔ Agent (Autonomous Peers Communicating)                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Side-by-Side Comparison

```
Feature              MCP                           A2A
────────────────     ──────────────────────────    ──────────────────────────────
Parties              Agent + Tool Server           Agent + Agent
Intelligence         One side (agent)              Both sides (both are agents)
Protocol             Standardized (MCP spec)       Custom (no standard yet)
State                Stateless per call            Stateful conversation
Initiated by         Always the agent/client       Either agent can initiate
Response format      Defined by MCP protocol       Agreed upon by both agents
Purpose              Access external data/tools    Coordinate, negotiate, delegate
Example              Agent → get stock price       Buyer ↔ Seller negotiation
```

### They Work Together

In our negotiation simulator, BOTH are used simultaneously:

```
                    ┌──────────────────────────────────┐
                    │     NEGOTIATION SESSION          │
                    └──────────────────────────────────┘

BUYER AGENT ─────────────────────────────────────────── SELLER AGENT
    │                     A2A                               │
    │        {"type": "OFFER", "price": 425000}             │
    │ ─────────────────────────────────────────────────►    │
    │                                                        │
    │        {"type": "COUNTER", "price": 477000}           │
    │ ◄─────────────────────────────────────────────────    │
    │                                                        │
    │ MCP                                                MCP │
    ▼                                                        ▼
PRICING                                               PRICING + INVENTORY
SERVER                                                SERVERS
(get_market_price)                                    (get_inventory_level,
                                                       get_minimum_price)
```

The buyer uses **MCP** to get market data, then uses **A2A** to make an offer to the seller. The seller uses **MCP** to get inventory data, then uses **A2A** to counter. MCP and A2A are complementary, not competing.

---

## 3. Why No Universal Standard Yet

As of 2025, there is no single dominant A2A standard (though Google announced an "Agent2Agent Protocol" specification in early 2025). Here's why this space is still evolving:

### The Challenge

```
Problem 1: What do agents need to communicate?
  ─────────────────────────────────────────────
  Simple case: "Here is my offer price"
  Complex case: "I'm delegating the financial analysis subtask to you.
                 Here's the full context, here are the tools you have access to,
                 here's what I need back, here's the deadline, here's how to
                 report errors, here's the priority level..."

Problem 2: How much state to share?
  ──────────────────────────────────
  • Just the message? (lightweight, loses context)
  • Full conversation history? (context-rich, expensive)
  • Shared memory/state object? (powerful, complex)

Problem 3: Trust and verification
  ─────────────────────────────────
  How does Agent B know Agent A is legitimate?
  How does Agent A know Agent B executed the task faithfully?

Problem 4: Discovery
  ─────────────────────
  How does Agent A know Agent B exists?
  How does Agent A know Agent B's capabilities?
```

### Current State (2025)

| Approach | Status | Used By |
|---|---|---|
| Custom JSON schemas | Most common today | Our workshop, most real projects |
| LangGraph messaging | Growing | LangGraph multi-agent apps |
| Google A2A Protocol | New (2025) | Google ADK ecosystem |
| OpenAI Swarm patterns | Experimental | OpenAI ecosystem |
| Human-readable text | Simple cases | Direct LLM conversation |

**Our approach**: We implement a **custom JSON schema** that's simple enough to understand in a workshop, but structured enough to demonstrate real patterns. This is the most common real-world approach as of 2025.

---

## 4. Message Schema Design Principles

When designing your A2A message schema, follow these principles:

### Principle 1: Include Identity

Every message must clearly identify who sent it and who it's for.

```python
{
    "from_agent": "buyer_agent",   # who sent this
    "to_agent": "seller_agent",    # who should receive it
    "session_id": "neg_001",       # which negotiation session
    "message_id": "msg_007",       # unique ID for deduplication
}
```

### Principle 2: Include Temporal Context

Agents need to know where they are in a conversation.

```python
{
    "round": 3,                           # negotiation round number
    "timestamp": "2025-01-15T10:30:00Z",  # when it was sent
    "in_reply_to": "msg_006",             # which message this responds to
}
```

### Principle 3: Use Intent-Typed Messages

Don't just send raw text. Categorize the message intent so agents can route it correctly without LLM parsing.

```python
{
    "message_type": "COUNTER_OFFER",  # one of: OFFER, COUNTER_OFFER, ACCEPT, REJECT, WITHDRAW, INFO
}
```

### Principle 4: Separate Payload from Metadata

Keep the "what" (payload) separate from the "how/who/when" (metadata).

```python
{
    # Metadata (for routing and tracking)
    "message_id": "msg_007",
    "from_agent": "seller",
    "to_agent": "buyer",
    "message_type": "COUNTER_OFFER",
    "round": 3,

    # Payload (the actual content)
    "payload": {
        "price": 465000,
        "conditions": ["Close within 30 days", "As-is condition"],
        "message": "Based on the 2023 kitchen renovation, $465K is fair.",
        "expiry_rounds": 2   # this offer expires in 2 rounds
    }
}
```

### Principle 5: Include Human-Readable Context

The LLM on the other side needs to understand the message. Include explanatory text alongside structured data.

```python
"payload": {
    "price": 465000,
    "message": "We're willing to come down to $465,000. The property was recently renovated with $45K in upgrades including a new kitchen, roof (2022), and HVAC. This is our best offer given the market conditions."
    # ↑ This is what the other agent's LLM reads and reasons about
}
```

---

## 5. Our Real Estate A2A Protocol

### Complete Message Schema

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
import uuid

MessageType = Literal[
    "OFFER",          # Buyer makes initial or updated offer
    "COUNTER_OFFER",  # Seller responds with counter-offer
    "ACCEPT",         # Either party accepts current offer
    "REJECT",         # Either party rejects and exits negotiation
    "WITHDRAW",       # Buyer withdraws their offer (walk-away)
    "INFO_REQUEST",   # Agent requests more information
    "INFO_RESPONSE",  # Agent provides requested information
]

class NegotiationPayload(BaseModel):
    """The actual negotiation content."""
    price: Optional[float] = None          # Offer/counter price in USD
    conditions: list[str] = []             # ["Contingent on inspection", ...]
    message: str                           # Human-readable explanation from agent
    closing_timeline_days: Optional[int] = None  # Proposed closing timeline
    concessions: list[str] = []            # ["Seller pays closing costs", ...]
    expiry_rounds: Optional[int] = None    # How many rounds until this offer expires

class A2AMessage(BaseModel):
    """A2A message between negotiation agents."""
    # Identity
    message_id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}")
    session_id: str                        # Identifies this negotiation session
    from_agent: Literal["buyer", "seller"]
    to_agent: Literal["buyer", "seller"]

    # Temporal context
    round: int
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    in_reply_to: Optional[str] = None     # message_id of the message being replied to

    # Intent
    message_type: MessageType

    # Content
    payload: NegotiationPayload
```

### Example Message Exchange

```python
# Round 1: Buyer makes initial offer
offer_1 = A2AMessage(
    session_id="neg_austin_742",
    from_agent="buyer",
    to_agent="seller",
    round=1,
    message_type="OFFER",
    payload=NegotiationPayload(
        price=425000,
        conditions=["Contingent on home inspection", "Financing contingency (30 days)"],
        closing_timeline_days=45,
        message=(
            "We've analyzed recent comparable sales in the 78701 zip code. "
            "The average comp price is $462,000, suggesting the property is "
            "listed approximately 4.9% above market value. We offer $425,000 "
            "which reflects this analysis along with the property's age (2005). "
            "We're serious buyers with pre-approval in hand."
        )
    )
)

# Round 1: Seller counters
counter_1 = A2AMessage(
    session_id="neg_austin_742",
    from_agent="seller",
    to_agent="buyer",
    round=1,
    in_reply_to=offer_1.message_id,
    message_type="COUNTER_OFFER",
    payload=NegotiationPayload(
        price=477000,
        conditions=["As-is sale (no repairs)", "Closing within 30 days"],
        closing_timeline_days=30,
        message=(
            "Thank you for your offer. However, $425,000 significantly undervalues "
            "this property. The kitchen was fully renovated in 2023 ($45,000 upgrade), "
            "and the roof was replaced in 2022. Current inventory in 78701 shows "
            "only 2.1 months of supply — a seller's market. We counter at $477,000, "
            "which we believe is fair given these improvements."
        )
    )
)

# Round 2: Buyer increases
offer_2 = A2AMessage(
    session_id="neg_austin_742",
    from_agent="buyer",
    to_agent="seller",
    round=2,
    in_reply_to=counter_1.message_id,
    message_type="OFFER",
    payload=NegotiationPayload(
        price=438000,
        conditions=["Contingent on inspection", "Financing contingency (21 days)"],
        closing_timeline_days=40,
        message=(
            "We acknowledge the renovations add value. Adjusting our offer to $438,000, "
            "which is $7,000 above the average comp and reflects the kitchen upgrade. "
            "We've shortened our financing contingency to 21 days to make this more "
            "attractive. We're willing to be flexible on closing date."
        )
    )
)

# Agreement reached!
acceptance = A2AMessage(
    session_id="neg_austin_742",
    from_agent="seller",
    to_agent="buyer",
    round=4,
    in_reply_to="msg_previous",
    message_type="ACCEPT",
    payload=NegotiationPayload(
        price=452000,
        conditions=["Standard inspection", "30-day financing"],
        closing_timeline_days=35,
        message="We accept $452,000. Congratulations, we have a deal!"
    )
)
```

---

## 6. Message Types and the Negotiation State Machine

A2A conversations need a **state machine** to track what messages are valid at each point.

### State Machine Diagram

```
                        START
                          │
                          ▼
                    ┌──────────┐
                    │  BUYER   │ ── sends OFFER ──►
                    │  THINKS  │
                    └──────────┘
                                         │
                                         ▼
                                   ┌──────────┐
                                   │  SELLER  │
                                   │  THINKS  │
                                   └──────────┘
                                         │
                          ┌──────────────┼──────────────────┐
                          │              │                    │
                          ▼              ▼                    ▼
                   COUNTER_OFFER      ACCEPT               REJECT
                          │              │                    │
                          ▼              ▼                    ▼
                    ┌──────────┐   ┌──────────┐        ┌──────────┐
                    │  BUYER   │   │ AGREED   │        │  DEAL    │
                    │  THINKS  │   │ 🎉 DONE  │        │  DEAD    │
                    └──────────┘   └──────────┘        └──────────┘
                          │
              ┌───────────┼───────────────┐
              │           │               │
              ▼           ▼               ▼
          NEW OFFER    ACCEPT          WITHDRAW
              │           │               │
              ▼           ▼               ▼
         (continue)   AGREED 🎉       DEAL DEAD ❌
              │
         (if round >= 5)
              │
              ▼
          DEADLOCK ⏱️
```

### Valid Message Transitions

```python
VALID_RESPONSES: dict[MessageType, list[MessageType]] = {
    "OFFER": ["COUNTER_OFFER", "ACCEPT", "REJECT"],
    "COUNTER_OFFER": ["OFFER", "ACCEPT", "REJECT", "WITHDRAW"],
    "ACCEPT": [],                    # Terminal state
    "REJECT": [],                    # Terminal state
    "WITHDRAW": [],                  # Terminal state
    "INFO_REQUEST": ["INFO_RESPONSE"],
    "INFO_RESPONSE": ["OFFER", "COUNTER_OFFER", "ACCEPT"],
}

TERMINAL_STATES = {"ACCEPT", "REJECT", "WITHDRAW"}
```

### State Machine Implementation

```python
class NegotiationStateMachine:
    """
    Enforces valid A2A message sequences in the negotiation.
    Prevents agents from sending invalid messages (e.g., accepting
    before any offer has been made).
    """

    def __init__(self, max_rounds: int = 5):
        self.current_round = 0
        self.max_rounds = max_rounds
        self.last_message_type: Optional[MessageType] = None
        self.is_terminal = False

    def validate_message(self, message: A2AMessage) -> tuple[bool, str]:
        """Returns (is_valid, reason_if_invalid)."""

        if self.is_terminal:
            return False, "Negotiation has already concluded"

        if self.current_round >= self.max_rounds and message.message_type not in TERMINAL_STATES:
            return False, f"Maximum rounds ({self.max_rounds}) reached. Only terminal messages allowed."

        if self.last_message_type is not None:
            valid_next = VALID_RESPONSES.get(self.last_message_type, [])
            if message.message_type not in valid_next:
                return False, (
                    f"Cannot send {message.message_type} after {self.last_message_type}. "
                    f"Valid responses: {valid_next}"
                )

        return True, "Valid"

    def record_message(self, message: A2AMessage) -> None:
        """Update state after a valid message is sent."""
        self.last_message_type = message.message_type
        if message.from_agent == "buyer":
            self.current_round += 1
        if message.message_type in TERMINAL_STATES:
            self.is_terminal = True
```

### Why the Naive Approach Breaks: The while True Problem

Before you saw the state machine above, you probably would have written the negotiation loop like this:

```python
# FROM m1_baseline/naive_negotiation.py — DO NOT DO THIS

while True:
    response = seller.respond_to_offer(buyer_message)
    if "DEAL" in response.upper():   # Fragile: "DEAL-breaker" also matches!
        break
    if "REJECT" in response.upper():
        break
    if turn > 100:                   # Emergency exit, not a guarantee
        break
```

**Three problems in 8 lines:**

1. **String matching for termination** — `"DEAL"` matches "DEAL-breaker", "DEAL with it", etc. You're relying on the LLM to spell a specific word correctly every time.

2. **No guarantee** — if the buyer max price < seller min price, agents negotiate *forever* (until turn 100). This wastes tokens and money.

3. **Emergency exit is a band-aid** — "stop at 100 turns" is not a proof of termination, it's an arbitrary cutoff.

### The FSM Solution: Termination By Design

`m1_baseline/state_machine.py` solves this with explicit terminal states:

```python
# FROM m1_baseline/state_machine.py — the correct approach

class NegotiationFSM:
    TRANSITIONS = {
        NegotiationState.IDLE:        {NegotiationState.NEGOTIATING, NegotiationState.FAILED},
        NegotiationState.NEGOTIATING: {NegotiationState.NEGOTIATING, NegotiationState.AGREED, NegotiationState.FAILED},
        NegotiationState.AGREED:      set(),    # ← TERMINAL: no outgoing transitions
        NegotiationState.FAILED:      set(),    # ← TERMINAL: no outgoing transitions
    }
```

**The guarantee:** `AGREED` and `FAILED` have **empty transition sets**. There is no code path that can exit a terminal state — not even a bug. The loop becomes:

```python
# Clean, guaranteed loop
fsm = NegotiationFSM(max_turns=5)
fsm.start()

while not fsm.is_terminal():
    if not fsm.process_turn():  # Auto-transitions to FAILED at max_turns
        break
    # ... run agents
```

### Progression: FSM → LangGraph

```
m1_baseline/state_machine.py          m3_langgraph_multiagents/langgraph_flow.py
───────────────────────────        ─────────────────────────────────────
NegotiationFSM                     StateGraph(NegotiationState)
  .state = NEGOTIATING               route_after_seller()
  .process_turn()                    → "continue" | "end"
  AGREED/FAILED = terminal           END node = terminal
  max_turns check                    max_rounds conditional edge

Guarantees termination              Guarantees termination
at agent level                      at workflow level
```

LangGraph **is** a state machine — but for entire multi-step workflows with conditional routing, parallel execution, and checkpointing. The same termination principle applies: the `END` node has no outgoing edges.

**Run the baseline to see both sides:**
```bash
python m1_baseline/naive_negotiation.py   # ← See the while True problem
python m1_baseline/state_machine.py       # ← See the FSM fix
python m3_langgraph_multiagents/main_langgraph_multiagent.py                  # ← See LangGraph apply the same principle at scale
```

---

## 7. A2A Transport Options

How do agents physically exchange messages? Several options depending on your architecture.

### Option 1: In-Process (Simplest — Our Simple Version)

```python
# Both agents live in the same Python process
# LangGraph passes messages through shared state
# No network, no serialization overhead

class NegotiationState(TypedDict):
    buyer_message: Optional[A2AMessage]   # buyer → seller
    seller_message: Optional[A2AMessage]  # seller → buyer
    history: list[A2AMessage]

# In LangGraph nodes, agents "receive" messages from state
def buyer_node(state: NegotiationState) -> dict:
    last_seller_msg = state.get("seller_message")  # Read seller's A2A message
    # ... reason and respond
    new_offer = create_offer(...)
    return {"buyer_message": new_offer}  # Write buyer's A2A message
```

**Best for**: Single-process simulations, workshops, testing.

### Option 2: HTTP/REST (Microservices)

```python
# Each agent runs as a FastAPI service
# Agents call each other's REST endpoints

# buyer service
@app.post("/receive_counter_offer")
async def receive_counter(message: A2AMessage) -> A2AMessage:
    # Agent processes the counter offer
    new_offer = await buyer_agent.decide_response(message)
    return new_offer

# seller service (sending to buyer)
response = requests.post(
    "http://buyer-agent:8000/receive_counter_offer",
    json=counter_offer.dict()
)
```

**Best for**: Microservice architectures, separate agent teams, horizontal scaling.

### Option 3: Message Queue (Production)

```python
# Agents publish to and subscribe from message queues
# Decoupled, reliable, supports retry

import asyncio
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

# Buyer publishes offers
async def send_offer(offer: A2AMessage):
    producer = AIOKafkaProducer(bootstrap_servers="kafka:9092")
    await producer.start()
    await producer.send("negotiation.offers", offer.json().encode())
    await producer.stop()

# Seller subscribes to offers
async def listen_for_offers():
    consumer = AIOKafkaConsumer("negotiation.offers", bootstrap_servers="kafka:9092")
    async for msg in consumer:
        offer = A2AMessage.parse_raw(msg.value)
        response = await seller_agent.respond(offer)
        await send_counter(response)
```

**Best for**: Production systems, high volume, fault tolerance requirements.

---

## 8. Error Handling in A2A Communication

A2A communication can fail in ways that direct API calls don't. Plan for:

### Error Categories

```
1. MESSAGE VALIDATION ERRORS
   Agent sent an invalid message (wrong type for this state,
   missing required fields, invalid price)
   → Response: Send ERROR message with explanation

2. AGENT REASONING ERRORS
   LLM failed to generate a valid structured response
   (hallucinated wrong format, token limit hit)
   → Response: Retry with simpler prompt, or report failure

3. COMMUNICATION FAILURES
   Network error, timeout, agent crashed
   → Response: Retry with exponential backoff, or deadlock

4. NEGOTIATION DEADLOCK
   Max rounds reached with no agreement
   → Response: Terminal DEADLOCK state, report to orchestrator

5. INVALID NEGOTIATION MOVE
   Agent tries to accept when it shouldn't, or offers above budget
   → Response: Override or reject the move at orchestrator level
```

### Error Message Schema

```python
class ErrorPayload(BaseModel):
    error_code: str          # "INVALID_OFFER" | "AGENT_FAILURE" | "TIMEOUT"
    error_message: str       # Human-readable explanation
    recoverable: bool        # Can the negotiation continue?
    suggested_action: str    # What the other party should do

# Example
error_msg = A2AMessage(
    session_id="neg_001",
    from_agent="buyer",
    to_agent="seller",
    round=3,
    message_type="INFO",
    payload=NegotiationPayload(
        message="ERROR: Our financing fell through. We need to pause negotiations."
    )
)
```

---

## 9. Implementing A2A in Python

For Module 3 message structure, see `m3_langgraph_multiagents/negotiation_types.py`.
For true protocol transport, see Module 4 (`m4_adk_multiagents/a2a_protocol_*`).
Here's the core in-process routing pattern for learning:

### Message Router

```python
class A2AMessageBus:
    """
    Simple in-process message bus for A2A communication.
    In production, this would be replaced by HTTP endpoints or a message queue.
    """

    def __init__(self):
        self._queues: dict[str, list[A2AMessage]] = {
            "buyer": [],
            "seller": []
        }
        self.history: list[A2AMessage] = []

    def send(self, message: A2AMessage) -> None:
        """Route a message to the recipient agent's queue."""
        # Validate message
        is_valid, reason = validate_message(message)
        if not is_valid:
            raise ValueError(f"Invalid A2A message: {reason}")

        # Route to recipient
        self._queues[message.to_agent].append(message)
        self.history.append(message)

    def receive(self, agent_name: str) -> Optional[A2AMessage]:
        """Get next message for an agent. Returns None if queue is empty."""
        queue = self._queues.get(agent_name, [])
        if queue:
            return queue.pop(0)
        return None

    def has_messages(self, agent_name: str) -> bool:
        """Check if agent has pending messages."""
        return len(self._queues.get(agent_name, [])) > 0
```

### Using the Message Bus

```python
async def run_negotiation():
    bus = A2AMessageBus()
    buyer = BuyerAgent(budget=460000)
    seller = SellerAgent(minimum_price=445000)

    # Buyer makes first move
    initial_offer = await buyer.make_initial_offer()
    bus.send(initial_offer)

    for round_num in range(1, 6):  # max 5 rounds
        # Seller receives and responds
        buyer_message = bus.receive("seller")
        if buyer_message.message_type in ["ACCEPT", "REJECT", "WITHDRAW"]:
            break

        seller_response = await seller.respond(buyer_message)
        bus.send(seller_response)

        if seller_response.message_type in ["ACCEPT", "REJECT"]:
            break

        # Buyer receives and responds
        seller_message = bus.receive("buyer")
        buyer_response = await buyer.respond(seller_message)
        bus.send(buyer_response)

    return bus.history
```

### 9.1 Google ADK True A2A Demo in This Repo

If you want the **Google ADK true protocol A2A** version in this repo, run:

```bash
python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102
python m4_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 5
python m4_adk_multiagents/a2a_protocol_buyer_client_demo.py --seller-url http://127.0.0.1:9102
```

What this demonstrates:
- Buyer and seller are both ADK `LlmAgent`-based agents
- Communication happens over networked A2A JSON-RPC transport
- Seller endpoint publishes an A2A agent card for discovery

Key files:
- `m4_adk_multiagents/a2a_protocol_seller_server.py` (A2A protocol seller endpoint)
- `m4_adk_multiagents/a2a_protocol_http_orchestrator.py` (A2A protocol multi-round HTTP orchestrator)
- `m4_adk_multiagents/a2a_protocol_buyer_client_demo.py` (A2A protocol buyer client)
- `m4_adk_multiagents/buyer_adk.py` and `m4_adk_multiagents/seller_adk.py` (ADK agents)

---

## 10. Production A2A Patterns

### Pattern 1: Agent Registry

In production, agents need to discover each other. An agent registry solves this:

```python
class AgentRegistry:
    """
    Agents register themselves with their capabilities.
    Other agents can discover and connect to them.
    """

    def __init__(self):
        self._agents: dict[str, AgentCard] = {}

    def register(self, agent_card: AgentCard) -> None:
        """Agent announces its existence and capabilities."""
        self._agents[agent_card.agent_id] = agent_card

    def find_by_capability(self, capability: str) -> list[AgentCard]:
        """Find agents that can handle a specific task."""
        return [
            card for card in self._agents.values()
            if capability in card.capabilities
        ]

class AgentCard(BaseModel):
    """The A2A equivalent of an MCP server's tool list."""
    agent_id: str
    name: str
    description: str
    capabilities: list[str]   # ["real_estate_negotiation", "property_valuation"]
    endpoint: str             # "http://buyer-agent:8000"
    supported_message_types: list[MessageType]
    input_schema: dict        # What messages this agent accepts
```

### Pattern 2: Mediator Agent

When two agents reach deadlock, a mediator agent can help:

```python
class MediatorAgent:
    """
    A third agent that intervenes when buyer and seller can't agree.
    This is an A2A pattern where a third agent joins the negotiation.
    """

    async def mediate(
        self,
        buyer_final_offer: float,
        seller_final_counter: float,
        negotiation_history: list[A2AMessage]
    ) -> A2AMessage:
        """Propose a compromise based on both parties' positions."""

        # LLM analyzes the full history to find a fair midpoint
        midpoint = (buyer_final_offer + seller_final_counter) / 2

        prompt = f"""
        A real estate negotiation has stalled:
        - Buyer's final offer: ${buyer_final_offer:,.0f}
        - Seller's final ask: ${seller_final_counter:,.0f}
        - Gap: ${seller_final_counter - buyer_final_offer:,.0f}

        Full negotiation history: {[m.dict() for m in negotiation_history]}

        Propose a fair settlement price with justification.
        The mathematical midpoint is ${midpoint:,.0f}.
        """

        settlement = await self.llm.propose_settlement(prompt)
        return A2AMessage(
            from_agent="mediator",
            to_agent="both",
            message_type="SETTLEMENT_PROPOSAL",
            payload=NegotiationPayload(
                price=settlement.price,
                message=settlement.justification
            )
        )
```

### Pattern 3: Delegation

One agent delegates a subtask to a specialist agent:

```python
# Buyer agent delegates property research to a specialist
delegation_message = A2AMessage(
    from_agent="buyer",
    to_agent="research_agent",
    message_type="TASK_DELEGATION",
    payload=NegotiationPayload(
        message=(
            "Please research 742 Evergreen Terrace, Austin TX 78701. "
            "I need: (1) comparable sales in last 90 days, "
            "(2) neighborhood crime statistics, "
            "(3) school district rating, "
            "(4) flood zone status. "
            "Report back before my next negotiation round."
        )
    )
)
```

---

## 11. Common Misconceptions

### ❌ "A2A means agents talk in natural language"

**Reality**: While agents CAN communicate in natural language (one LLM sends text to another), structured JSON messages are far more reliable in production. Natural language is ambiguous; JSON is not.

### ❌ "A2A replaces MCP"

**Reality**: They solve completely different problems. MCP connects agents to external systems. A2A connects agents to each other. Our negotiation simulator uses both simultaneously.

### ❌ "A2A requires a framework"

**Reality**: The simplest A2A is two Python functions calling each other. You don't need a framework. Add structure (message schemas, state machines) as complexity grows.

### ❌ "Agents need equal capabilities to communicate"

**Reality**: A simple rule-based agent can A2A communicate with a sophisticated GPT-4 agent. The protocol is the interface — not the intelligence behind it.

### ❌ "A2A is only for multi-agent systems"

**Reality**: A2A patterns also appear when a single agent communicates with itself across time (e.g., leaving a "message" for its next execution) or when an orchestrator delegates to specialized sub-agents.

---

## Summary

| Concept | Key Takeaway |
|---|---|
| **A2A definition** | Autonomous agents communicating with each other |
| **vs MCP** | MCP = agent to tools; A2A = agent to agent |
| **No standard yet** | Custom JSON schemas are most common in 2025 |
| **Message schema** | Include identity, temporal context, intent, payload |
| **State machine** | Track valid message transitions to prevent invalid moves |
| **Transport** | In-process (simple), HTTP (microservices), MQ (production) |
| **Error types** | Validation, reasoning, communication, deadlock |
| **Production patterns** | Registry, Mediator, Delegation |

---

*← [MCP Deep Dive](../../m2_mcp/notes/mcp_deep_dive.md)*
*→ [LangGraph Explained](../../m3_langgraph_multiagents/notes/langgraph_explained.md)*
