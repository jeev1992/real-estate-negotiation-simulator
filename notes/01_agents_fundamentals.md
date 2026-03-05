# 01 — Agent Fundamentals
## A Complete Guide for Engineers New to AI Agents

---

## Table of Contents

1. [What Is an AI Agent?](#1-what-is-an-ai-agent)
2. [The Perception-Cognition-Action Loop](#2-the-perception-cognition-action-loop)
3. [LLM vs Workflow vs Agent](#3-llm-vs-workflow-vs-agent)
4. [The Three Core Properties of Agents](#4-the-three-core-properties-of-agents)
5. [Agent Architectures](#5-agent-architectures)
6. [Multi-Agent Systems](#6-multi-agent-systems)
7. [Real-World Analogies](#7-real-world-analogies)
8. [Common Misconceptions](#8-common-misconceptions)
9. [When to Use Agents (and When NOT To)](#9-when-to-use-agents-and-when-not-to)
10. [How Our Negotiation Simulator Uses These Concepts](#10-how-our-negotiation-simulator-uses-these-concepts)

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

**Implementation note**: In our simple version, GPT-4o implements ReAct implicitly through its system prompt and structured output. In LangGraph, we make the loop explicit as graph nodes.

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
             │  LANGGRAPH           │
             │  ORCHESTRATOR        │
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

An LLM orchestrator (like LangGraph) is like an air traffic controller:
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

A2A Communication         Structured JSON messages between agents (see note 03)

MCP Tool Use              Both agents use MCP to query external pricing and
                          inventory data (see note 02)

LangGraph Orchestration   The negotiation loop is a stateful graph (see note 04)

Google ADK                Production-style agent framework (see note 05)
```

### The Architecture at a Glance

```
                    ┌─────────────────────────────┐
                    │   LANGGRAPH ORCHESTRATOR    │
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

## Summary

| Concept | Key Takeaway |
|---|---|
| **Agent** | LLM + Tools + Memory + Goal + Loop |
| **vs LLM** | LLM is just cognition; agent is the full system |
| **vs Workflow** | Workflow has predetermined logic; agent decides its own |
| **Core properties** | Autonomy, Reactivity, Pro-activeness |
| **Architectures** | ReAct (most common), Plan-Execute, Reflection |
| **Multi-agent** | Adversarial, Hierarchical, Collaborative |
| **Use agents when** | Logic cannot be predetermined; high ambiguity |
| **Avoid agents when** | Deterministic process; speed/cost critical |

---

*Next: [02 — MCP Deep Dive →](02_mcp_deep_dive.md)*
