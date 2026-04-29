# Google ADK Overview
## Building Production-Grade Agents with Google's Agent Development Kit

See also: [A2A Protocols](a2a_protocols.md) for the protocol layer that lets ADK agents talk to other agents.

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
12. [ADK vs Plain Python](#12-adk-vs-plain-python)
13. [Common Misconceptions](#13-common-misconceptions)

**Part II — ADK Internals**
14. [Workflow Agents in Depth (`SequentialAgent`, `ParallelAgent`, `LoopAgent`)](#14-workflow-agents-in-depth)
15. [`AgentTool` — Treating an Agent as a Function](#15-agenttool--treating-an-agent-as-a-function)
16. [`ToolContext`, Scoped State, and Artifacts](#16-toolcontext-scoped-state-and-artifacts)
17. [Callbacks (`before_model`, `before_tool`, `after_tool`, `after_agent`)](#17-callbacks)
18. [Events, Actions, and Escalation](#18-events-actions-and-escalation)
19. [Authentication and Credentials](#19-authentication-and-credentials)
20. [Agent Discovery — The `adk web` Convention](#20-agent-discovery--the-adk-web-convention)
21. [ADK ↔ A2A Integration](#21-adk--a2a-integration)
22. [Putting It All Together — How the Workshop Uses These](#22-putting-it-all-together)

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
│  ADK workflow agents (Sequential / Parallel / Loop)          │
│  Custom orchestrators built on top of agent frameworks       │
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

The execution engine — processes one turn at a time.

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

The memory store — persists conversation history and state across turns.

**Runner vs Session — the key distinction:**

| | Runner | Session |
|---|---|---|
| What it is | Execution engine — runs one turn | Memory store — persists across all turns |
| Lifespan | Transient (one message in, events out) | Persistent (survives across entire conversation) |
| State | Reads state at start, writes back at end | Holds the state dict |
| Stored in session.db? | No | Yes (`sessions` + `events` tables) |

The Runner is stateless — it processes one message and is done. The Session
is what gives an agent memory. You could run the same Runner against different
sessions (different users, different conversations).

In `adk web`, both are created automatically. You only manage them manually
when writing standalone scripts.

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

In this repo, orchestration for Module 3 is handled by the `negotiation_agents/negotiation/agent.py` `LoopAgent`, which wraps a `SequentialAgent(buyer → seller)`. The buyer and seller communicate via session state (`output_key` / `{placeholder}`).

To see these workflow agents live:
```bash
adk web m3_adk_multiagents/adk_demos/   # demos d04–d06 show sequential/parallel/loop
adk web m3_adk_multiagents/negotiation_agents/   # the full negotiation orchestration
```

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

**In our workshop, we use two patterns:**
- **Declarative agents** (`negotiation_agents/buyer_agent/agent.py`, `seller_agent/agent.py`) — each is a `root_agent = LlmAgent(...)` with MCPToolset
- **Orchestrated negotiation** (`negotiation_agents/negotiation/agent.py`) — a `LoopAgent` wrapping a `SequentialAgent(buyer → seller)` with `after_agent_callback` for termination

### Agent Hierarchy Design Principles

From the ADK docs:

1. **Single Parent Constraint**: An agent can only have one parent. Attempting to add the same agent as a sub-agent of two parents raises `ValueError`. This prevents ambiguous ownership.

2. **State-Driven Coordination**: Prefer passive state sharing (via `session.state` / `output_key`) over tight event coupling. Lower coupling = easier to test and debug.

3. **Clear Descriptions for Dynamic Routing**: If using LLM-driven delegation (`transfer_to_agent`), every sub-agent needs a clear `description`. This is what the coordinator's LLM reads to decide who to delegate to.

4. **Escalation Signals for Loop Termination**: In `LoopAgent`, termination is signaled by yielding an Event with `escalate=True`. This is cleaner than hardcoding termination conditions in loop logic.

---

## 10. Model Provider Choices in ADK

ADK supports multiple model providers. In this workshop's Module 3 implementation,
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
Agent protocol:    A2A (HTTP JSON-RPC transport in Module 3)
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

Here's how our negotiation simulator uses ADK (detailed in `m3_adk_multiagents/`).

### Buyer Agent — Declarative (Idiomatic ADK)

```python
# m3_adk_multiagents/negotiation_agents/buyer_agent/agent.py

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams, StdioServerParameters

root_agent = LlmAgent(
    name="buyer_agent",
    model="openai/gpt-4o",
    description="Real estate buyer agent for 742 Evergreen Terrace, Austin TX.",
    instruction=(
        "You are an expert real estate buyer agent...\n"
        "Maximum budget: $460,000. Call MCP tools before every offer."
    ),
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[_PRICING_SERVER],
                )
            )
        )
    ],
    before_tool_callback=_enforce_buyer_allowlist,
)
```

**Key points:**
- No class, no `__aenter__`/`__aexit__`, no manual Runner — just `root_agent = LlmAgent(...)`
- MCPToolset goes directly in the `tools` list — ADK manages the lifecycle
- `adk web` discovers this agent automatically from the package structure
- `adk web --a2a` serves it as an A2A endpoint with an auto-generated Agent Card

### Seller Agent — Dual MCPToolsets

```python
# m3_adk_multiagents/negotiation_agents/seller_agent/agent.py

root_agent = LlmAgent(
    name="seller_agent",
    model="openai/gpt-4o",
    instruction="...",
    tools=[
        MCPToolset(...)  # pricing server
        MCPToolset(...)  # inventory server — has get_minimum_acceptable_price
    ],
    before_tool_callback=_enforce_seller_allowlist,
)
```

Seller has access to `get_minimum_acceptable_price` — the buyer does not. Same information asymmetry as Module 2, now declarative.

### Negotiation Orchestrator — LoopAgent + SequentialAgent

```python
# m3_adk_multiagents/negotiation_agents/negotiation/agent.py

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent

buyer = LlmAgent(name="buyer", output_key="buyer_offer", ...)
seller = LlmAgent(name="seller", output_key="seller_response",
                  after_agent_callback=_check_agreement, ...)

round = SequentialAgent(name="round", sub_agents=[buyer, seller])
root_agent = LoopAgent(name="negotiation", sub_agents=[round], max_iterations=5)
```

### How to Run

```bash
# Interactive web UI — pick buyer, seller, or negotiation from dropdown
adk web m3_adk_multiagents/negotiation_agents/

# With A2A endpoints (Agent Cards auto-generated)
adk web --a2a m3_adk_multiagents/negotiation_agents/

# ADK demos (9 concept demos in dropdown)
adk web m3_adk_multiagents/adk_demos/
```
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

## 12. ADK vs Plain Python

Understanding when to use each approach:

```
┌───────────────────────────┬──────────────────┬──────────────────┐
│ Need                      │ Plain Python     │ Google ADK       │
├───────────────────────────┼──────────────────┼──────────────────┤
│ Quick prototype           │ ✅ Best          │ 🔶 Some setup    │
│ Complex state management  │ 🔶 Manual        │ ✅ Session-based │
│ Cyclic workflows          │ 🔶 Manual while  │ ✅ LoopAgent     │
│ MCP tool integration      │ 🔶 Manual client │ ✅ Native        │
│ Multi-agent coordination  │ 🔶 Manual        │ ✅ Sub-agents    │
│ Production deployment     │ ❌ Manual infra  │ ✅ GCP-ready     │
│ Human-in-the-loop         │ ❌ Manual        │ 🔶 Via callbacks │
│ Streaming responses       │ 🔶 Manual        │ ✅ Built-in      │
│ Session persistence       │ ❌ Manual        │ ✅ Session svc   │
└───────────────────────────┴──────────────────┴──────────────────┘
```

### Our Workshop's Approach

This workshop uses **Google ADK** (`m3_adk_multiagents/`) as the production-style implementation:

- ADK `LlmAgent` defines buyer and seller
- `MCPToolset` integrates the M2 MCP servers natively
- `Runner` + `InMemorySessionService` manage the per-session conversation state
- ADK workflow agents (`SequentialAgent`, `LoopAgent`) provide bounded multi-agent orchestration
- A2A SDK exposes the seller as an HTTP service so any A2A-compatible client can talk to it

We contrast this with the naive Python baseline in Module 1 (`m1_baseline/`), which shows what you have to build by hand without a framework.

---

## 13. Common Misconceptions

### ❌ "ADK only works with Google Cloud"

**Reality**: ADK runs locally with just a model API key (we use OpenAI in this workshop via `openai/gpt-4o`). You don't need GCP for the workshop. Cloud deployment is optional for production.

### ❌ "ADK only works with Gemini"

**Reality**: ADK supports other models via LiteLLM integration (this workshop uses `openai/gpt-4o`). Gemini has the deepest native integration, but other providers are first-class through the provider-prefixed model id.

### ❌ "MCPToolset downloads tools from the internet"

**Reality**: MCPToolset connects to MCP servers you specify — either local (stdio) or remote (SSE). It doesn't download or discover tools from any registry automatically.

### ❌ "ADK handles the negotiation logic"

**Reality**: ADK handles infrastructure (sessions, tool calling, streaming). You still define the negotiation strategy in the agent's instruction prompt.

---

# Part II — ADK Internals (Phase 2 Deep-Dive)

The first half of this document showed *what ADK is* and the basic
LlmAgent + Runner + Session + MCPToolset + workflow-agent vocabulary.
This half drills into the abstractions you reach for once a single
LlmAgent is no longer enough. Each section has a runnable demo under
[`m3_adk_multiagents/adk_demos/`](../adk_demos/).

---

## 14. Workflow Agents in Depth

ADK ships three workflow agents. They are *not* LlmAgents — they don't
call a model themselves. They orchestrate other agents (which usually
*are* LlmAgents).

### 14.1 `SequentialAgent`

Runs `sub_agents` in declaration order. Each child writes into session
state via its `output_key`; subsequent children can read those values
through `{key}` placeholders in their instruction.

```python
SequentialAgent(name="pipeline", sub_agents=[market_brief, drafter, polisher])
```

Use it for: deterministic pipelines (research → draft → polish).

**Demo:** `m3_adk_multiagents/adk_demos/d04_sequential/agent.py`.

### 14.2 `ParallelAgent`

Runs `sub_agents` concurrently. All children share the same session, so
they each write their own `output_key` into state. After all finish,
state contains every key.

```python
ParallelAgent(name="signals", sub_agents=[schools, comps, inventory])
```

Use it for: independent fan-out research where order doesn't matter.

> ⚠️ **State write conflicts.** ParallelAgent does not merge state across
> children automatically; if two children write to the same key the last
> writer wins. Give each child its own `output_key`.

**Demo:** `m3_adk_multiagents/adk_demos/d05_parallel/agent.py`.

### 14.3 `LoopAgent`

Repeats `sub_agents` either until `max_iterations` is hit or until any
event raises `actions.escalate = True`. The escalation signal is the
loop's only natural stopping condition.

```python
LoopAgent(name="haggle_loop", sub_agents=[haggler], max_iterations=5)
```

In the demo, the haggler's `after_agent_callback` parses the proposed
price and sets `callback_context.actions.escalate = True` once the price
is in the target range.

Use it for: iterate-until-good-enough loops (refine, retry, sample).

**Demo:** `m3_adk_multiagents/adk_demos/d06_loop/agent.py`.

---

## 15. `AgentTool` — Treating an Agent as a Function

`AgentTool(agent=...)` wraps an entire agent and exposes it to *another*
agent as if it were a single function tool. The wrapping agent's
`description` becomes the tool's docstring; its inputs/outputs become the
tool's request/response.

```python
specialist = LlmAgent(name="valuator", description="Estimates fair market value...", ...)
coordinator = LlmAgent(
    name="coordinator",
    instruction="Call the valuator tool when you need a price opinion.",
    tools=[AgentTool(agent=specialist)],
)
```

**Why use AgentTool instead of `sub_agents`?**
- `sub_agents` is for explicit orchestration — the parent decides *when*
  the child runs (via Sequential/Parallel/Loop or explicit transfer).
- `AgentTool` is for *implicit* delegation — the parent's LLM decides
  whether to call the child by reasoning over the tool catalog.

Use AgentTool for "expert hierarchy" patterns where the coordinator may
or may not need a specialist on any given turn.

**Demo:** `m3_adk_multiagents/adk_demos/d07_agent_as_tool/agent.py`.

---

## 16. `ToolContext`, Scoped State, and Artifacts

Any tool function that takes a parameter named `tool_context: ToolContext`
gets ADK's runtime context injected automatically.

```python
def bump_offer_counter(tool_context: ToolContext) -> dict:
    current = tool_context.state.get("user:offer_attempts", 0)
    tool_context.state["user:offer_attempts"] = current + 1
    return {"offer_attempts": current + 1}
```

Through `tool_context` a tool can:

- **Read/write session state**: `tool_context.state[...]`
- **Save/load artifacts** (binary blobs): `await tool_context.save_artifact(...)` / `load_artifact`
- **Influence the run**: `tool_context.actions.escalate = True`,
  `tool_context.actions.transfer_to_agent = "other_agent"`,
  `tool_context.actions.skip_summarization = True`
- **Inspect the call**: `tool_context.function_call_id`, `agent_name`, `invocation_id`

### State scope prefixes

| Prefix     | Lifetime / scope                                              |
|------------|---------------------------------------------------------------|
| (none)     | Bound to the current session.                                 |
| `user:`    | Bound to the `user_id`; survives across sessions.             |
| `app:`     | Bound to the `app_name`; shared across users and sessions.    |
| `temp:`    | Lives only for the current invocation; not persisted.         |

**`user:` vs `app:` in practice:** If Alice and Bob both use the app,
`user:total_offers` has a different value for each (per-buyer). But
`app:negotiations_run` is global — both see the same counter. In `adk web`,
`user_id` defaults to `"user"` so both behave the same in a workshop.
The distinction matters in production with multiple users.

In our agents, `negotiation_agents/buyer_agent/agent.py` uses
`before_tool_callback=_enforce_buyer_allowlist` to scope the buyer's
allowed tools. The seller has a similar allowlist that additionally
permits `get_minimum_acceptable_price`.

**Demo:** `m3_adk_multiagents/adk_demos/d03_sessions_state/agent.py`.

---

## 17. Callbacks

Callbacks are how you plug *policy* into an agent without changing its
instruction. They run synchronously around model and tool calls.

| Callback                   | Fires when                          | Return value semantics                                  |
|----------------------------|-------------------------------------|---------------------------------------------------------|
| `before_agent_callback`    | before the agent's first model turn | None = continue; `Content` = use this instead of running the agent |
| `after_agent_callback`     | after the agent's last event        | None = continue; `Content` = replace final response     |
| `before_model_callback`    | before each LLM request             | None = continue; mutate `llm_request` in place          |
| `after_model_callback`     | after each LLM response             | None = continue; return `LlmResponse` to replace        |
| `before_tool_callback`     | before each tool call               | None = run the tool; `dict` = short-circuit with this result |
| `after_tool_callback`      | after each tool returns             | None = use the tool's result; return value replaces it   |

Each callback receives a `CallbackContext` (or `ToolContext` for tool
callbacks) with the same state/artifact/actions surface as `ToolContext`.

In our agents, `negotiation_agents/buyer_agent/agent.py` and
`negotiation_agents/seller_agent/agent.py` use `before_tool_callback`
to enforce a tool allowlist — the buyer can never accidentally call the
seller-private inventory tools, even if the model tries.

**Demo:** `m3_adk_multiagents/adk_demos/d08_callbacks/agent.py` wires
`before_model` (PII redaction), `before_tool` (allowlist), and
`after_tool` (logging) into a single agent.

---

## 18. Events, Actions, and Escalation

`Runner.run_async(...)` yields a stream of `Event` objects. Each event
carries:

- `author` — which agent produced it (an LlmAgent name, or workflow agent name).
- `content` — `google.genai.types.Content` with parts (text, function_call,
  function_response).
- `actions` — an `EventActions` with side-effect fields the runner honors:
  `state_delta`, `artifact_delta`, `escalate`, `transfer_to_agent`,
  `skip_summarization`, `requested_auth_configs`.
- `is_final_response()` — convenience predicate: this is the last text
  the agent will emit for the current invocation.

**Escalation** is how you break out of containers. Setting
`actions.escalate = True` tells the nearest parent workflow agent
(`LoopAgent` is the typical target) to stop iterating after this event.

State deltas attached to events become the canonical record of how state
changed during the invocation — the `negotiation_agents/negotiation/agent.py`
uses `output_key` and `after_agent_callback` to track round state.

---

## 19. Authentication and Credentials

ADK agents often need credentials to call external services (MCP servers,
APIs, OAuth-protected endpoints). ADK provides a layered auth model.

### Tool-level credential injection

Tools can receive credentials through `ToolContext`. When a tool needs
authentication, it can read from session state or environment:

```python
def call_paid_api(query: str, tool_context: ToolContext) -> dict:
    # Read API key from session state (injected at session creation)
    api_key = tool_context.state.get("app:paid_api_key")
    # Or from environment (simpler, less dynamic)
    api_key = os.environ.get("PAID_API_KEY")
    ...
```

### before_tool_callback for auth enforcement

The `before_tool_callback` pattern used in our buyer/seller agents is
also how you enforce *authorization* — which tools a given agent is
allowed to call, regardless of what the MCP server exposes:

```python
def _enforce_buyer_allowlist(tool, args, tool_context):
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized"}
    return None
```

### CredentialService (advanced)

ADK ships an `InMemoryCredentialService` (experimental) for managing
OAuth flows. When `adk web` starts, it creates one automatically. For
production, implement a custom `BaseCredentialService` backed by a
secrets manager.

### MCP server credentials

MCPToolset with `StdioServerParameters` can pass environment variables
to the spawned server process — this is how you inject API keys:

```python
MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["my_server.py"],
            env={"API_KEY": os.environ["API_KEY"]},  # injected
        )
    )
)
```

### A2A-level auth

When using `adk web --a2a`, A2A endpoints inherit whatever HTTP auth
the deployment provides. The Agent Card declares supported auth schemes.
For local development, no auth is configured.

---

## 20. Agent Discovery — The `adk web` Convention

`adk web` discovers agents through a specific directory convention.
Understanding this convention is essential for creating new agents.

### The package structure

```
my_agents/                    # ← pass this directory to adk web
    agent_one/                # each subfolder = one agent
        __init__.py           # must contain: from . import agent
        agent.py              # must define: root_agent = LlmAgent(...)
        agent.json            # OPTIONAL: required only for --a2a (Agent Card definition)
    agent_two/
        __init__.py
        agent.py
        agent.json
```

### Discovery rules

1. `adk web my_agents/` scans each immediate subfolder
2. Each subfolder must be a valid Python package (`__init__.py`)
3. The `__init__.py` must import the `agent` module
4. The `agent.py` must define a module-level variable named `root_agent`
5. The `root_agent` can be any ADK agent: `LlmAgent`, `SequentialAgent`, `LoopAgent`, etc.

### What `adk web` creates automatically

For each discovered agent, `adk web` creates:
- A `Runner` instance
- An `InMemorySessionService` (or database-backed via `--session_service_uri`)
- A web UI entry in the dropdown
- Session management and conversation history

### With `--a2a`: additional A2A infrastructure

Adding the `--a2a` flag also creates for each agent **that has an `agent.json` file**:
- An **Agent Card** at `/a2a/<agent_name>/.well-known/agent-card.json`
  (loaded from `agent.json` in the agent folder)
- A **JSON-RPC endpoint** at `POST /a2a/<agent_name>/`
  (handles `message/send` and `message/stream`)
- A **Task store** for managing task lifecycle

**`agent.json` is required for `--a2a`**. Without it, the agent will appear
in the `adk web` chat UI but will NOT get A2A endpoints. The file defines
the Agent Card: name, description, capabilities, skills, URL.

```bash
# Interactive only
adk web m3_adk_multiagents/negotiation_agents/

# Interactive + A2A endpoints
adk web --a2a m3_adk_multiagents/negotiation_agents/
```

### Our workshop structure

```
negotiation_agents/
    buyer_agent/    → root_agent = LlmAgent(name="buyer_agent", ...)
    seller_agent/   → root_agent = LlmAgent(name="seller_agent", ...)
    negotiation/    → root_agent = LoopAgent(name="negotiation", ...)

adk_demos/
    d01_basic_agent/  → root_agent = LlmAgent(name="basic_agent", ...)
    d02_mcp_tools/    → root_agent = LlmAgent(name="mcp_tools_agent", ...)
    ...               → 9 total demo agents
```

**Demo:** `adk web m3_adk_multiagents/adk_demos/` — 9 agents in the dropdown.

---

## 21. ADK ↔ A2A Integration

ADK and A2A are complementary. ADK builds agents; A2A exposes them as
network services. The bridge is `adk web --a2a`.

### How it works

```
agent.py                          adk web --a2a
─────────                         ─────────────────────────
root_agent = LlmAgent(            Reads root_agent →
    name="seller_agent",            Generates Agent Card:
    description="...",                name: "seller_agent"
    tools=[MCPToolset(...)],          description: "..."
)                                     skills: [from tools]
                                      url: "http://host:port/seller_agent"

                                    Serves:
                                      GET /.well-known/agent-card.json
                                      POST / (message/send JSON-RPC)
                                      POST / (message/stream SSE)
```

### The agent as MCP client AND A2A server

A single ADK agent commonly plays both roles:

```
                    ┌──────────────────────────────┐
                    │     seller_agent (ADK)        │
                    │                               │
 A2A client  ──────►  A2A server (auto by adk web) │
 (buyer demo)       │                               │
                    │  LlmAgent                     │
                    │    ├── MCPToolset → pricing    │──── MCP client
                    │    └── MCPToolset → inventory  │──── MCP client
                    └──────────────────────────────┘
```

- **Inbound**: A2A messages arrive via JSON-RPC
- **Processing**: LlmAgent reasons with GPT-4o, calls MCP tools
- **Outbound**: Response sent back as A2A Task result

### No custom server code needed

Compare with the traditional approach (what we deleted):

| Aspect | Old approach | New approach |
|--------|-------------|-------------|
| Server code | Manual server code | 0 lines (`adk web --a2a`) |
| Agent Card | Manually constructed `AgentCard(...)` | Auto-generated |
| Request handling | Custom `AgentExecutor` subclass | Built into ADK |
| Task lifecycle | Manual `TaskUpdater` calls | Automatic |
| MCP lifecycle | `__aenter__`/`__aexit__` context managers | Managed by MCPToolset |

### When you need a custom server

`adk web --a2a` covers most cases. You'd write a custom A2A server when:
- You need custom HTTP middleware (rate limiting, custom auth)
- You need to transform messages before they reach the agent
- You need to run multiple agents behind a single endpoint with custom routing
- You need to integrate with a non-ADK agent implementation

**Demos:**
- `adk_demos/a2a_10_wire_lifecycle.py` — client talking to `adk web --a2a`
- `adk_demos/a2a_11_context_threading.py` — multi-turn via contextId
- `adk_demos/a2a_12_parts_and_artifacts.py` — multi-part messages
- `adk_demos/a2a_13_streaming.py` — message/stream SSE events

---

## 22. Putting It All Together

These pieces land in our module as follows:

| Concept                      | Where it lives in the workshop                                  |
|------------------------------|-----------------------------------------------------------------|
| `LlmAgent`                   | `negotiation_agents/buyer_agent/agent.py`, `seller_agent/agent.py` |
| `MCPToolset` (multiple)      | Seller connects pricing + inventory MCPToolsets                  |
| `before_tool_callback` allowlist | `_enforce_buyer_allowlist`, `_enforce_seller_allowlist`       |
| `SequentialAgent` + `LoopAgent` | `negotiation_agents/negotiation/agent.py`                     |
| `output_key` state passing   | buyer writes `buyer_offer`, seller reads `{buyer_offer}`         |
| `after_agent_callback` escalation | Seller callback checks for ACCEPT, breaks the loop          |
| Workflow agents (Seq/Par/Loop) | `adk_demos/d04–d06`                                            |
| `AgentTool`                  | `adk_demos/d07_agent_as_tool`                                    |
| `ToolContext` scoped state   | `adk_demos/d03_sessions_state`                                   |
| Callbacks (PII / allowlist / logging) | `adk_demos/d08_callbacks`                               |
| Event stream + state deltas  | `adk_demos/d09_event_stream`                                     |
| Agent discovery convention   | `__init__.py` + `agent.py` + `root_agent` in every package       |
| ADK ↔ A2A bridge             | `adk web --a2a negotiation_agents/`                              |

Run the demos as a kit: each one shows *one* ADK abstraction in
isolation, then the negotiation agents show them composed.

```bash
# Demos (pick from dropdown)
adk web m3_adk_multiagents/adk_demos/

# Full agents (buyer, seller, negotiation)
adk web m3_adk_multiagents/negotiation_agents/

# A2A endpoints (Agent Cards auto-generated)
adk web --a2a m3_adk_multiagents/negotiation_agents/
```



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

*← [A2A Protocols](a2a_protocols.md)*
