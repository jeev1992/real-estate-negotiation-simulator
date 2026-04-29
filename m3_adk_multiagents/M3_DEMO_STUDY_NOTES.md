# Module 3 — Demo Walkthrough & Concept Notes

Personal study notes captured while running each demo hands-on.

---

## Demo 01 — Basic LlmAgent (`d01_basic_agent`)

**File:** `adk_demos/d01_basic_agent/agent.py` (~40 lines)

### What it teaches
The simplest possible ADK agent: one `LlmAgent` with one function tool.

### Key code elements

```python
root_agent = LlmAgent(
    name="basic_agent",              # unique identifier — shows in adk web dropdown
    model="openai/gpt-4o",           # provider/model format (routed via LiteLLM)
    description="...",               # used by other agents for discovery/routing
    instruction="...",               # system prompt — tells the LLM how to behave
    tools=[get_quick_estimate],      # plain Python function — ADK wraps it automatically
)
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`LlmAgent`** | The core ADK building block. Combines model + instruction + tools into one declarative object |
| **`root_agent`** | The magic variable name that `adk web` looks for when discovering agents |
| **Function tools** | Any Python function with type hints + docstring becomes a tool. ADK generates the JSON schema from the signature. The LLM sees it as a callable function |
| **`model="openai/gpt-4o"`** | Provider-prefixed model ID. `openai/` tells LiteLLM to route to OpenAI's API. Without the prefix, ADK tries Google's native Gemini integration |
| **`description`** | Not shown to the user — used by other agents (in multi-agent setups) to decide whether to delegate to this agent |
| **`instruction`** | The system prompt. This is where you define personality, strategy, output format, and tool usage guidance |
| **Tool decision** | The LLM decides WHETHER and WHEN to call tools. The instruction nudges it ("use get_quick_estimate"), but the model makes the final call |

### What happens under the hood

```
User: "What is 742 Evergreen Terrace worth?"
  → ADK sends to GPT-4o with system prompt + tool schemas
  → GPT-4o returns: function_call(get_quick_estimate, {address: "742 Evergreen Terrace"})
  → ADK executes the Python function locally
  → ADK feeds the result back to GPT-4o
  → GPT-4o produces final text answer
  → ADK returns it to the UI
```

### session.db after running

| Table | Contents |
|-------|----------|
| **sessions** | 1 row: `app_name=d01_basic_agent`, `user_id=user`, state has only `__session_metadata__` (display name for the UI session dropdown) |
| **events** | 6 rows for a 2-turn conversation: user→LLM→(no tool)→response, user→LLM→tool_call→tool_result→LLM→response |
| **app_states** | Empty — no `app:` prefixed state keys written |
| **user_states** | Empty — no `user:` prefixed state keys written |

### ADK Web UI elements observed

| UI Element | What it showed |
|------------|---------------|
| **Agent dropdown** (top-left) | `d01_basic_agent` selected |
| **Info tab** | Agent config: model, system_instruction, tool schemas (get_quick_estimate with address parameter) |
| **Events tab** (right panel) | Conversation: user messages (blue), agent responses (dark), tool call badges (⚡ → ✓) |
| **Events tab** (left panel) | Event inspector — 6 internal events for this session. Click any to see raw JSON |
| **State tab** | Only `__session_metadata__` — this demo doesn't use session state |
| **Streaming toggle** | When on, tokens stream in. When off, full response appears at once |

### Key teaching points for class

1. **"This is the hello world of ADK."** One agent, one tool, ~40 lines.
2. **The LLM is not scripted.** You don't tell it "call get_quick_estimate on line 3." You say "use this tool when asked about properties" and the model decides.
3. **The tool is a plain Python function.** No decorator, no schema file — ADK reads the type hints and docstring.
4. **`root_agent` is the convention.** Name it anything else and `adk web` won't find it.
5. **Compare to M2:** In `github_agent_client.py`, you hand-wrote the tool loop (call LLM → check for tool_calls → execute → feed back). Here, ADK does all of that. You just declare `tools=[fn]`.

---

## Demo 02 — MCP Tools (`d02_mcp_tools`)

**File:** `adk_demos/d02_mcp_tools/agent.py` (~50 lines)

### What it teaches
How ADK connects to external MCP servers and auto-discovers tools. The LLM sees MCP tools exactly like local Python functions — the source is invisible to the model.

### Key code elements

```python
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)

