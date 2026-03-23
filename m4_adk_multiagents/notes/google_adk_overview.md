# Google ADK Overview
## Building Production-Grade Agents with Google's Agent Development Kit

See also: [LangGraph vs Google ADK vs A2A](langgraph_adk_a2a_comparison.md) for the orchestration and interoperability comparison index.

---

## Table of Contents

1. [What Is Google ADK?](#1-what-is-google-adk)
2. [ADK vs Building From Scratch](#2-adk-vs-building-from-scratch)
3. [Core Components](#3-core-components)
4. [Agent Types in ADK](#4-agent-types-in-adk)
5. [Tool Integration in ADK](#5-tool-integration-in-adk)
6. [MCP Integration in ADK](#6-mcp-integration-in-adk)
7. [Session and Memory Management](#7-session-and-memory-management)
8. [The Agent Lifecycle](#8-the-agent-lifecycle)
9. [Multi-Agent in ADK](#9-multi-agent-in-adk)
10. [Model Provider Choices in ADK](#10-model-provider-choices-in-adk)
11. [Our ADK Implementation](#11-our-adk-implementation)
12. [ADK vs LangGraph vs Simple Python](#12-adk-vs-langgraph-vs-simple-python)
13. [Common Misconceptions](#13-common-misconceptions)

---

## 1. What Is Google ADK?

**Google ADK (Agent Development Kit)** is Google's open-source Python framework for building AI agents, released in early 2025. It provides a production-grade, opinionated structure for:

- Defining agents with tools
- Managing agent sessions and memory
- Integrating with MCP servers
- Running agents with proper lifecycle management
- Building multi-agent systems

### ADK in the AI Ecosystem

```
AI AGENT FRAMEWORKS (2025):

┌──────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                       │
│  LangGraph (cycles, state machines, multi-agent workflows)   │
└──────────────────────────────────────────────────────────────┘

┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   GOOGLE ADK    │  │  OPENAI AGENTS  │  │   LANGCHAIN     │
│                 │  │  (Swarm, etc.)  │  │   AGENTS        │
│ Framework for   │  │                 │  │                 │
│ production      │  │ OpenAI-centric  │  │ General         │
│ agents          │  │ agent patterns  │  │ purpose         │
│                 │  │                 │  │                 │
│ Best with:      │  │ Best with:      │  │ Best with:      │
│ MCP + tool-use  │  │ GPT models      │  │ Any model       │
└────────┬────────┘  └─────────────────┘  └─────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                     MODEL LAYER                             │
│  OpenAI / Gemini / other provider-supported models         │
└─────────────────────────────────────────────────────────────┘
```

### Why ADK Matters

Google ADK represents Google's vision for how production agents should be built:
1. **Standardized structure** — consistent patterns across teams
2. **Built-in MCP support** — first-class MCP tool integration
3. **Session management** — agents remember conversations
4. **Multi-agent** — agents can delegate to sub-agents
5. **Deployment-ready** — designed to run on Google Cloud

---

## 2. ADK vs Building From Scratch

Let's compare what you'd write without ADK vs with ADK.

### Without ADK (From Scratch)

```python
# You have to build EVERYTHING yourself

import json
import asyncio
from openai import AsyncOpenAI  # or any LLM client

class AgentFromScratch:
    def __init__(self):
        self.client = AsyncOpenAI()
        self.conversation_history = []
        self.tools = {}
        self.session_data = {}  # you implement this

    def register_tool(self, name: str, func, schema: dict):
        self.tools[name] = {"func": func, "schema": schema}

    async def run(self, user_message: str) -> str:
        self.conversation_history.append({"role": "user", "content": user_message})

        while True:
            # Call LLM
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=self.conversation_history,
                tools=[t["schema"] for t in self.tools.values()]
            )

            choice = response.choices[0]

            # Check if done
            if choice.finish_reason == "stop":
                answer = choice.message.content
                self.conversation_history.append({"role": "assistant", "content": answer})
                return answer

            # Handle tool calls
            if choice.finish_reason == "tool_calls":
                self.conversation_history.append(choice.message)

                for tool_call in choice.message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    # Execute the tool (you implement all error handling)
                    try:
                        result = await self.tools[tool_name]["func"](**tool_args)
                    except Exception as e:
                        result = {"error": str(e)}

                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })

    # You also need to implement:
    # - Session persistence
    # - Memory management
    # - Multi-agent delegation
    # - MCP integration
    # - Streaming
    # - Error recovery
    # - Observability
```

### With ADK

```python
# ADK handles all the infrastructure

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# 1. Define your tools (ADK converts these to LLM-compatible format)
def get_market_price(address: str) -> dict:
    """Get market price for a property."""
    return {"list_price": 485000, "estimated_value": 462000}

# 2. Create the agent (one clean definition)
agent = LlmAgent(
    name="buyer_agent",
    model="openai/gpt-4o",
    description="A real estate buyer agent",
    instruction="You are a buyer agent. Your goal is to purchase the property at the best price.",
    tools=[FunctionTool(get_market_price)]
    # ADK handles: conversation history, tool calling loop, error handling
)

# 3. Run it
session_service = InMemorySessionService()
runner = Runner(agent=agent, app_name="negotiation", session_service=session_service)
# ADK handles: sessions, memory, streaming, multi-turn conversations
```

**The difference**: ADK turns ~100 lines of boilerplate into ~15 lines of agent definition.

---

## 3. Core Components

ADK has five core components that work together:

```
┌──────────────────────────────────────────────────────────────────┐
│                     YOUR APPLICATION                             │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                      RUNNER                                      │
│  Orchestrates agent execution. Takes user messages,              │
│  invokes agents, returns responses. Main entry point.            │
└────────┬────────────────────────────────────────────┬────────────┘
         │                                            │
         ▼                                            ▼
┌─────────────────────┐                   ┌──────────────────────┐
│     AGENT           │                   │   SESSION SERVICE    │
│                     │                   │                      │
│  LlmAgent:          │                   │  Manages state       │
│  • model            │                   │  across turns.       │
│  • instruction      │                   │  Options:            │
│  • tools            │◄──────────────────│  • InMemory          │
│  • sub_agents       │    session state  │  • Vertex AI         │
│                     │                   │  • Custom            │
└──────────┬──────────┘                   └──────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                         TOOLS                                    │
│                                                                  │
│  FunctionTool    MCPToolset    AgentTool    BuiltInTools          │
│  (Python func)   (MCP server) (sub-agent)  (code exec, etc.)     │
└──────────────────────────────────────────────────────────────────┘
```

### Component 1: Agent (LlmAgent)

```python
from google.adk.agents import LlmAgent

agent = LlmAgent(
    # Identity
    name="buyer_agent",                    # Unique identifier
    description="Real estate buyer",       # For sub-agent discovery

    # Intelligence
    model="openai/gpt-4o",                # Provider-style model id in this workshop
    instruction="""
        You are a buyer agent representing a client who wants to purchase
        742 Evergreen Terrace, Austin, TX 78701.

        Your client's constraints:
        - Maximum budget: $460,000
        - Wants inspection contingency
        - Can close in 30-45 days

        Your strategy:
        1. Always check market data before making offers
        2. Start at 12% below asking price
        3. Increase offers in 2-3% increments
        4. Walk away if seller won't go below $460,000
    """,

    # Capabilities
    tools=[pricing_tool, discount_tool],   # Tools this agent can use
    sub_agents=[research_agent],           # Agents this agent can delegate to

    # Behavior
    output_key="buyer_response",           # Key for storing output in session
)
```

### Component 2: Runner

```python
from google.adk.runners import Runner

runner = Runner(
    agent=root_agent,              # The top-level agent
    app_name="real_estate_nego",   # Application identifier
    session_service=session_service
)

# Running the agent
async def run_agent(message: str, session_id: str, user_id: str):
    from google.adk.types import Content, Part

    content = Content(parts=[Part(text=message)])

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content
    ):
        # Stream events
        if event.is_final_response() and event.content:
            return event.content.parts[0].text
```

### Component 3: Session Service

```python
from google.adk.sessions import InMemorySessionService

# Development: in-memory (lost on restart)
session_service = InMemorySessionService()

# Create a session
session = await session_service.create_session(
    app_name="real_estate_nego",
    user_id="user_001",
    session_id="neg_001",
    state={"initial_budget": 460000}  # Initial state
)

# Get existing session
session = await session_service.get_session(
    app_name="real_estate_nego",
    user_id="user_001",
    session_id="neg_001"
)
```

---

## 4. Agent Types in ADK

### LlmAgent (Most Common)

The standard agent type. Uses a provider-supported LLM for reasoning.

```python
from google.adk.agents import LlmAgent

buyer = LlmAgent(
    name="buyer",
    model="openai/gpt-4o",
    instruction="...",
    tools=[...]
)
```

### SequentialAgent

Runs a list of sub-agents in order. Useful for pipeline workflows.

```python
from google.adk.agents import SequentialAgent

research_pipeline = SequentialAgent(
    name="research_pipeline",
    description="Research pipeline for property analysis",
    sub_agents=[
        market_research_agent,    # Runs first
        comparable_analysis_agent, # Runs second
        recommendation_agent,     # Runs third
    ]
)
```

### ParallelAgent

Runs sub-agents concurrently. Useful when tasks are independent.

```python
from google.adk.agents import ParallelAgent

parallel_research = ParallelAgent(
    name="parallel_research",
    description="Run multiple research tasks concurrently",
    sub_agents=[
        property_value_agent,    # Runs simultaneously
        neighborhood_agent,      # Runs simultaneously
        market_trend_agent,      # Runs simultaneously
    ]
    # All three run at the same time — much faster than sequential!
)
```

### LoopAgent

Runs a sub-agent in a loop until a condition is met.

```python
from google.adk.agents import LoopAgent

negotiation_loop = LoopAgent(
    name="negotiation_loop",
    description="Negotiation loop until agreement or max rounds",
    sub_agents=[negotiation_round_agent],
    max_iterations=5,  # Our max_rounds = 5
)
```

In this repo, orchestration for Module 4 is handled by the HTTP A2A runner (`m4_adk_multiagents/a2a_protocol_http_orchestrator.py`), where buyer/seller turns are coordinated over networked A2A transport.

Other orchestration patterns are still valid depending on use case:
- `SequentialAgent`: pipeline steps like `research → validate → recommend`
- `ParallelAgent`: independent fan-out tasks like `market analysis` and `risk analysis`
- `LlmAgent` with `sub_agents`: dynamic routing when the model chooses which specialist to invoke
- `BaseAgent` subclass with `_run_async_impl`: fully custom orchestration logic

---

## 5. Tool Integration in ADK

ADK supports multiple tool types that can all be mixed in a single agent.

### FunctionTool (Python Functions)

```python
from google.adk.tools import FunctionTool

def check_buyer_budget(proposed_price: float, buyer_budget: float) -> dict:
    """
    Check if a proposed price is within the buyer's budget.

    Args:
        proposed_price: The price being considered
        buyer_budget: The buyer's maximum budget

    Returns:
        Budget analysis with recommendation
    """
    difference = proposed_price - buyer_budget
    within_budget = proposed_price <= buyer_budget

    return {
        "within_budget": within_budget,
        "difference": abs(difference),
        "recommendation": "Proceed" if within_budget else "Walk away or counter lower",
        "remaining_budget": buyer_budget - proposed_price if within_budget else 0
    }

# Wrap as ADK tool
budget_tool = FunctionTool(check_buyer_budget)
# ADK automatically generates JSON schema from the docstring and type hints
```

### Built-in Tools

ADK provides several built-in tools:

```python
from google.adk.tools.built_in import (
    google_search,        # Google Search
    code_execution,       # Execute Python code
    vertex_ai_search,     # Search Vertex AI data stores
)

agent = LlmAgent(
    name="research_agent",
    model="openai/gpt-4o",
    tools=[google_search, code_execution]  # Built-in tools, no configuration needed
)
```

### AgentTool (Agent-as-Tool)

One agent can use another agent as a tool:

```python
from google.adk.tools import AgentTool

# Define a specialist agent
property_research_agent = LlmAgent(
    name="property_research",
    model="openai/gpt-4o",
    instruction="Research properties and provide detailed analysis.",
    tools=[pricing_mcp_tool, google_search]
)

# Use specialist as a tool in main agent
buyer_agent = LlmAgent(
    name="buyer",
    model="openai/gpt-4o",
    instruction="You are a buyer agent. Use property_research when you need market data.",
    tools=[
        AgentTool(agent=property_research_agent),  # Delegate to specialist
        budget_tool,
        offer_tool,
    ]
)
```

---

## 6. MCP Integration in ADK

This is one of ADK's most powerful features — first-class MCP support via `MCPToolset`.

### Using stdio MCP Servers

```python
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters

async def create_buyer_with_mcp():
    """Create a buyer agent with MCP tools from our pricing server."""

    # Connect to our pricing MCP server
    pricing_toolset = MCPToolset(
        connection_params=StdioServerParameters(
            command="python",
            args=["m2_mcp/pricing_server.py"],
            # env={"SOME_API_KEY": "..."}  # Pass env vars to the MCP server
        )
    )

    # Connect to GitHub's MCP server (for market research)
    github_toolset = MCPToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GITHUB_TOKEN"]}
        )
    )

    # Initialize tools from both servers
    # ADK handles the connection lifecycle
    async with pricing_toolset, github_toolset:
        pricing_tools = await pricing_toolset.get_tools()
        github_tools = await github_toolset.get_tools()

        agent = LlmAgent(
            name="buyer_agent",
            model="openai/gpt-4o",
            instruction="You are a real estate buyer...",
            tools=[*pricing_tools, *github_tools]
            # Agent now has access to ALL tools from BOTH MCP servers!
        )

        return agent
```

### Using SSE MCP Servers

```python
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseServerParams

# Start pricing server in SSE mode first:
# python m2_mcp/pricing_server.py --sse --port 8001

pricing_toolset = MCPToolset(
    connection_params=SseServerParams(
        url="http://localhost:8001/sse"
    )
)
```

### How ADK + MCP Works Together

```
┌─────────────────────────────────────────────────────────────────┐
│                    BUYER AGENT (ADK LlmAgent)                  │
│                                                                 │
│  Instruction: "You are a buyer agent for 742 Evergreen..."      │
│  Model: openai/gpt-4o                                            │
│                                                                 │
│  Available Tools (from MCP):                                    │
│    • get_market_price(address, property_type)                   │
│    • calculate_discount(base_price, market_condition)           │
│    • [auto-discovered from MCP server]                          │
│                                                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ When the model decides to call a tool:
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MCPToolset                                 │
│                                                                 │
│  Receives: {"tool": "get_market_price",                         │
│             "args": {"address": "742 Evergreen..."}}            │
│                                                                 │
│  Translates to MCP protocol:                                    │
│  {"method": "tools/call", "params": {"name": "get_market_price" │
│   "arguments": {"address": "742 Evergreen..."}}}                │
│                                                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │ stdio/SSE transport
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PRICING MCP SERVER                             │
│                  (pricing_server.py)                            │
│                                                                 │
│  Executes: get_market_price("742 Evergreen...", "single_family") │
│  Returns:  {"list_price": 485000, "estimated_value": 462000...} │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Session and Memory Management

ADK has a sophisticated session system that enables agents to maintain state across turns.

### Session State

```python
# Session state persists across multiple agent calls in the same session
session = await session_service.create_session(
    app_name="negotiation",
    user_id="buyer_001",
    session_id="neg_session_001",
    state={
        "round_number": 0,
        "current_offer": 425000,
        "negotiation_history": [],
        "buyer_budget": 460000,
    }
)

# State is accessible within agent via context
# And can be updated between turns
```

### Memory Types in ADK

```
SHORT-TERM MEMORY (within a session):
  • Conversation history (all messages in this session)
  • Tool call results (what tools returned)
  • Session state (dict you can read/write)
  • Managed automatically by ADK Runner

LONG-TERM MEMORY (across sessions):
  • Requires VertexAI Memory Bank or custom implementation
  • Agent can "remember" things from previous sessions
  • Example: "This buyer previously walked away at $458K"

IN-CONTEXT MEMORY (within one turn):
  • The agent's current context window
  • All messages from this turn's conversation
  • Tool results from this turn
```

### Accessing Session State in Tools

```python
from google.adk.tools.tool_context import ToolContext

def update_negotiation_round(
    new_offer: float,
    tool_context: ToolContext  # ADK injects this automatically
) -> dict:
    """
    A tool that also updates session state.
    ADK passes ToolContext as a special parameter — don't include in schema.
    """
    # Read from session state
    current_round = tool_context.state.get("round_number", 0)
    history = tool_context.state.get("negotiation_history", [])

    # Update session state
    tool_context.state["round_number"] = current_round + 1
    tool_context.state["current_offer"] = new_offer
    tool_context.state["negotiation_history"] = history + [{
        "round": current_round + 1,
        "offer": new_offer
    }]

    return {
        "round": current_round + 1,
        "offer": new_offer,
        "history_length": len(history) + 1
    }
```

---

## 8. The Agent Lifecycle

Understanding the ADK agent lifecycle helps debug production issues.

```
1. INITIALIZATION
   ─────────────────
   • Agent is created with LlmAgent(...)
   • Tools are registered
   • MCP connections established (if MCPToolset used)
   • Session service is set up

2. SESSION CREATION
   ──────────────────
   • session_service.create_session(...)
   • Initial state is stored
   • Session ID is generated

3. TURN START
   ────────────
   • runner.run_async(user_id, session_id, new_message)
   • ADK loads session state
   • ADK assembles context (system prompt + history + state)

4. AGENT REASONING LOOP
   ──────────────────────
    • ADK sends assembled context to the model
    • The model returns either:
     a) Final text response → go to step 6
     b) Tool call request → go to step 5

5. TOOL EXECUTION
   ─────────────────
    • ADK receives tool call from the model
   • ADK validates arguments against schema
   • ADK executes the tool function
   • ADK adds result to conversation context
   • Go back to step 4 (another LLM call with tool result)

6. TURN END
   ──────────
   • Final response is assembled
   • Conversation history is updated in session
   • Session state is saved
   • Events are emitted to the caller

7. CLEANUP
   ─────────
   • MCP connections closed (if context manager used)
   • Runner disposes resources (on shutdown)
```

---

## 9. Multi-Agent in ADK

ADK supports multi-agent systems through sub-agents and agent tools.

### Pattern 1: Hierarchical Sub-Agents

```python
# Specialist agents
property_researcher = LlmAgent(
    name="property_researcher",
    model="openai/gpt-4o",
    description="Researches property market data and comparables",
    tools=[pricing_mcp_tools]
)

legal_advisor = LlmAgent(
    name="legal_advisor",
    model="openai/gpt-4o",
    description="Reviews contract terms and conditions",
    tools=[legal_database_tool]
)

# Coordinator agent
buyer_coordinator = LlmAgent(
    name="buyer_coordinator",
    model="openai/gpt-4o",
    instruction="""
        You coordinate the real estate purchase process.
        Delegate to specialist agents:
        - Use property_researcher for market data
        - Use legal_advisor for contract questions
        Make final negotiation decisions yourself.
    """,
    sub_agents=[property_researcher, legal_advisor]
)
```

### Pattern 2: Adversarial Multi-Agent (Our Simulator)

```python
# Two LlmAgents run independently, coordinated by the application

buyer_agent = LlmAgent(
    name="buyer",
    model="openai/gpt-4o",
    instruction="You are a buyer agent. Goal: buy low.",
    tools=[pricing_tools]
)

seller_agent = LlmAgent(
    name="seller",
    model="openai/gpt-4o",
    instruction="You are a seller agent. Goal: sell high.",
    tools=[pricing_tools, inventory_tools]
)

# Application coordinates them
class NegotiationCoordinator:
    def __init__(self):
        self.buyer_runner = Runner(agent=buyer_agent, ...)
        self.seller_runner = Runner(agent=seller_agent, ...)

    async def run_round(self, round_num: int, last_counter: str) -> tuple[str, str]:
        buyer_offer = await self.run_agent(self.buyer_runner, last_counter)
        seller_counter = await self.run_agent(self.seller_runner, buyer_offer)
        return buyer_offer, seller_counter
```

---

### Communication Mechanisms Between ADK Agents

> Source: [Google ADK — Multi-Agent Systems](https://google.github.io/adk-docs/agents/multi-agents/)

ADK provides three distinct ways for agents to communicate. Choosing the right one is an architectural decision:

#### 1. Shared Session State (Passive / Asynchronous)

The simplest pattern: agents read and write to `session.state`. No direct calls between agents — they just share a dictionary.

```python
# Agent 1 writes a result to session state (via output_key)
buyer_agent = LlmAgent(
    name="buyer",
    model="openai/gpt-4o",
    instruction="Research the property and record your offer.",
    output_key="buyer_offer"   # LlmAgent auto-writes final response here
)

# Agent 2 reads it via template substitution
seller_agent = LlmAgent(
    name="seller",
    model="openai/gpt-4o",
    instruction="The buyer has offered {buyer_offer}. Respond with a counter-offer.",
    output_key="seller_counter"
)
```

**Best for**: Sequential pipelines where Agent A's output feeds Agent B's input. Low coupling, easy to test.

#### 2. LLM-Driven Delegation (Dynamic / Transfer)

An `LlmAgent` can dynamically invoke another agent via a generated function call: `transfer_to_agent(agent_name='target')`. The ADK framework intercepts this, locates the target agent via `find_agent()`, and switches execution context.

```python
# The coordinator dynamically delegates based on what's needed
coordinator = LlmAgent(
    name="coordinator",
    model="openai/gpt-4o",
    instruction="""
        You coordinate property research.
        - Use property_researcher for MLS data and comparable sales
        - Use legal_advisor for contract questions
        Only delegate, don't do research yourself.
    """,
    sub_agents=[property_researcher, legal_advisor]
    # The LLM decides WHEN and WHO to delegate to — no hardcoded routing
)
```

**Key requirement**: Sub-agents need clear `description` attributes so the coordinator's LLM can make intelligent routing decisions.

**Best for**: Dynamic workflows where the routing logic is complex or data-dependent and the LLM is better at deciding than hardcoded rules.

#### 3. Explicit Invocation (AgentTool)

Wrap an agent in `AgentTool` and add it to a parent agent's `tools` list. The parent LLM explicitly calls the sub-agent like a function call.

```python
from google.adk.tools import AgentTool

# Sub-agent is a specialist
valuation_agent = LlmAgent(
    name="valuation_specialist",
    description="Provides detailed property valuations using MLS data",
    tools=[pricing_mcp_tool, comparable_sales_tool]
)

# Parent uses sub-agent as a tool — explicit, not dynamic delegation
buyer_agent = LlmAgent(
    name="buyer",
    instruction="Use valuation_specialist to get property data before making offers.",
    tools=[
        AgentTool(agent=valuation_agent),  # Sub-agent called as a tool
        offer_submission_tool,
    ]
)
```

**How it works**: When the parent LLM generates a function call to `valuation_specialist`, ADK executes the sub-agent synchronously, captures its response, forwards any state/artifact changes to the parent, and returns the result as a tool output.

**Best for**: When you want predictable, explicit control over when a sub-agent is invoked — as opposed to the LLM deciding when to delegate.

---

### ADK Multi-Agent Patterns

> Source: [Google ADK — Multi-Agent Systems](https://google.github.io/adk-docs/agents/multi-agents/)

| Pattern | Structure | When to Use |
|---|---|---|
| **Coordinator/Dispatcher** | Central LLM routes to specialists via transfer or AgentTool | Complex tasks requiring different expertise per request |
| **Sequential Pipeline** | Agent A output -> Agent B input via `output_key` | Multi-step processes with clear data flow |
| **Parallel Fan-Out/Gather** | `ParallelAgent` fans out to concurrent specialists, synthesizer gathers | Independent research tasks that can run simultaneously |
| **Hierarchical Decomposition** | Multi-level trees of agents breaking down a problem | Very complex tasks that need recursive decomposition |
| **Generator-Critic** | Agent A drafts, Agent B reviews via state | Quality-sensitive output requiring review cycles |
| **Iterative Refinement** | `LoopAgent` with escalation signals until quality threshold met | Negotiation, code generation, writing tasks |

**In our workshop, we use the Adversarial pattern** — two independent agents (buyer and seller) coordinated by the HTTP orchestrator (`m4_adk_multiagents/a2a_protocol_http_orchestrator.py`). This is not a standard ADK hierarchy — the agents don't delegate to each other. The orchestrator loop manages turns and termination over A2A transport.

### Agent Hierarchy Design Principles

From the ADK docs:

1. **Single Parent Constraint**: An agent can only have one parent. Attempting to add the same agent as a sub-agent of two parents raises `ValueError`. This prevents ambiguous ownership.

2. **State-Driven Coordination**: Prefer passive state sharing (via `session.state` / `output_key`) over tight event coupling. Lower coupling = easier to test and debug.

3. **Clear Descriptions for Dynamic Routing**: If using LLM-driven delegation (`transfer_to_agent`), every sub-agent needs a clear `description`. This is what the coordinator's LLM reads to decide who to delegate to.

4. **Escalation Signals for Loop Termination**: In `LoopAgent`, termination is signaled by yielding an Event with `escalate=True`. This is cleaner than hardcoding termination conditions in loop logic.

---

## 10. Model Provider Choices in ADK

ADK supports multiple model providers. In this workshop's Module 4 implementation,
we configure ADK agents with provider-style OpenAI model IDs (for example `openai/gpt-4o`).

### Example Provider-Style IDs

```python
# OpenAI via ADK provider-style id
model = "openai/gpt-4o"

# Other provider-style ids are also possible when configured in your ADK environment
# (for example, Gemini provider ids).
```

### Practical takeaway for this repo

```
Framework layer:   Google ADK (agents, sessions, tools, runners)
Model provider:    OpenAI (configured as openai/gpt-4o)
Tool protocol:     MCP (pricing/inventory servers)
Agent protocol:    A2A (HTTP JSON-RPC transport in Module 4)
```

### API Key Setup for This Workshop

```bash
# Set in environment
export OPENAI_API_KEY="sk-..."

# In Python
import os
os.environ["OPENAI_API_KEY"] = "sk-..."
```

---

## 11. Our ADK Implementation

Here's how our negotiation simulator uses ADK (detailed in `m4_adk_multiagents/`).

### Buyer Agent (ADK Version)

```python
# m4_adk_multiagents/buyer_adk.py — conceptual overview

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams, StdioServerParameters

BUYER_INSTRUCTION_TEMPLATE = f"""
You are a real estate buyer agent for a client purchasing:
Property: 742 Evergreen Terrace, Austin, TX 78701
Type: Single Family, 4BR/3BA, 2,400 sqft

Your client's profile:
- Maximum budget: $460,000 (NEVER exceed this)
- Initial strategy: Offer ~12% below asking price
- Acceptable outcome: Any price at or below $455,000
- Walk-away point: Seller won't go below $460,000

Before making any offer, call your available MCP tools to get market data.

AVAILABLE MCP TOOLS (auto-discovered):
{{tools_section}}

Output your response as JSON:
{{
    "offer_price": <number>,
    "message": "<your message to the seller>",
    "reasoning": "<internal strategy notes>",
    "walk_away": <true/false>
}}
"""

async def create_buyer_agent() -> LlmAgent:
    toolset = MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="python",
                args=["m2_mcp/pricing_server.py"]
            )
        )
    )
    tools = await toolset.get_tools()

    agent = LlmAgent(
        name="buyer_agent",
        model="openai/gpt-4o",
        description="Real estate buyer agent for 742 Evergreen Terrace",
        instruction=BUYER_INSTRUCTION_TEMPLATE.format(
            tools_section="\n".join(f"- {t.name}" for t in tools)
        ),
        tools=tools
    )

    return agent
```

### Seller Agent (ADK Version)

```python
# m4_adk_multiagents/seller_adk.py — conceptual overview

SELLER_INSTRUCTION_TEMPLATE = f"""
You are a real estate seller agent representing the owners of:
Property: 742 Evergreen Terrace, Austin, TX 78701
Listed at: $485,000

Seller's profile:
- Minimum acceptable price: $445,000 (absolute floor)
- Ideal outcome: Close at $465,000 or above
- Property highlights: Renovated kitchen (2023), new roof (2022)

Strategy:
1. Use get_inventory_level() to understand market pressure
2. Use get_minimum_acceptable_price() to confirm your floor price
3. Start counter-offers at $477,000
4. Come down in small increments (1-2% at a time)
5. Never go below $445,000

Leverage your property's upgrades in every counter-offer.
"""
```

---

## 12. ADK vs LangGraph vs Simple Python

Understanding when to use each approach:

```
┌───────────────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Need                      │ Simple Python    │ LangGraph        │ Google ADK       │
├───────────────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Quick prototype           │ ✅ Best          │ ❌ Overkill      │ ❌ Overkill      │
│ Complex state management  │ 🔶 Manual       │ ✅ Best          │ 🔶 Session-based │
│ Cyclic workflows          │ 🔶 Manual while  │ ✅ Native        │ LoopAgent        │
│ MCP tool integration      │ 🔶 Manual client │ 🔶 Via plugins  │ ✅ Native        │
│ Multi-agent coordination  │ 🔶 Manual        │ ✅ Excellent     │ ✅ Sub-agents    │
│ Production deployment     │ ❌ Manual infra  │ ✅ With checkpt  │ ✅ GCP-ready     │
│ Human-in-the-loop         │ ❌ Manual        │ ✅ Native        │ 🔶 Via interrupt │
│ Teaching/workshop         │ ✅ Clearest      │ ✅ Good          │ 🔶 More complex  │
│ Streaming responses       │ 🔶 Manual        │ ✅ Built-in      │ ✅ Built-in      │
│ Session persistence       │ ❌ Manual        │ ✅ Checkpointer  │ ✅ Session svc   │
└───────────────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

### Our Workshop's Approach

We implement both to compare:

1. **Simple Python + LangGraph** (`m3_langgraph_multiagents/`, `m3_langgraph_multiagents/main_langgraph_multiagent.py`)
   - Use when learning the concepts
   - OpenAI GPT-4o
   - MCP via Python client
   - LangGraph for workflow management

2. **Google ADK** (`m4_adk_multiagents/`, `m4_adk_multiagents/a2a_protocol_seller_server.py`)
   - Use when building for production
   - Gemini 2.0 Flash (free tier)
   - MCP via native MCPToolset
   - ADK handles session management
    - Orchestration can be modeled multiple ways (Loop/Sequential/Parallel/router/custom), and this repo's dedicated orchestrator demo uses `LoopAgent` with buyer/seller agents for clarity

---

## 13. Common Misconceptions

### ❌ "ADK only works with Google Cloud"

**Reality**: ADK runs locally with just a Google API key (free tier). You don't need GCP for the workshop. Cloud deployment is optional for production.

### ❌ "ADK replaces LangGraph"

**Reality**: They're complementary. ADK is for defining and running individual agents. LangGraph is for orchestrating complex multi-agent workflows. You can use both together (ADK agents orchestrated by LangGraph).

### ❌ "ADK only works with Gemini"

**Reality**: ADK supports other models via LiteLLM integration. But Gemini has the deepest native integration and best MCP support.

### ❌ "MCPToolset downloads tools from the internet"

**Reality**: MCPToolset connects to MCP servers you specify — either local (stdio) or remote (SSE). It doesn't download or discover tools from any registry automatically.

### ❌ "ADK handles the negotiation logic"

**Reality**: ADK handles infrastructure (sessions, tool calling, streaming). You still define the negotiation strategy in the agent's instruction prompt.

---

## Summary

| Component | Purpose |
|---|---|
| **LlmAgent** | Define agent with model, instruction, tools |
| **Runner** | Execute agents, manage turn lifecycle |
| **SessionService** | Persist conversation state across turns |
| **FunctionTool** | Wrap Python functions as agent tools |
| **MCPToolset** | Connect to MCP servers (stdio or SSE) |
| **AgentTool** | Use one agent as a tool for another |
| **SequentialAgent** | Run sub-agents in order |
| **ParallelAgent** | Run sub-agents concurrently |
| **LoopAgent** | Run sub-agent in a loop |
| **Workshop model id** | openai/gpt-4o |

---

*← [LangGraph Explained](../../m3_langgraph_multiagents/notes/langgraph_explained.md)*
*→ [Exercises](../exercises/exercises.md)*
