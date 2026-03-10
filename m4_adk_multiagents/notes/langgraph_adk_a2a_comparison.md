# LangGraph vs Google ADK vs A2A
## Orchestration Models, Tradeoffs, and Interoperability

---

## Table of Contents

1. [Google ADK Orchestration](#1-google-adk-orchestration)
2. [LangGraph Orchestration](#2-langgraph-orchestration)
3. [ADK vs LangGraph (Side-by-Side)](#3-adk-vs-langgraph-side-by-side)
4. [A2A Protocol](#4-a2a-protocol)
5. [How They Fit Together](#5-how-they-fit-together)
6. [How This Repo Maps to the Concepts](#6-how-this-repo-maps-to-the-concepts)
7. [Key Takeaways](#7-key-takeaways)

---

## 1. Google ADK Orchestration

Google ADK provides built-in orchestrator agent types for composing multi-agent workflows.

### Built-in agent/orchestrator patterns

- `SequentialAgent` — runs sub-agents one after another (pipeline)
- `ParallelAgent` — runs sub-agents concurrently
- `LoopAgent` — repeats sub-agents until iteration/termination criteria are met
- `LlmAgent` — can act as a router/coordinator using LLM reasoning to choose among tools/sub-agents

The model is hierarchical: orchestrators are agents that contain other agents.

For custom routing logic, subclass `BaseAgent` and override `_run_async_impl`.

---

## 2. LangGraph Orchestration

LangGraph uses an explicit graph model.

### Core mechanics

- Agents/functions are graph nodes
- Routing logic is encoded as edges (including conditional edges)
- Shared state flows through a `StateGraph`

This makes cycles, branching, and stateful decisions explicit and inspectable.

Practical tradeoff:
- More verbose setup
- Usually easier to reason about complex routing and termination behavior

---

## 3. ADK vs LangGraph (Side-by-Side)

| Feature | LangGraph | Google ADK |
|---|---|---|
| Model | Explicit graph (nodes/edges) | Hierarchical agent composition |
| Sequential flows | Linear/ordered graph paths | `SequentialAgent` |
| Parallel execution | Parallel node branches | `ParallelAgent` |
| Conditional routing | Conditional edges/router functions | `LlmAgent` routing or custom `BaseAgent` |
| Looping | Cycles in graph | `LoopAgent` |
| State management | `StateGraph` shared state | Session + `InvocationContext` |
| Complexity | More setup, more explicit | Simpler defaults, less explicit flow surface |

Both are in-process, single-framework orchestration approaches when used inside one application/runtime.

---

## 4. A2A Protocol

A2A (Agent-to-Agent) is Google’s open protocol for cross-framework, cross-system agent communication over HTTP.

### Key protocol concepts

- Each agent publishes an Agent Card (`/.well-known/agent.json`) describing capabilities
- Agents exchange standardized task requests/responses (JSON-RPC style)
- Any framework can participate (ADK, LangGraph, CrewAI, custom) if it implements the protocol

### Important clarification

A2A does **not** remove the need for orchestration; it changes where orchestration can happen.

You can have:
- A central orchestrator delegating to remote agents via A2A
- Decentralized peer-to-peer networks with no single orchestrator

---

## 5. How They Fit Together

```text
┌─────────────────────────────────────────────┐
│           Within a single system            │
│    LangGraph (graph) / ADK (hierarchy)      │
│         in-process orchestration             │
└─────────────────┬───────────────────────────┘
                  │ A2A bridges across systems
┌─────────────────▼───────────────────────────┐
│          Across systems/frameworks          │
│  ADK Agent ←─A2A─→ LangGraph Agent ←─A2A─→ │
│  CrewAI Agent  (peer-to-peer possible)      │
└─────────────────────────────────────────────┘
```

---

## 6. How This Repo Maps to the Concepts

### LangGraph side

- `m3_langgraph_multiagents/langgraph_flow.py`
  - Explicit node/edge orchestration with shared state

### ADK side

- `m4_adk_multiagents/buyer_adk.py`
- `m4_adk_multiagents/seller_adk.py`
  - `LlmAgent` + `MCPToolset` + `Runner`
- `m4_adk_multiagents/a2a_protocol_http_orchestrator.py`
  - Buyer/seller orchestration loop with ADK session-state tracking

### A2A side

- `m4_adk_multiagents/a2a_protocol_seller_server.py`
- `m4_adk_multiagents/a2a_protocol_buyer_client_demo.py`
  - True protocol-level A2A transport between agents

---

## 7. Key Takeaways

- LangGraph = explicit graph-based orchestration, single framework
- Google ADK = hierarchical agent composition, single framework
- A2A = interoperability protocol for cross-framework, cross-system communication
- A2A is complementary to LangGraph/ADK orchestration, not a replacement
