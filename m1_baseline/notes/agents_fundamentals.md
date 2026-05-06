# Agent Fundamentals
## A Complete Guide for Engineers New to AI Agents

---

## Table of Contents

1. [What Is an AI Agent?](#1-what-is-an-ai-agent)
2. [The Perception-Cognition-Action Loop](#2-the-perception-cognition-action-loop)
3. [LLM vs Workflow vs Agent](#3-llm-vs-workflow-vs-agent)
4. [The Three Core Properties of Agents](#4-the-three-core-properties-of-agents)
5. [Agent Architectures](#5-agent-architectures)
    - [Finite State Machines (FSM) as Agent Control](#54-finite-state-machines-fsm-as-agent-control)
6. [Multi-Agent Systems](#6-multi-agent-systems)
7. [Real-World Analogies](#7-real-world-analogies)
8. [Common Misconceptions](#8-common-misconceptions)
9. [When to Use Agents (and When NOT To)](#9-when-to-use-agents-and-when-not-to)
10. [How Our Negotiation Simulator Uses These Concepts](#10-how-our-negotiation-simulator-uses-these-concepts)
11. [The Workshop's 10 Failure Modes — Why Naive Agents Break](#11-the-workshops-10-failure-modes--why-naive-agents-break)

---

## 1. What Is an AI Agent?

An **AI Agent** is a software system that:

1. **Perceives** its environment (reads tool outputs, receives messages, processes data)
2. **Reasons** about what action to take next (powered by an LLM or decision engine)
3. **Acts** to change its environment (calls tools, sends messages, writes files)
4. **Loops** — repeats this cycle autonomously until a goal is achieved or a stopping condition is met

The key word is **autonomous**. An agent doesn't just answer one question — it works through a problem over multiple steps, adapting its behavior based on what it observes.

### Minimal Definition

```
Agent = LLM + Tools + Memory + Goal + Loop
```

Remove any one of these, and you have something less than an agent:
- **LLM without tools** → a chatbot
- **LLM without a loop** → a single inference call
- **Loop without a goal** → an infinite script
- **Tools without reasoning** → a regular API client

---

## 2. The Perception-Cognition-Action Loop

This is the fundamental operating cycle of every agent. Think of it as the agent's heartbeat.

```
┌─────────────────────────────────────────────────────────────────┐
│                        ENVIRONMENT                              │
│         (external APIs, databases, other agents, files)         │
└────────────────┬────────────────────────────┬───────────────────┘
                 │                            │
            Observe                          Act
                 │                            │
                 ▼                            │
    ┌────────────────────────┐               │
    │      PERCEPTION        │               │
    │                        │               │
    │  • Read tool results   │               │
    │  • Parse API responses │               │
    │  • Receive messages    │               │
    │  • Load memory         │               │
    └────────────┬───────────┘               │
                 │                            │
                 ▼                            │
    ┌────────────────────────┐               │
    │      COGNITION         │               │
    │                        │               │
    │  • LLM reasoning       │               │
    │  • Goal evaluation     │               │
    │  • Plan next action    │               │
    │  • Update beliefs      │               │
    └────────────┬───────────┘               │
                 │                            │
                 ▼                            │
    ┌────────────────────────┐               │
    │        ACTION          │───────────────┘
    │                        │
    │  • Call tools          │
    │  • Send messages       │
    │  • Write to storage    │
    │  • Signal completion   │
    └────────────────────────┘
```

### Concrete Example: Our Buyer Agent

```
Round 1:
  PERCEIVE  → "Seller countered at $480,000. Market data shows avg comp is $462,000."
  COGNIZE   → "Counter is 3.7% above market. I have budget room. Increase my offer slightly."
  ACT       → Send new offer: $435,000 with market data justification

Round 2:
  PERCEIVE  → "Seller came down to $472,000. Still 2.2% above market."
  COGNIZE   → "Good movement. I'll push harder. I'm at $435K, budget is $460K."
  ACT       → Send new offer: $445,000

... continues until agreement or deadlock
```

---

## 3. LLM vs Workflow vs Agent

This is one of the most important distinctions to understand before building any AI system.

### Side-by-Side Comparison

```
┌─────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Feature         │ Raw LLM Call     │ Workflow         │ Agent            │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Memory          │ None (stateless) │ Defined in code  │ Dynamic, grows   │
│ Tool use        │ No               │ Hardcoded steps  │ Chosen by agent  │
│ Loop            │ No               │ Fixed iterations │ Goal-driven      │
│ Decisions       │ Single response  │ Branching script │ Autonomous       │
│ Adaptability    │ None             │ Limited          │ High             │
│ Predictability  │ High             │ Very high        │ Lower            │
│ Complexity      │ Simple           │ Medium           │ High             │
│ Cost            │ Low              │ Medium           │ Higher           │
└─────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

### Raw LLM Call

```python
# This is NOT an agent
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What is 2+2?"}]
)
# One call. One response. Done. No loop, no tools, no memory.
```

**Use when**: You need a single transformation, classification, or generation. No state needed.

**Example**: Summarize this paragraph, classify this email, translate this sentence.

### Workflow (Scripted Pipeline)

```python
# This is NOT an agent — it's a deterministic pipeline
def process_mortgage_application(application: dict) -> dict:
    # Step 1: Always validate
    validated = validate_fields(application)

    # Step 2: Always check credit
    credit_score = check_credit_bureau(validated["ssn"])

    # Step 3: Branch, but the logic is PREDETERMINED
    if credit_score > 700:
        return approve_loan(validated)
    else:
        return reject_loan(validated)
    # The PROGRAMMER decided every branch. The LLM had no autonomy.
```

**Use when**: The process is well-defined, steps are known in advance, compliance matters.

**Example**: Invoice processing, form validation pipelines, ETL jobs.

### Agent

```python
# This IS an agent
async def buyer_agent_loop(state: NegotiationState) -> NegotiationState:
    # The LLM decides what to do next, not the programmer
    response = await llm.decide(
        goal="Purchase the property at the best possible price",
        observations=state.history,
        available_tools=["get_market_price", "calculate_discount", "make_offer"],
        current_state=state
    )

    # The agent autonomously chooses to use a tool...
    if response.wants_tool:
        tool_result = await call_tool(response.tool_name, response.tool_args)
        state.add_observation(tool_result)
        return await buyer_agent_loop(state)  # Loop back

    # ...or make a final decision
    return state.with_offer(response.offer_price, response.message)
```

**Use when**: The path to the goal cannot be fully predetermined, requires adaptation, multi-step reasoning.

**Example**: Negotiation, research, code debugging, customer service resolution.

---

## 4. The Three Core Properties of Agents

These come from the original academic definition (Wooldridge & Jennings, 1995) and remain relevant today.

### 4.1 Autonomy

The agent operates without direct human intervention. It makes its own decisions based on its goals and beliefs, not by following a script.

```
LOW AUTONOMY (workflow):                HIGH AUTONOMY (agent):
─────────────────────────               ─────────────────────────
Step 1: Call Zillow API                 Goal: Get best offer for property
Step 2: If price > X, do Y             LLM: "I'll check market data first..."
Step 3: Send email                      LLM: "Comps are lower than asking..."
Step 4: Done                            LLM: "I'll counter at 93% of list price"
                                        LLM: "Seller rejected, adjusting..."
                                        LLM: "Found a comparable that helps me..."
                                        [continues until goal met]
```

### 4.2 Reactivity (Responsiveness)

The agent perceives its environment and **responds to changes** in a timely fashion. It doesn't just blindly execute a plan — it updates based on what it observes.

In negotiation: If the seller unexpectedly drops their price significantly in round 2, the buyer agent notices this (reactivity) and adjusts its strategy accordingly rather than mechanically executing a pre-planned sequence of offers.

### 4.3 Pro-activeness (Goal-Directedness)

The agent doesn't just react — it **takes initiative** to achieve its goals. It anticipates, plans ahead, and acts strategically.

In negotiation: The buyer agent proactively queries market data before making an offer, even if nobody told it to. It takes this initiative because it serves the goal of making a well-justified offer.

---

## 5. Agent Architectures

Different agent architectures make different trade-offs between capability and complexity.

### 5.1 ReAct (Reason + Act)

The most common pattern for tool-using LLM agents. The model alternates between reasoning ("Thought:") and acting ("Action:").

```
┌─────────────────────────────────────────────────────────┐
│  User Goal: "Negotiate the best price for this house"   │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
    ┌───────────────────────────────────────────────────┐
    │  THOUGHT: "I need market data to justify my       │
    │  opening offer. Let me check comparable sales."   │
    └───────────────────────┬───────────────────────────┘
                            │
                            ▼
    ┌───────────────────────────────────────────────────┐
    │  ACTION: call get_market_price("742 Evergreen...") │
    └───────────────────────┬───────────────────────────┘
                            │
                            ▼
    ┌───────────────────────────────────────────────────┐
    │  OBSERVATION: {avg_comp: $462K, list: $485K,      │
    │  overpriced_by: 4.9%}                             │
    └───────────────────────┬───────────────────────────┘
                            │
                            ▼
    ┌───────────────────────────────────────────────────┐
    │  THOUGHT: "Property is overpriced by ~5%.         │
    │  Starting offer at $425K is justified."           │
    └───────────────────────┬───────────────────────────┘
                            │
                            ▼
    ┌───────────────────────────────────────────────────┐
    │  ACTION: send_offer(price=425000, msg="Based on   │
    │  recent comps averaging $462K...")                │
    └───────────────────────────────────────────────────┘
```

**Implementation note**: In our simple version, GPT-4o implements ReAct implicitly through its system prompt and structured output. In M3's ADK build, the same loop is made explicit by the `Runner` + `MCPToolset` pair driving each turn.

### 5.2 Plan-and-Execute

The agent first creates a complete plan, then executes each step. Better for long-horizon tasks where you need upfront structure.

```
PHASE 1 — PLANNING:
  LLM creates plan:
    1. Research market comparables
    2. Determine fair value range
    3. Calculate opening offer (12% below ask)
    4. Negotiate in increments of 2-3%
    5. Walk away if seller won't go below $460K

PHASE 2 — EXECUTION:
  Execute step 1 → observe result → execute step 2 → ...
  (Can replan if steps fail)
```

### 5.3 Reflection (Self-Critique Loop)

The agent critiques its own outputs before committing. Useful for high-stakes decisions.

```
Draft offer: $435,000
    ↓
REFLECT: "Is this offer reasonable? Does it respect my budget?
          Will it offend the seller? Is it justified by data?"
    ↓
Critique: "This is 10.3% below asking. Might be too aggressive
           given the market is balanced, not cold."
    ↓
Revised offer: $442,000
    ↓
REFLECT: "Better. 8.9% below asking. Data supports this range."
    ↓
COMMIT: Send $442,000 offer
```

### 5.4 Finite State Machines (FSM) as Agent Control

An **FSM (Finite State Machine)** is a deterministic control layer that defines:
- which state the system is currently in,
- what events are valid in that state,
- and exactly which state comes next.

This is one of the best ways to make LLM-driven systems safe and predictable: let the LLM decide *content* (what to say, what offer to make), while the FSM decides *control flow* (what is allowed now, what happens next).

```
STATE MACHINE = States + Events + Transition Rules
```

### Negotiation FSM Example

```
INIT
    └─(start_negotiation)────────────► BUYER_TURN

BUYER_TURN
    └─(buyer_offer_submitted)────────► SELLER_TURN

SELLER_TURN
    ├─(seller_accepts)───────────────► AGREEMENT
    ├─(seller_rejects_deadlock)──────► DEADLOCK
    └─(seller_counter_offer)─────────► BUYER_TURN

ANY TURN
    └─(max_rounds_reached)───────────► DEADLOCK
```

### Why FSMs Matter for Agents

- **Guardrails**: Prevent illegal actions (e.g., double-turns or accepting after deadlock).
- **Debuggability**: You can inspect transitions and explain exactly why a run ended.
- **Testability**: State transitions are deterministic and easy to unit test.
- **Separation of concerns**: LLM handles strategy; FSM handles protocol correctness.

In this repository, the baseline implementation in `m1_baseline/state_machine.py` demonstrates this principle directly.

**Read this next (implementation walkthrough):**

1. Open `m1_baseline/state_machine.py`
2. Identify the state enum/constants and allowed transitions
3. Trace one full path: `INIT → BUYER_TURN → SELLER_TURN → AGREEMENT`
4. Then run `tests/test_fsm.py` to verify transition behavior

---

## 6. Multi-Agent Systems

Single agents have limits. Multi-agent systems distribute cognition across specialized agents.

### Why Multiple Agents?

```
SINGLE AGENT PROBLEMS:
  • Context window fills up (too much history)
  • Conflicting goals (can't be objective)
  • Single point of failure
  • Hard to parallelize

MULTI-AGENT SOLUTIONS:
  • Each agent has focused context
  • Adversarial/cooperative dynamics (buyer vs seller)
  • Redundancy and specialization
  • Natural parallelism
```

### Multi-Agent Patterns

#### Pattern 1: Adversarial (Our Negotiation Simulator)

Two agents with **opposing goals** interact through structured communication.

```
┌─────────────────┐    A2A Messages    ┌─────────────────┐
│   BUYER AGENT   │◄──────────────────►│   SELLER AGENT  │
│                 │                    │                 │
│ Goal: Buy low   │    OFFERS &        │ Goal: Sell high │
│ Budget: $460K   │    COUNTER-OFFERS  │ Min: $445K      │
│ Uses: MCP       │                    │ Uses: MCP       │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         └──────────────┬───────────────────────┘
                        │
                        ▼
             ┌──────────────────────┐
             │  ADK ORCHESTRATOR    │
             │                      │
             │  • Manages state     │
             │  • Controls rounds   │
             │  • Detects agreement │
             │  • Enforces rules    │
             └──────────────────────┘
```

#### Pattern 2: Hierarchical

A manager agent decomposes goals and delegates to worker agents.

```
                 ┌─────────────────┐
                 │  MANAGER AGENT  │
                 │  (Coordinator)  │
                 └────────┬────────┘
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │ Research │    │ Analysis │    │ Decision │
   │  Agent   │    │  Agent   │    │  Agent   │
   └──────────┘    └──────────┘    └──────────┘
```

#### Pattern 3: Collaborative (Swarm)

Multiple agents work together toward a shared goal, sharing observations.

```
Agent A ──┐
Agent B ──┼──► Shared Memory / State ──► Synthesized Output
Agent C ──┘
```

### Agent Communication Protocols

When agents talk to each other, they need a **shared language**. This is what **A2A** (covered in note 03) addresses.

```python
# Agents don't just send raw text to each other
# They send structured messages with defined schemas

message = {
    "message_id": "msg_005",
    "from_agent": "buyer",
    "to_agent": "seller",
    "message_type": "COUNTER_OFFER",
    "round": 3,
    "payload": {
        "offer_price": 448000,
        "conditions": ["30-day financing contingency"],
        "message": "Given comparable sales averaging $462K..."
    }
}
```

---

## 7. Real-World Analogies

Analogies make abstract concepts stick. Use these to explain agents to non-technical stakeholders.

### The Real Estate Buyer's Agent Analogy

You hire a buyer's agent (a human) to find and negotiate a home for you. They:
- **Perceive**: Read MLS listings, visit properties, research comparables
- **Reason**: "This house is overpriced by 8% given the comps on Oak Street"
- **Act**: Make an offer, negotiate with the listing agent, advise you

An AI buyer agent does the same thing — but never sleeps, negotiates in seconds, and can run 1,000 negotiations simultaneously.

### The Stock Trader Analogy

An algorithmic trader:
- Perceives market data (prices, volumes, news)
- Reasons about patterns and opportunities
- Acts by placing buy/sell orders
- Loops continuously throughout trading hours

This IS an agent — it just doesn't use an LLM.

### The Air Traffic Controller Analogy

An LLM orchestrator (like ADK's workflow agents) is like an air traffic controller:
- It doesn't fly any planes (it doesn't execute business logic)
- It coordinates multiple agents (planes) following defined protocols
- It manages state (which runway is free, which agents are active)
- It handles conflicts and edge cases

---

## 8. Common Misconceptions

### ❌ Misconception 1: "An agent is just a chatbot with tools"

**Reality**: A chatbot responds to user messages. An agent **autonomously** pursues goals. Big difference. Our buyer agent doesn't wait for a human to tell it what offer to make — it decides that itself.

### ❌ Misconception 2: "More agents = better results"

**Reality**: More agents = more complexity, more cost, more failure modes. Use the minimum number of agents needed. A single well-designed agent often outperforms a poorly-coordinated multi-agent system.

### ❌ Misconception 3: "Agents are deterministic"

**Reality**: Agents powered by LLMs are probabilistic. The same input can produce different outputs. This is a feature (adaptability) and a bug (unpredictability). You need guardrails, state management, and testing strategies.

### ❌ Misconception 4: "The LLM IS the agent"

**Reality**: The LLM is just the cognition component. The agent is the full system: LLM + tool execution framework + memory/state + orchestration + error handling.

### ❌ Misconception 5: "Agents will replace all software"

**Reality**: Agents are appropriate for tasks with high ambiguity and complexity. For well-defined processes with clear rules, traditional code is faster, cheaper, and more reliable.

---

## 9. When to Use Agents (and When NOT To)

### ✅ Use Agents When:

| Situation | Why Agents Help |
|---|---|
| Path to goal is unknown upfront | Agent can explore and adapt |
| Multiple tools need coordination | Agent decides which tools to use when |
| Requires judgment and reasoning | LLM provides flexible cognition |
| Context is complex and changing | Agent updates beliefs from observations |
| Task is adversarial or negotiation-based | Agent can counter-strategize |

### ❌ Do NOT Use Agents When:

| Situation | Better Alternative |
|---|---|
| Process is fully deterministic | Use a function/workflow |
| Speed is critical (< 100ms) | Agents are too slow |
| Regulatory compliance required | Deterministic code + audit logs |
| Budget is very tight | Agents consume many tokens |
| Task is a single-step transformation | Direct LLM call |

### The Golden Rule

> **If you can write the logic as a script, write it as a script. Use agents only when the logic itself cannot be predetermined.**

---

## 10. How Our Negotiation Simulator Uses These Concepts

Our project is a concrete demonstration of every concept above:

```
CONCEPT                   HOW WE USE IT
─────────────────────────────────────────────────────────────────────────
Perception-Cognition-Act  Each agent perceives counter-offers, reasons
                          with its LLM, then acts by submitting new offers

Autonomy                  Agents decide their own offer prices; no human
                          intervention during negotiation rounds

Reactivity                If seller drops price dramatically, buyer adjusts
                          strategy (doesn't just follow the pre-planned sequence)

Multi-Agent Adversarial   Buyer agent vs Seller agent with opposing goals

FSM Control Layer         Deterministic state transitions for turns,
                         agreement, and deadlock outcomes

A2A Communication         Structured JSON messages between agents (see note 03)

MCP Tool Use              Both agents use MCP to query external pricing and
                          inventory data (see note 02)

ADK Orchestration         The negotiation loop is bounded by ADK workflow agents and the A2A message lifecycle (see notes in `m3_adk_multiagents/notes/`)

Google ADK                Production-style agent framework (see note 05)
```

### The Architecture at a Glance

```
                    ┌─────────────────────────────┐
                    │   ADK ORCHESTRATOR          │
                    │   (manages negotiation       │
                    │    state across all rounds)  │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                                 │
              ▼                                 ▼
   ┌─────────────────────┐          ┌─────────────────────┐
   │    BUYER AGENT      │          │    SELLER AGENT     │
   │                     │          │                     │
   │  LLM: GPT-4o        │◄────────►│  LLM: GPT-4o        │
   │  (simple version)   │  A2A     │  (simple version)   │
   │  or Gemini 2.0      │  msgs    │  or Gemini 2.0      │
   │  (ADK version)      │          │  (ADK version)      │
   └──────────┬──────────┘          └──────────┬──────────┘
              │                                 │
              │ MCP                             │ MCP
              │                                 │
   ┌──────────▼──────────┐          ┌──────────▼──────────┐
   │   PRICING SERVER    │          │  INVENTORY SERVER   │
   │   (MCP Tool)        │          │  (MCP Tool)         │
   │                     │          │                     │
   │  • market_price     │          │  • inventory_level  │
   │  • calc_discount    │          │  • min_price        │
   └─────────────────────┘          └─────────────────────┘
```

---

## 11. The Workshop's 10 Failure Modes — Why Naive Agents Break

This section exists specifically to map the conceptual material above onto
the failure modes the **Module 1 workshop demo** is built around. If you
read this note before the workshop, this is the section that previews the
demo. If you read it after, this is the section that lets you re-anchor on
the specific bugs you saw.

The premise of `m1_baseline/naive_negotiation.py` is: **"Build the most
obvious agent system you can. Then watch every part of it fail in
production-realistic ways."** The file documents 10 distinct failure modes —
each one fixed somewhere later in the workshop.

### The 10 failure modes

| # | Failure mode | What goes wrong | Fixed by |
|---|---|---|---|
| 1 | Raw string communication | LLM returns anything; downstream code can't reliably parse intent | A2A structured messages (Module 3) |
| 2 | No schema validation | Messages have no contract — fields can be missing, types can drift | Pydantic / A2A `DataPart` (Module 3) |
| 3 | No state machine | `while True` loop with no termination guarantee | `NegotiationFSM` → `LoopAgent` |
| 4 | No turn limits | Can loop forever if no agreement is reached | `max_turns` → `max_iterations` |
| 5 | Fragile regex parsing | `re.search(r'\$?(\d[\d,]*)')` extracts the *first* number it sees — wrong if the LLM mentions any other dollar amount first | Typed `submit_decision` parameters |
| 6 | No termination guarantee | `"DEAL" in message.upper()` matches `"DEAL-breaker"` (false positive) and misses `"let's finalize this"` (false negative) | Terminal states with empty transitions / `submit_decision` action field |
| 7 | Silent failures | Bad parse returns `None`; loop keeps going on corrupted data with no error | Pydantic validation that raises on missing fields |
| 8 | Hardcoded prices | `SELLER_MIN_PRICE = 445_000` lives in source — stale, leaked, untyped | MCP servers (Module 2) |
| 9 | No observability | Can't reconstruct what happened; no event log | ADK event stream + A2A task lifecycle |
| 10 | No evaluation | Can't measure if the result was actually good | Session analytics, agreed-price tracking |

### The bugs in concrete terms

The first three are abstract until you see them play out. Three concrete
examples from the workshop demo:

**Bug from Demo 1 — "works by luck."** Buyer max $460K, seller min $445K
(ZOPA exists). The buyer offers $425K, the seller counters $453K, the
buyer says `"ACCEPT at $453,150"`. The system reports a deal. **It worked,
but barely.** Three things had to happen by coincidence:
- The seller's LLM happened to start its reply with the magic word `"DEAL"`.
- The seller's reply happened to mention the counter price as the *only*
  dollar amount in the text.
- The buyer's LLM happened to use the keyword `"ACCEPT"` rather than
  `"agreed"`, `"yes"`, `"sold"`, or any of the dozens of natural ways a
  human might phrase agreement.

Change any one of those — different temperature, different model version,
slightly different prompt — and the same scenario fails. This is why
**"my agent works on my machine" is not a release criterion for agent systems.**

**Bug from Demo 2 — "no-ZOPA infinite loop."** Buyer max $420K, seller min
$450K. The agents physically cannot agree. The naive loop runs for the
full 100-turn cap, burning ~$5 of API calls. Then **the seller's LLM
fatigues and emits the word `"DEAL"` to escape the conversation, accepting
$420K — thirty thousand below its own floor.** The system reports
"success" with a contract that violates the seller's stated constraint.
Nothing in the code caught the violation. *No code checked whether
$420K ≥ $450K.* The "business rule" existed only as a prompt instruction.

**Bug from M3 development — `'ACCEPT' in 'acceptable'`.** When we built the
M3 negotiation orchestrator, the first version's acceptance check was:

```python
if "ACCEPT" in seller_response.upper():
    deal_reached = True
```

The seller's MCP tool `get_minimum_acceptable_price` returns text containing
**"minimum *acceptable* price is $445,000"**. The substring check matched
**ACCEPTABLE** and false-triggered acceptance on every counter-offer that
mentioned the floor. The negotiation closed on round 1 every time.

The fix is the M3 `submit_decision` tool — the seller calls a typed
function with `action='ACCEPT'` or `action='COUNTER'`, and the loop reads
`state['seller_decision']['action']` as a structured dict field. **No
substring matching, ever.** This is M1's lesson cashing out two modules later.

### How the FSM fixes the first slice of these

The remediations live across three modules, but Module 1's `state_machine.py`
fixes failure modes **#3, #4, and #6** directly:

- **#3 (no state machine)** → `NegotiationFSM` with explicit states.
- **#4 (no turn limits)** → `process_turn()` increments `turn_count`,
  capped at `max_turns`. Loop must exit.
- **#6 (no termination guarantee)** → Terminal states `AGREED` and `FAILED`
  have **empty transition sets**:
  ```python
  TRANSITIONS = {
      IDLE:        {NEGOTIATING, FAILED},
      NEGOTIATING: {NEGOTIATING, AGREED, FAILED},
      AGREED:      set(),    # ← empty: no way out
      FAILED:      set(),    # ← empty: no way out
  }
  ```
  Once the FSM enters a terminal state, it cannot move. Combined with the
  turn cap, **the loop is mathematically guaranteed to terminate**.

The remaining failure modes (#1, #2, #5, #7, #8, #9, #10) are fixed by
MCP (Module 2) and ADK + A2A (Module 3). The "termination guarantee" lesson
from `state_machine.py` is the conceptual foundation; everything later is
the same idea applied to richer scenarios.

### What this means for everything that follows

**Module 2** (MCP) replaces hardcoded data with protocol-served tools —
fixing failure mode #8.

**Module 3** (ADK + A2A) replaces fragile control flow with `LoopAgent`,
typed messages with A2A `DataPart`, and string-match termination with the
`submit_decision` pattern — fixing failure modes #1, #2, #5, #6, #7, #9, #10.

The arc of the entire course is: **"see the failure → name it → fix it
properly".** Section 11 you just read is the *first half* — the seeing and
naming. The rest of the workshop is the *second half* — the proper fixing.

---

## Summary

| Concept | Key Takeaway |
|---|---|
| **Agent** | LLM + Tools + Memory + Goal + Loop |
| **vs LLM** | LLM is just cognition; agent is the full system |
| **vs Workflow** | Workflow has predetermined logic; agent decides its own |
| **Core properties** | Autonomy, Reactivity, Pro-activeness |
| **Architectures** | ReAct (most common), Plan-Execute, Reflection, FSM control layer |
| **Multi-agent** | Adversarial, Hierarchical, Collaborative |
| **Use agents when** | Logic cannot be predetermined; high ambiguity |
| **Avoid agents when** | Deterministic process; speed/cost critical |

---

*Next: [MCP Deep Dive →](../../m2_mcp/notes/mcp_deep_dive.md)*