_PRICING_SERVER = str(
    Path(__file__).resolve().parents[3] / "m2_mcp" / "pricing_server.py"
)

root_agent = LlmAgent(
    name="mcp_tools_agent",
    model="openai/gpt-4o",
    tools=[
        MCPToolset(                          # ← replaces local function tools
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,   # python
                    args=[_PRICING_SERVER],   # m2_mcp/pricing_server.py
                )
            )
        )
    ],
)
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`MCPToolset`** | ADK's bridge to MCP servers. Spawns the server, runs `initialize` + `tools/list`, wraps discovered tools for the LLM. All automatic |
| **`StdioConnectionParams`** | Tells ADK to connect via stdio (subprocess). The alternative is `SseConnectionParams` for HTTP-based MCP servers |
| **`StdioServerParameters`** | Specifies the command + args to spawn the MCP server subprocess. `sys.executable` = the current Python interpreter |
| **Auto-discovery** | You don't list tool names anywhere in `agent.py`. ADK discovers them from the server at startup via `tools/list`. Add a new `@mcp.tool()` to the server → ADK picks it up on next restart |
| **Tool source transparency** | The LLM doesn't know (or care) whether a tool is a local Python function (d01) or a remote MCP server (d02). The function-calling interface is identical |
| **Cross-module dependency** | `_PRICING_SERVER` points to `m2_mcp/pricing_server.py` — M3 consumes tools built in M2. No code changes needed in M2 |

### d01 vs d02 — the key comparison

```
d01: tools=[get_quick_estimate]         → you wrote the function, ADK reads its signature
d02: tools=[MCPToolset(...)]            → ADK spawns the server, discovers tools via MCP protocol
```

The LLM sees identical function schemas in both cases.

### What happens under the hood

```
adk web starts
  → imports agent.py, sees MCPToolset in tools list
  → spawns pricing_server.py as subprocess (stdio pipe)
  → MCP handshake: initialize → tools/list
  → discovers: get_market_price, calculate_discount, get_property_tax_estimate
  → LlmAgent now has 3 callable tools

User: "What's 742 Evergreen Terrace worth?"
  → GPT-4o sees 3 tool schemas, decides to call get_market_price
  → ADK sends tools/call to pricing_server.py via stdio
  → Server runs Python function, returns JSON result
  → ADK feeds result back to GPT-4o
  → GPT-4o produces final answer with real data

adk web shuts down
  → ADK kills the pricing_server.py subprocess (no orphans)
```

### Why event count is high (~317)

The left panel shows ~317 events because it includes:
- MCP handshake frames (`initialize`, `notifications/initialized`, `tools/list`)
- Each MCP `tools/call` request and response
- LLM streaming token events (each chunk is an event)
- Session state events

The right panel shows only the meaningful conversation steps (#1–#8). Focus students there.

### ADK Web UI — what to notice

| UI Element | What's different from d01 |
|------------|--------------------------|
| **Info tab** | Shows MCP-discovered tool schemas — notice the tool descriptions come from the `@mcp.tool()` docstrings in `pricing_server.py`, not from this file |
| **Tool call badges** | `⚡ get_market_price` → `✓ get_market_price` — same as d01 but the tool ran on the MCP server, not locally |
| **Event count** | Much higher (~300+) because MCP protocol frames and streaming tokens are counted |

### Key teaching points for class

1. **"Same agent pattern, different tool source."** Compare d01 and d02 side by side — the `LlmAgent` declaration is nearly identical. Only `tools=` changed.
2. **"You didn't touch the MCP server."** `pricing_server.py` was built in M2. It works with ADK without modification — that's the power of a protocol standard.
3. **"Auto-discovery means zero wiring."** Add a new `@mcp.tool()` to the server, restart `adk web`, and the LLM can call it. No agent code changes needed (this is exactly what Exercise 02 in M2 teaches).
4. **The 317 events are normal.** MCP runs an entire subprocess protocol under the hood. Students should focus on the right panel, not the event counter.
5. **This is what the buyer/seller agents do.** `negotiation_agents/buyer_agent/agent.py` uses the same `MCPToolset` pattern — this demo is the simplified version.

---

## Demo 03 — Sessions & State (`d03_sessions_state`)

**File:** `adk_demos/d03_sessions_state/agent.py`

### What it teaches

### Concepts introduced

### Key teaching points

---

## Demo 04 — SequentialAgent (`d04_sequential`)

**File:** `adk_demos/d04_sequential/agent.py`

### What it teaches

### Concepts introduced

### Key teaching points

---

## Demo 05 — ParallelAgent (`d05_parallel`)

**File:** `adk_demos/d05_parallel/agent.py`

### What it teaches

### Concepts introduced

### Key teaching points

---

## Demo 06 — LoopAgent (`d06_loop`)

**File:** `adk_demos/d06_loop/agent.py`

### What it teaches

### Concepts introduced

### Key teaching points

---

## Demo 07 — Agent-as-Tool (`d07_agent_as_tool`)

**File:** `adk_demos/d07_agent_as_tool/agent.py`

### What it teaches

### Concepts introduced

### Key teaching points

---

## Demo 08 — Callbacks (`d08_callbacks`)

**File:** `adk_demos/d08_callbacks/agent.py`

### What it teaches

### Concepts introduced

### Key teaching points

---

## Demo 09 — Event Stream (`d09_event_stream`)

**File:** `adk_demos/d09_event_stream/agent.py`

### What it teaches

### Concepts introduced

### Key teaching points

---

## Demo 10 — A2A Wire Format & Task Lifecycle (`a2a_10_wire_lifecycle.py`)

**File:** `adk_demos/a2a_10_wire_lifecycle.py` (terminal script)

### What it teaches

### Concepts introduced

### Key teaching points

---

## Demo 11 — A2A Context Threading (`a2a_11_context_threading.py`)

**File:** `adk_demos/a2a_11_context_threading.py` (terminal script)

### What it teaches

### Concepts introduced

### Key teaching points

---

## Demo 12 — A2A Parts & Artifacts (`a2a_12_parts_and_artifacts.py`)

**File:** `adk_demos/a2a_12_parts_and_artifacts.py` (terminal script)

### What it teaches

### Concepts introduced

### Key teaching points

---

## Demo 13 — A2A Streaming (`a2a_13_streaming.py`)

**File:** `adk_demos/a2a_13_streaming.py` (terminal script)

### What it teaches

### Concepts introduced

### Key teaching points

---

## Negotiation Agents — Full System

### buyer_agent

### seller_agent

### negotiation orchestrator

### Key teaching points

---

## Cross-cutting concepts

| Concept | First introduced | Revisited in |
|---------|-----------------|-------------|
| `LlmAgent` | d01 | Every demo |
| `root_agent` convention | d01 | Every adk web demo |
| Function tools | d01 | d03, d08, d09 |
| `MCPToolset` | d02 | buyer_agent, seller_agent |
| `ToolContext` + state | d03 | d09 |
| `output_key` + `{placeholder}` | d04 | d05, negotiation |
| `SequentialAgent` | d04 | negotiation |
| `ParallelAgent` | d05 | — |
| `LoopAgent` + escalation | d06 | negotiation |
| `AgentTool` | d07 | — |
| Callbacks (before/after) | d08 | buyer_agent, seller_agent |
| Event stream | d09 | — |
| Agent Card | a2a_10 | a2a_11, a2a_12, a2a_13 |
| `contextId` threading | a2a_11 | — |
| Parts (Text/Data/File) | a2a_12 | — |
| Artifacts | a2a_12 | — |
| `message/stream` SSE | a2a_13 | — |
| Information asymmetry | buyer vs seller | — |
| `before_tool_callback` allowlist | d08 | buyer_agent, seller_agent |
