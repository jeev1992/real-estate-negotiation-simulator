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

**The 4 tables in session.db** (same in every demo):

| Table | ADK Scope | What it stores | Lifetime |
|-------|-----------|----------------|----------|
| **sessions** | Session-scoped | Conversation history, session metadata, state keys with **no prefix** | Cleared on "New Session" |
| **events** | Per-turn | Every Event from the agent loop — user messages, tool calls, tool results, LLM responses, state deltas | Appended each turn, tied to a session |
| **user_states** | `user:` prefix | State keys like `user:total_offers` — persists for the same `user_id` | Survives "New Session" |
| **app_states** | `app:` prefix | State keys like `app:global_counter` — shared across ALL users and sessions | Survives everything |

The `temp:` prefix is never persisted — it lives only in memory for one turn.

**`user:` vs `app:` — when does the distinction matter?**

If Alice and Bob both use the app:

| Key | Alice sees | Bob sees |
|-----|-----------|----------|
| `offer_history` (no prefix) | Alice's current session offers | Bob's current session offers |
| `user:total_offers` | Alice's lifetime total (e.g., 5) | Bob's lifetime total (e.g., 3) |
| `app:negotiations_run` | 42 (same for everyone) | 42 (same for everyone) |

In `adk web`, the `user_id` defaults to `"user"` for everyone — so in a workshop, `user:` and `app:` behave the same since there's only one user. The distinction matters in production with multiple users.

**d01 specific data:**

| Table | Contents |
|-------|----------|
| **sessions** | 3 rows (3 separate sessions). State only has `__session_metadata__` with `displayName` (first message of each session) |
| **events** | 20 events across 3 sessions |
| **app_states** | Empty — no `app:` prefixed state keys written |
| **user_states** | Empty — no `user:` prefixed state keys written |

**Full event flow (20 events, 4 test questions):**

```
Session 1 (early exploration):

  Event 1  | user:        "Hi"
  Event 2  | basic_agent: "Hello! How can I assist you with real estate today?" (no tool call)

  Event 3  | user:        "What is the price for 742 Evergreen Terrace?"
  Event 4  | basic_agent: tool_call: get_quick_estimate({"address": "742 Evergreen Terrace"})
  Event 5  | basic_agent: tool_result: {estimate_usd: 462000, confidence: "high"}
  Event 6  | basic_agent: "The estimated market value is $462,000, with high confidence."

Session 2 (all 4 test questions in same session):

  Event 7  | user:        "What's 742 Evergreen Terrace worth?"
  Event 8  | basic_agent: tool_call: get_quick_estimate({"address": "742 Evergreen Terrace"})
  Event 9  | basic_agent: tool_result: {estimate_usd: 462000, confidence: "high"}
  Event 10 | basic_agent: "$462,000, high confidence"

  Event 11 | user:        "How about 123 Main St?"
  Event 12 | basic_agent: tool_call: get_quick_estimate({"address": "123 Main St"})
  Event 13 | basic_agent: tool_result: {estimate_usd: 380000, confidence: "medium"}
  Event 14 | basic_agent: "$380,000, medium confidence"

  Event 15 | user:        "What about 999 Unknown Ave?"
  Event 16 | basic_agent: tool_call: get_quick_estimate({"address": "999 Unknown Ave"})
  Event 17 | basic_agent: tool_result: {estimate_usd: 450000, confidence: "low"}
  Event 18 | basic_agent: "$450,000, LOW confidence"  ← fallback value

Session 3 (no tool call):

  Event 19 | user:        "What's the best neighborhood in Austin?"
  Event 20 | basic_agent: "The best neighborhood depends on preferences..." (NO tool call)
```

**Key observations:**

1. **Question 1–3**: Each property question triggered `get_quick_estimate`. The tool returned different confidence levels (high/medium/low) and the LLM faithfully reported each.

2. **Question 3 (unknown address)**: The tool's fallback logic returned $450K with "low" confidence. The LLM highlighted the low confidence — it reads and reasons about the tool's output, not just the number.

3. **Question 4 (no tool)**: "Best neighborhood" is not a property estimate, so the LLM answered from its own knowledge without calling the tool. Only 2 events (user + response) — no tool_call/tool_result events.

4. **"Hi" greeting**: The first message also had no tool call — the LLM recognized it as a greeting, not a property query. Same pattern as question 4.

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

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|-----------------|
| 1 | "What's 742 Evergreen Terrace worth?" | Calls `get_quick_estimate` → $462K, high confidence | Basic tool call flow |
| 2 | "How about 123 Main St?" | Calls tool → $380K, medium confidence | Different data, same tool |
| 3 | "What about 999 Unknown Ave?" | Calls tool → $450K, **low** confidence (fallback) | Tool handles unknown inputs gracefully |
| 4 | "What's the best neighborhood in Austin?" | Does NOT call tool — answers from LLM knowledge | LLM decides when tools are relevant |

### Where is the session/runner code?

**Runner vs Session — the key distinction:**

| | **Runner** | **Session** |
|---|---|---|
| **What it is** | Execution engine — runs one turn | Memory store — persists across all turns |
| **What it does** | Takes message → calls LLM → handles tool calls → produces events | Stores conversation history, state dict, events |
| **Lifespan** | Transient (processes one message, done) | Persistent (survives across all turns in a conversation) |
| **In session.db** | Not stored | `sessions` table + `events` table |
| **Analogy** | The waiter who takes your order | The order pad that remembers everything |

The Runner reads state FROM the session at the start of each turn, and writes state BACK at the end. You could run the same Runner against different sessions (different conversations).

In d01–d09, you never write session or runner code. `adk web` handles it all:

| What | Who does it | Where |
|------|------------|-------|
| Create session | `adk web` (auto on "New Session" click) | Stored in `.adk/session.db` → `sessions` table |
| Create Runner | `adk web` (auto from `root_agent`) | Internal — you never see it |
| Create SessionService | `adk web` (SQLite by default) | `.adk/session.db` |
| Call `runner.run_async()` | `adk web` (on each chat message) | Internal — you never see it |

If you needed to do this manually (no `adk web`), you'd write:

```python
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name="my_app", session_service=session_service)
session = await session_service.create_session(app_name="my_app", user_id="alice", session_id="s1")

async for event in runner.run_async(
    user_id="alice", session_id="s1",
    new_message=Content(role="user", parts=[Part(text="What's 742 Evergreen worth?")]),
):
    if event.content and event.content.parts:
        print(event.content.parts[0].text)
```

**You don't need this in the workshop.** It's here so you can answer "how would I do this without `adk web`?" if a student asks. The A2A terminal scripts (10–13) also don't show this — they're HTTP clients talking to `adk web --a2a`, which handles sessions server-side.

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
4. **The high event count is normal.** MCP runs an entire subprocess protocol under the hood. Students should focus on the right panel, not the event counter.
5. **This is what the buyer/seller agents do.** `negotiation_agents/buyer_agent/agent.py` uses the same `MCPToolset` pattern — this demo is the simplified version.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|-----------------|
| 1 | "What's 742 Evergreen Terrace worth?" | Calls `get_market_price` → rich data (comps, value, $/sqft) | MCP tool discovery + execution works |
| 2 | "Calculate a discount for a $485K property in a balanced market" | Calls `calculate_discount` → discount ranges, negotiation tips | LLM picks the right tool from multiple options |
| 3 | "What are the taxes on 742 Evergreen Terrace?" | Does NOT call any tool — says "I don't have tax info" | **Key moment**: `get_property_tax_estimate` is commented out in the server. LLM correctly knows it has no tax tool. Proves auto-discovery is real |
| 4 | "Is this property overpriced?" | May call `get_market_price` then reason about listing vs estimated value | LLM chains reasoning on top of tool results |

> **Demo 3 is the most important question.** It proves the instruction doesn't need to name tools — the LLM only knows about tools MCPToolset actually discovered. After M2 Exercise 01 (uncomment the tax tool), this same question will work.

### session.db after running

| Table | Contents |
|-------|----------|
| **sessions** | 2 rows — one per "New Session" click. Each has `app_name=d02_mcp_tools`, state only has `__session_metadata__` with `displayName` |
| **events** | 10 events across 2 sessions. Three queries exercised all available tools + one that revealed a missing tool |
| **app_states** | Empty — no `app:` scoped state |
| **user_states** | Empty — no `user:` scoped state |

**Full event flow (10 events, 3 queries):**

```
Session 1 (3 queries in same session):

  Event 1  | user:           "What's 742 Evergreen Terrace worth?"
  Event 2  | mcp_tools_agent | tool_call: get_market_price({"address": "742 Evergreen..."})
  Event 3  | mcp_tools_agent | tool_result: get_market_price -> {address, property_details, estimated_value...}
  Event 4  | mcp_tools_agent | final answer: "The property at 742 Evergreen... single-family, 4BR, 2400 sqft..."

  Event 5  | user:           "Calculate a discount for a $485K property in a balanced market"
  Event 6  | mcp_tools_agent | tool_call: calculate_discount({"base_price": 485000, "market_condition": "balanced"...})
  Event 7  | mcp_tools_agent | tool_result: calculate_discount -> {inputs, discount_analysis...}
  Event 8  | mcp_tools_agent | final answer: "For a property listed at $485,000 in a balanced market..."

Session 2 (1 query — demonstrates missing tool):

  Event 9  | user:           "What are the taxes on 742 Evergreen Terrace?"
  Event 10 | mcp_tools_agent | final answer (NO tool call): "I currently don't have access to specific tax information..."
```

**Key observations:**

1. **Query 1 & 2**: The LLM correctly chose `get_market_price` for valuation and `calculate_discount` for pricing — without the instruction naming these tools. Auto-discovery works.

2. **Query 3 (the revealing one)**: Asked about taxes. The LLM did NOT call any tool — it responded directly saying it doesn't have tax data. This is because `get_property_tax_estimate` is **commented out** in `pricing_server.py` (it's the M2 Exercise 01 tool). The LLM checked its available tools, found no tax tool, and honestly declined. **This proves auto-discovery is real** — the LLM only knows about tools MCPToolset actually discovered.

3. **No tool names in instruction**: After removing hardcoded tool names from the instruction, the LLM still found and used the right tools. The function-calling schemas (visible in the Info tab) are what the LLM reads, not the instruction text.

4. **MCP content wrapping**: Tool results have `{"content": [{"type": "text", "text": "..."}]}` — the MCP protocol envelope around the actual data. Compare to d01 where tool results were plain dicts.

5. **The LLM added arguments the user didn't provide**: For `calculate_discount`, the user said "balanced market" but the LLM also supplied `days_on_market: 18` and `property_condition: "good"` — it inferred reasonable defaults from the tool's JSON schema.

---

## Demo 03 — Sessions & State (`d03_sessions_state`)

**File:** `adk_demos/d03_sessions_state/agent.py` (~55 lines)

### What it teaches
How tools read and write session state via `ToolContext`, and how state scoping (`user:` prefix) controls what persists across sessions.

### Key code elements

```python
from google.adk.tools.tool_context import ToolContext

def record_offer(price: int, tool_context: ToolContext) -> dict:
    """Record the user's latest offer price in session state."""
    history = tool_context.state.get("offer_history", [])
    history.append(price)
    tool_context.state["offer_history"] = history          # session-scoped (no prefix)
    tool_context.state["user:total_offers"] = len(history) # user-scoped (survives New Session)
    return {"recorded_price": price, "total_offers": len(history), "all_offers": history}

def get_offer_history(tool_context: ToolContext) -> dict:
    """Retrieve the full history of offers made in this session."""
    history = tool_context.state.get("offer_history", [])
    total = tool_context.state.get("user:total_offers", 0)
    return {"offers": history, "total_across_sessions": total}
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`ToolContext`** | ADK injects this into any tool that declares `tool_context: ToolContext` as a parameter. It gives tools access to session state, artifacts, and actions. ADK hides it from the LLM's JSON schema — the LLM never sees it |
| **`tool_context.state`** | A dict that persists across turns within the same session. Tools can read and write it freely |
| **Session-scoped state** (no prefix) | `offer_history` — lives in the `sessions` table, cleared on "New Session" |
| **User-scoped state** (`user:` prefix) | `user:total_offers` — lives in the `user_states` table, survives across sessions for the same user |
| **State tab** | The ADK web UI's State tab shows the session state dict live — updates after every message |
| **Parallel tool calls** | The LLM called BOTH `record_offer` AND `get_offer_history` in a single turn (visible in events 2–3). ADK supports parallel tool calls |

### What happens under the hood

```
User: "Offer $430,000"
  → LLM decides to call record_offer(price=430000) + get_offer_history()
  → ADK executes both tools
  → record_offer writes: state["offer_history"] = [430000], state["user:total_offers"] = 1
  → get_offer_history reads: offers=[430000], total=1
  → LLM receives both results, produces strategic advice
  → State tab now shows: offer_history: [430000]

User: "Offer $440,000" (after $445K)
  → record_offer writes: state["offer_history"] = [430000, 445000, 440000]
  → LLM notices $440K < previous $445K and warns about regression
     (Note: regression warning logic is in Exercise 02, not in this demo's code.
      The LLM noticed the regression from the offer history and warned on its own.)

Click "New Session" → "How many offers?"
  → get_offer_history reads: offers=[] (session cleared), total_across_sessions=3 (user: persisted)
  → LLM says: "3 offers across all sessions, none in current session"
```

### session.db after running

| Table | Contents |
|-------|----------|
| **sessions** | 2 rows — session 1 has `offer_history: [430000, 445000, 440000]`, session 2 has empty state |
| **events** | 20 events across 2 sessions (5 queries) |
| **app_states** | Empty — no `app:` scoped state |
| **user_states** | **1 row!** `{"total_offers": 3}` — first time we see data here. Persisted across sessions |

**Full event flow (20 events, 5 queries):**

```
Session 1 (4 queries — offer sequence):

  Event 1  | user:           "Offer $430,000"
  Event 2  | stateful_agent: tool_call: record_offer({"price": 430000}) + get_offer_history({})
  Event 3  | stateful_agent: tool_results: {recorded: 430K, total: 1} + {offers: [430K], total: 1}
  Event 4  | stateful_agent: "You've made an offer of $430,000... At $430K you're 11% below asking..."

  Event 5  | user:           "$445,000"
  Event 6  | stateful_agent: tool_call: record_offer({"price": 445000}) + get_offer_history({})
  Event 7  | stateful_agent: tool_results: {recorded: 445K, total: 2} + {offers: [430K, 445K], total: 2}
  Event 8  | stateful_agent: "You've increased to $445,000..."

  Event 9  | user:           "Offer $440,000"
  Event 10 | stateful_agent: tool_call: record_offer({"price": 440000}) + get_offer_history({})
  Event 11 | stateful_agent: tool_results: {recorded: 440K, total: 3} + {offers: [430K, 445K, 440K], total: 3}
  Event 12 | stateful_agent: "Your new offer is $440,000..." (LLM noticed regression from $445K)

  Event 13 | user:           "What's my offer history?"
  Event 14 | stateful_agent: tool_call: get_offer_history({})
  Event 15 | stateful_agent: tool_result: {offers: [430K, 445K, 440K], total: 3}
  Event 16 | stateful_agent: "Here's your complete offer history: 1. $430K, 2. $445K, 3. $440K"

Session 2 (1 query — proves user-scoped persistence):

  Event 17 | user:           "How many offers?"
  Event 18 | stateful_agent: tool_call: get_offer_history({})
  Event 19 | stateful_agent: tool_result: {offers: [], total_across_sessions: 3}  ← KEY MOMENT
  Event 20 | stateful_agent: "3 offers across all sessions, none in current session"
```

**Key observations:**

1. **Parallel tool calls**: Events 2–3 show the LLM calling `record_offer` AND `get_offer_history` in a single turn. ADK executes both and returns both results. The LLM didn't need to be told to do this — it decided on its own.

2. **State accumulation**: The `offer_history` array grew across turns: `[430K]` → `[430K, 445K]` → `[430K, 445K, 440K]`. Each turn's tool call could read the previous turns' state.

3. **Regression detection by LLM**: The LLM noticed that $440K < $445K and warned about it — even though our demo code doesn't have explicit regression warning logic (that's Exercise 02). The LLM reasoned about the data.

4. **Session vs user scope proven**: Event 19 is the proof. `offers: []` (session state cleared on New Session) but `total_across_sessions: 3` (`user:total_offers` persisted in `user_states` table).

5. **`user_states` table has data**: `{"total_offers": 3}` — first demo where this table is populated. This is the `user:` prefix at work.

6. **session.state shows the dict**: Session 1's state in the `sessions` table contains the full `offer_history` array — this is what the State tab in the UI shows.

### Key teaching points for class

1. **"ToolContext is the magic parameter."** Add `tool_context: ToolContext` to any tool function and ADK injects it. The LLM never sees it — it's hidden from the schema.
2. **"State scope = where it lives."** No prefix → session table (cleared on New Session). `user:` → user_states table (survives forever for this user). `app:` → app_states (global). `temp:` → memory only (one turn).
3. **"Watch the State tab."** After each message, the State tab updates live. This is session state — the same dict the tools read and write.
4. **"This is how the negotiation agents track rounds."** The `negotiation/agent.py` orchestrator uses `output_key` (writes to session state) and `{placeholder}` (reads from session state) — same mechanism, different syntax.
5. **"The LLM called two tools in one turn."** It decided on its own to call both `record_offer` and `get_offer_history` simultaneously. ADK supports parallel tool calls.

---

## Demo 04 — SequentialAgent (`d04_sequential`)

**File:** `adk_demos/d04_sequential/agent.py` (~55 lines)

### What it teaches
How to chain multiple agents in a pipeline where each agent's output feeds the next agent's input via session state.

### Key code elements

```python
from google.adk.agents import LlmAgent, SequentialAgent

market_brief = LlmAgent(name="market_brief", output_key="market_summary", ...)
offer_drafter = LlmAgent(name="offer_drafter", output_key="offer_text",
    instruction="Read {market_summary} and draft an offer...")       # ← reads previous output
polisher = LlmAgent(name="message_polisher", output_key="final_email",
    instruction="Polish {offer_text} into a professional email...")  # ← reads previous output

root_agent = SequentialAgent(
    name="negotiation_pipeline",
    sub_agents=[market_brief, offer_drafter, polisher],  # runs in THIS order
)
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`SequentialAgent`** | A workflow agent (not an LlmAgent). Doesn't call a model itself — runs its `sub_agents` in declaration order, one after another |
| **`output_key`** | Each sub-agent writes its response to a named session state key. This is how data flows between agents |
| **`{placeholder}`** | In an instruction, `{market_summary}` is replaced with the value from session state at runtime. This is how agent B reads agent A's output |
| **Pipeline pattern** | Agent A produces data → writes to state → Agent B reads it → produces more data → Agent C reads it. Linear data flow |
| **No tools** | None of the sub-agents have tools. They're pure LLM reasoning, chained via state. Tools are orthogonal to workflow agents |

### What happens under the hood

```
User: "Research this property"
  → SequentialAgent starts
  → Runs market_brief first
    → LLM produces market summary
    → ADK writes it to state["market_summary"]
  → Runs offer_drafter second
    → ADK substitutes {market_summary} in the instruction
    → LLM reads the market data and drafts an offer
    → ADK writes it to state["offer_text"]
  → Runs message_polisher third
    → ADK substitutes {offer_text} in the instruction
    → LLM polishes into a professional email
    → ADK writes it to state["final_email"]
  → Pipeline complete — final_email is the last output
```

### session.db after running

| Table | Contents |
|-------|----------|
| **sessions** | 1 row — state has `market_summary`, `offer_text`, `final_email` all populated |
| **events** | 4 events: user message + 3 agent responses (one per sub-agent) |
| **app_states** | Empty |
| **user_states** | Empty |

**Full event flow (4 events):**

```
  Event 1 | author: user             "Research this property"
  Event 2 | author: market_brief     "I'm unable to conduct real-time research..." (no MCP tools = LLM knowledge only)
  Event 3 | author: offer_drafter    "We are pleased to extend an offer of $460,000..."
  Event 4 | author: message_polisher "Subject: Initial Offer for 742 Evergreen Terrace\n\nDear [Listing Agent]..."
```

**Key observations:**

1. **3 different `author` names**: `market_brief` → `offer_drafter` → `message_polisher`. Each sub-agent is a separate LLM call with its own instruction.

2. **Only 4 events total**: Much simpler than d01–d03. No tool calls — just 1 user message + 3 LLM responses. Workflow agents are lightweight.

3. **State tab shows all 3 keys**: `market_summary`, `offer_text`, `final_email` — the entire pipeline's intermediate and final outputs are visible. This is the `output_key` mechanism at work.

4. **market_brief had no real data**: Without MCP tools (like d02), the first agent couldn't do real research — it said "I'm unable to access current data." In Exercise 03, students build a pipeline where the first agent IS an MCP-equipped researcher.

5. **Each agent saw only what it needed**: `offer_drafter` read `{market_summary}` — it didn't see the raw user message or the polisher's output. State keys create **scoped visibility** between agents.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|-----------------|
| 1 | "Research this property" (or any message) | Three agents fire in sequence: market_brief → offer_drafter → polisher | Pipeline execution order |
| 2 | After run, check **State tab** | See `market_summary`, `offer_text`, `final_email` keys | `output_key` state passing |

> Watch the Events panel — you'll see 3 different `author` names firing in order.

### Key teaching points for class

1. **"SequentialAgent is NOT an LlmAgent."** It doesn't call a model. It's a workflow primitive that runs children in order. Think of it as a for-loop over agents.
2. **"`output_key` + `{placeholder}` is the data pipeline."** Agent A writes to state via `output_key`. Agent B reads via `{placeholder}` in its instruction. No shared variables, no function calls between them.
3. **"Compare to d03."** In d03, tools wrote to `tool_context.state` explicitly. Here, `output_key` does it automatically — the agent's final text response is written to the key.
4. **"This is half of the negotiation orchestrator."** `negotiation/agent.py` uses `SequentialAgent(buyer, seller)` — buyer writes `buyer_offer`, seller reads `{buyer_offer}`. Same pattern.
5. **"The first agent was handicapped."** Without MCP tools, `market_brief` couldn't get real data. This is why d02 (MCPToolset) matters — combine it with SequentialAgent and you get a real research pipeline (Exercise 03).

---

## Demo 05 — ParallelAgent (`d05_parallel`)

**File:** `adk_demos/d05_parallel/agent.py` (~45 lines)

### What it teaches
How to run multiple agents concurrently with `ParallelAgent` — each writing to a different state key. Useful for fan-out research (gathering independent signals simultaneously).

### Key code elements

```python
from google.adk.agents import LlmAgent, ParallelAgent

schools = LlmAgent(name="schools_signal", output_key="schools", ...)
comps = LlmAgent(name="comps_signal", output_key="comps", ...)
inventory = LlmAgent(name="inventory_signal", output_key="inventory", ...)

root_agent = ParallelAgent(
    name="market_signals",
    sub_agents=[schools, comps, inventory],  # all run at the SAME time
)
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`ParallelAgent`** | Like `SequentialAgent` but runs all children concurrently. Not an LlmAgent — it's a workflow primitive |
| **Independent state keys** | Each sub-agent writes to its own `output_key` (`schools`, `comps`, `inventory`). No conflicts because they don't share keys |
| **Fan-out pattern** | Send the same task to multiple specialists, gather results. Classic map-reduce first step |

### d04 vs d05 — the key comparison

```
d04 SequentialAgent: market_brief → offer_drafter → polisher  (A feeds B feeds C)
d05 ParallelAgent:   schools ↗                                (all independent)
                     comps   →  all run at once
                     inventory ↘
```

d04 is for **pipelines** (data flows from A→B→C). d05 is for **fan-out** (A, B, C are independent).

### session.db after running

| Table | Contents |
|-------|----------|
| **sessions** | 1 row — state has `schools`, `comps`, `inventory` all populated |
| **events** | 4 events: user message + 3 concurrent agent responses |
| **app_states** | Empty |
| **user_states** | Empty |

**Full event flow (4 events):**

```
  Event 1 | author: user              "Gather signals"
  Event 2 | author: schools_signal    "Austin ISD near 78701 has strong academic programs..."
  Event 3 | author: comps_signal      "Recent comps show increasing prices, $700K–$1M range..."
  Event 4 | author: inventory_signal  "Housing inventory pressure in 78701 remains high..."
```

**Key observations:**

1. **Same event structure as d04** — 4 events, 3 different authors. The db layout looks identical. The difference is in execution timing (concurrent vs sequential), which you see in the Events panel timestamps.

2. **All 3 state keys populated in one turn**: The State tab shows `schools`, `comps`, `inventory` all filled after a single user message. In d04, the pipeline built up incrementally (summary → offer → email). Here, all 3 appear simultaneously.

3. **No `{placeholder}` reading**: Unlike d04, none of these agents read another agent's output. They're independent. This is why ParallelAgent works here — there are no data dependencies.

4. **State key in session different from event order**: The session state shows `inventory` before `schools` — the order in the state dict doesn't match declaration order because they ran concurrently and finished in unpredictable order.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|-----------------|
| 1 | "Gather signals" (or any message) | Three agents fire concurrently: schools, comps, inventory | Parallel fan-out |
| 2 | After run, check **State tab** | See `schools`, `comps`, `inventory` keys all populated | Independent state keys |

> Compare timestamps in Events — all 3 agents should start at roughly the same time (unlike d04 which is sequential).

### Key teaching points for class

1. **"ParallelAgent = fan-out."** Independent tasks that don't depend on each other. Use it when you'd otherwise call 3 APIs sequentially but they could run at the same time.
2. **"Same `output_key` pattern, different orchestration."** d04 and d05 both use `output_key` to write to state. The difference is SequentialAgent (ordered) vs ParallelAgent (concurrent).
3. **"Each agent MUST write to a different key."** If two agents wrote to the same `output_key`, the last one to finish would overwrite the other. No merge — just overwrite.
4. **"Combine them."** Exercise 03 asks students to nest a ParallelAgent inside a SequentialAgent — parallel research first, then sequential strategy + risk assessment. That's the real-world pattern.

---

## Demo 06 — LoopAgent (`d06_loop`)

**File:** `adk_demos/d06_loop/agent.py` (~55 lines)

### What it teaches
How `LoopAgent` iterates sub-agents until a stop condition — either `max_iterations` or an explicit escalation from a callback. This is the ADK equivalent of M1's FSM termination guarantee.

### Key code elements

```python
from google.adk.agents import LlmAgent, LoopAgent
from google.adk.agents.callback_context import CallbackContext

def stop_when_in_range(callback_context: CallbackContext):
    """Escalate (break the loop) when price is $450K–$470K."""
    raw = callback_context.state.get("proposal", "")
    digits = "".join(c for c in str(raw) if c.isdigit())
    price = int(digits)
    if 450_000 <= price <= 470_000:
        callback_context.actions.escalate = True    # ← THIS breaks the loop
    return None

haggler = LlmAgent(
    name="haggler",
    output_key="proposal",
    after_agent_callback=stop_when_in_range,        # runs AFTER each iteration
    ...
)

root_agent = LoopAgent(
    name="haggle_loop",
    sub_agents=[haggler],
    max_iterations=5,                                # bounded — NEVER runs more than 5
)
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`LoopAgent`** | Re-runs `sub_agents` each iteration. Stops when `max_iterations` is hit OR a callback escalates. Not an LlmAgent — a workflow primitive |
| **`max_iterations`** | Hard upper bound. Guarantees termination even if the callback never fires. Same guarantee as M1's FSM `max_turns` |
| **`after_agent_callback`** | Runs after each sub-agent completes. Receives `CallbackContext` with access to session state and actions |
| **`callback_context.actions.escalate = True`** | The ONE line that breaks the loop. Sets an escalation signal that the parent `LoopAgent` reads. Like setting `is_terminal = True` in M1's FSM |
| **`output_key` in a loop** | Each iteration overwrites the same key (`proposal`). Only the last value survives in state |

### What happens under the hood

```
User: "start"
  → LoopAgent starts, iteration 1
    → haggler produces "465000" → state["proposal"] = "465000"
    → after_agent_callback: 465K is in range → escalate = True
    → LoopAgent sees escalation → STOP
  Total: 1 iteration (early exit)

OR (different run):
  → iteration 1: "476000" → not in range → continue
  → iteration 2: "473000" → not in range → continue
  → iteration 3: "441000" → not in range → continue
  → iteration 4: "459000" → in range → escalate → STOP
  Total: 4 iterations

OR (worst case):
  → iterations 1-5: all outside range → max_iterations hit → STOP
  Total: 5 iterations (hard cap)
```

### session.db after running

| Table | Contents |
|-------|----------|
| **sessions** | 2 rows (2 runs). Each has `proposal` with the LAST price proposed |
| **events** | 12 events total across 2 sessions |
| **app_states** | Empty |
| **user_states** | Empty |

**Full event flow (12 events, 2 runs):**

```
Session 1 (5 iterations — hit max_iterations, never landed in range):

  Event 1  | user:    "start"
  Event 2  | haggler: "465000"  → in range BUT...
  Event 3  | haggler: "454000"  → in range BUT...
  Event 4  | haggler: "476000"  → out of range
  Event 5  | haggler: "473000"  → out of range
  Event 6  | haggler: "441000"  → out of range — hit max_iterations=5, STOP
  Final state: proposal = "441000"

Session 2 (5 iterations):

  Event 7  | user:    "start"
  Event 8  | haggler: "459000"  → in range (escalate!)... but continued?
  Event 9  | haggler: "475000"
  Event 10 | haggler: "445000"
  Event 11 | haggler: "460000"
  Event 12 | haggler: "471000"
  Final state: proposal = "471000"
```

**Key observations:**

1. **Non-deterministic**: The LLM proposed different prices each run. Session 1 had 5 iterations, session 2 had 5 iterations. The prices varied randomly as instructed ("vary your answer each time").

2. **`proposal` gets overwritten each iteration**: State only shows the LAST value. Unlike d03 where `offer_history` accumulated as an array, `output_key` with LoopAgent overwrites on each iteration.

3. **Escalation behavior**: Some prices that appear to be in range (e.g., 465000, 454000) might have been parsed differently by the callback (string parsing of LLM output can be imprecise). The callback extracts digits from the raw text — if the LLM included extra text, parsing might not match cleanly. This is a realistic edge case.

4. **`max_iterations=5` is the safety net**: Even when escalation doesn't fire, the loop always stops at 5. This is the same bounded termination guarantee as M1's FSM — but for multi-agent orchestration.

5. **Connection to M1 FSM**: `max_iterations` = `max_turns`. `escalate = True` = terminal state. Same principle, different level of abstraction.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|-----------------|
| 1 | "start" | Haggler proposes prices. Loop breaks when price hits $450K–$470K range or max 5 iterations | LoopAgent + escalation |
| 2 | After run, check **State tab** | See `proposal` key with the last price | output_key overwrites each iteration |
| 3 | Run again (New Session) | Different prices each time (LLM varies) but always stops ≤5 iterations | Bounded termination |

> Watch the Events panel for iteration count. If 1 iteration, escalation fired immediately. If 5, the range was never hit.

### Key teaching points for class

1. **"LoopAgent = bounded iteration."** `max_iterations` guarantees termination. Same principle as the FSM in M1 — the loop MUST stop.
2. **"`escalate = True` breaks the loop."** One line in a callback. The parent LoopAgent reads this and stops iterating. Like setting `is_terminal = True` in the FSM.
3. **"This is the negotiation loop."** `negotiation/agent.py` uses `LoopAgent(sub_agents=[SequentialAgent(buyer, seller)], max_iterations=5)`. Each iteration is one negotiation round. The seller's `after_agent_callback` checks for ACCEPT and escalates.
4. **"Compare to M1's while True problem."** The naive baseline had `while True` with no termination guarantee. LoopAgent replaces that with bounded iteration + explicit escalation. No while True, no emergency exits.
5. **"output_key overwrites in loops."** Each iteration writes the same key. Only the last value survives. If you need history, use `ToolContext.state` like d03 to accumulate an array.

---

## Demo 07 — Agent-as-Tool (`d07_agent_as_tool`)

**File:** `adk_demos/d07_agent_as_tool/agent.py` (~40 lines)

### What it teaches
How to wrap an entire `LlmAgent` as a callable tool using `AgentTool`. The coordinator agent calls the valuator like a function — but under the hood it's a full LLM call.

### Key code elements

```python
from google.adk.tools.agent_tool import AgentTool

valuator = LlmAgent(
    name="valuator",
    description="Estimates the fair market value of an Austin property.",  # ← coordinator reads this
    instruction="Return ONE sentence with estimated value range and biggest pricing factor.",
)

root_agent = LlmAgent(
    name="coordinator",
    instruction="When you need a valuation, call the `valuator` tool...",
    tools=[AgentTool(agent=valuator)],  # ← agent wrapped as a tool
)
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`AgentTool`** | Wraps an `LlmAgent` so it appears as a regular callable tool to the parent agent. The parent calls it like a function; ADK runs the child agent and returns the result |
| **Hierarchical delegation** | The coordinator decides WHEN to call the specialist. Unlike `sub_agents` (full delegation/transfer), `AgentTool` returns results to the caller — the coordinator stays in control |
| **`description` matters** | The coordinator's LLM reads the valuator's `description` to decide when to call it. A vague description = the LLM won't know when to delegate |
| **Two LLM calls per delegation** | One call for the coordinator (decides to call valuator), one call for the valuator (produces the valuation). More expensive than a single agent, but separation of concerns |

### AgentTool vs sub_agents vs SequentialAgent

```
AgentTool:        coordinator CALLS valuator as a tool → gets result back → continues reasoning
sub_agents:       coordinator TRANSFERS to valuator → valuator takes over completely
SequentialAgent:  both run in fixed order → no runtime decision about who runs
```

### session.db after running

| Table | Contents |
|-------|----------|
| **sessions** | 1 row — state has only `__session_metadata__` |
| **events** | 6 events across 2 queries |
| **app_states** | Empty |
| **user_states** | Empty |

**Full event flow (6 events, 2 queries):**

```
Query 1 — valuation needed (AgentTool fires):

  Event 1 | user:        "What should I offer on 742 Evergreen Terrace, Austin TX 78701?"
  Event 2 | coordinator: tool_call: valuator({"request": "742 Evergreen Terrace, Austin TX 78701"})
  Event 3 | coordinator: tool_result: valuator -> "estimated value $750K–$900K, biggest factor is location..."
  Event 4 | coordinator: "I recommend an offer within the $750K to $900K range..."

Query 2 — no valuation needed (AgentTool does NOT fire):

  Event 5 | user:        "What's the weather in Austin?"
  Event 6 | coordinator: "I'm unable to provide real-time weather updates..."  (no tool call)
```

**Key observations:**

1. **Event 2 looks like a regular tool call**: `tool_call: valuator({"request": "..."})` — identical to d01's `get_quick_estimate` call. The coordinator doesn't know it's calling another LLM agent vs a Python function.

2. **Event 3 is the valuator's response**: The valuator ran its own LLM call (not visible as a separate event in this session — it's nested inside the tool result). The result is a human-readable sentence because that's valuation agent's instruction.

3. **Event 4 shows coordinator reasoning**: The coordinator received the valuation, then wrote a recommendation paragraph. It stayed in control — it wasn't replaced by the valuator.

4. **Query 2 had no tool call**: "Weather in Austin" doesn't need a property valuation, so the coordinator skipped the valuator entirely. Same LLM decision pattern as d01 question #4.

5. **Valuator gave a much higher estimate ($750K–$900K)**: Without MCP tools, the valuator used LLM knowledge (which thinks Austin 78701 is expensive downtown). Compare to d02's MCP-backed `get_market_price` which returned $462K from simulated data. **This is why MCP matters** — without grounded data, the LLM hallucinated a price.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|-----------------|
| 1 | "What should I offer on 742 Evergreen Terrace, Austin TX 78701?" | Coordinator calls `valuator` tool, gets valuation, writes offer recommendation | AgentTool delegation |
| 2 | "What's the weather in Austin?" | Coordinator answers directly (no valuation needed) | Coordinator decides WHEN to delegate |

> In Events, look for the `valuator` tool call — it looks like a function call but it's actually running a full LlmAgent under the hood.

### Key teaching points for class

1. **"AgentTool = agent as a function."** The coordinator calls `valuator(...)` like any other tool. Under the hood, ADK runs a full LlmAgent and returns its text as the tool result.
2. **"The coordinator stays in control."** Unlike `sub_agents` where the LLM transfers to a sub-agent, `AgentTool` returns the result to the caller. The coordinator can combine results from multiple agent-tools in one response.
3. **"`description` is the function docstring."** The coordinator's LLM reads `valuator.description` to decide when to call it. Write it like you'd write a tool description — clear, specific, actionable.
4. **"Notice the hallucinated price."** Without MCP tools, the valuator estimated $750K–$900K (Austin downtown LLM knowledge). With d02's MCP tools, `get_market_price` returned $462K. This is the difference between LLM reasoning and grounded data.
5. **"Two LLM calls = more expensive."** Each delegation costs an extra model call. Use AgentTool when the specialist has genuinely different expertise or tools — not just for code organization.

---

## Demo 08 — Callbacks (`d08_callbacks`)

**File:** `adk_demos/d08_callbacks/agent.py` (~80 lines)

### What it teaches
How to inject policy into an agent WITHOUT changing its instruction — using `before_model_callback`, `before_tool_callback`, and `after_tool_callback`. Demonstrates PII redaction, tool allowlisting, and observability logging.

### Key code elements

```python
import re
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
ALLOWED_TOOLS = {"get_quick_estimate"}

def redact_pii(callback_context: CallbackContext, llm_request) -> None:
    """before_model: scrub SSNs from user messages before they reach the LLM."""
    for content in llm_request.contents or []:
        for part in content.parts or []:
            if part.text and SSN_RE.search(part.text):
                part.text = SSN_RE.sub("[REDACTED]", part.text)
                print("[before_model] redacted PII from prompt")
    return None  # None = continue to LLM

def enforce_allowlist(tool: BaseTool, args: dict, tool_context: ToolContext):
    """before_tool: block tools not on the allowlist."""
    if tool.name not in ALLOWED_TOOLS:
        print(f"[before_tool] BLOCKED {tool.name}")
        return {"error": f"tool '{tool.name}' is not permitted"}  # dict = short-circuit
    print(f"[before_tool] allow {tool.name}({args})")
    return None  # None = run the tool

def log_tool_result(tool: BaseTool, args: dict, tool_context: ToolContext, tool_response):
    """after_tool: log every tool return value."""
    print(f"[after_tool] {tool.name} -> {tool_response}")
    return None  # None = use the tool's original result

root_agent = LlmAgent(
    ...,
    tools=[get_quick_estimate, get_internal_admin],
    before_model_callback=redact_pii,
    before_tool_callback=enforce_allowlist,
    after_tool_callback=log_tool_result,
)
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`before_model_callback`** | Runs before EVERY LLM call. Can mutate the request (redact PII), or return `Content` to skip the LLM entirely |
| **`before_tool_callback`** | Runs before EVERY tool call. Return `None` to allow, return a `dict` to block (the dict becomes the tool's "result") |
| **`after_tool_callback`** | Runs after EVERY tool returns. Can log, modify, or replace the result |
| **Policy without prompts** | Callbacks enforce rules the LLM can't bypass. Prompt-based rules ("never reveal SSNs") are suggestive; callbacks are deterministic |
| **Short-circuit pattern** | `before_tool` returning a dict = the tool never runs. The dict is fed back to the LLM as if the tool had executed |

### What happens under the hood

```
Query 1: "My SSN is 123-45-6789. Estimate 742 Evergreen Terrace."
  → before_model: SSN regex matches → replaces with [REDACTED] → LLM never sees the SSN
  → LLM decides to call get_quick_estimate
  → before_tool: "get_quick_estimate" is in ALLOWED_TOOLS → allow
  → tool runs → returns {estimate: 462000}
  → after_tool: logs the result
  → LLM produces final answer

Query 2: "Also call get_internal_admin('debug')"
  → before_model: no SSN → passes through
  → LLM decides NOT to call the tool (it learned it was blocked, or instruction says "never call")
  → responds: "I can't perform that action, it's restricted"
  (Note: the LLM may or may not attempt the tool call — if it does, before_tool blocks it)

Query 3: "What's 742 Evergreen Terrace worth?"
  → before_model: no SSN → passes through
  → before_tool: allow get_quick_estimate
  → after_tool: logs result
  → normal response
```

### session.db after running

| Table | Contents |
|-------|----------|
| **sessions** | 1 row — state has only `__session_metadata__` |
| **events** | 10 events across 3 queries |
| **app_states** | Empty |
| **user_states** | Empty |

**Full event flow (10 events, 3 queries):**

```
Query 1 — PII redaction + allowed tool:

  Event 1  | user:          "My SSN is 123-45-6789. Estimate 742 Evergreen Terrace"
                             (terminal: [before_model] redacted PII from prompt)
  Event 2  | callback_demo: tool_call: get_quick_estimate({"address": "742 Evergreen Terrace"})
                             (terminal: [before_tool] allow get_quick_estimate({...}))
  Event 3  | callback_demo: tool_result: {estimate_usd: 462000}
                             (terminal: [after_tool] get_quick_estimate -> {result})
  Event 4  | callback_demo: "The rough market estimate is $462,000."

Query 2 — blocked tool (LLM didn't even try):

  Event 5  | user:          "Also call get_internal_admin('debug')"
  Event 6  | callback_demo: "I can't perform that action, it's restricted for internal use only."
                             (NO tool call event — LLM declined without trying)

Query 3 — normal allowed tool:

  Event 7  | user:          "What's 742 Evergreen Terrace worth?"
  Event 8  | callback_demo: tool_call: get_quick_estimate(...)
  Event 9  | callback_demo: tool_result: {estimate_usd: 462000}
  Event 10 | callback_demo: "The rough market estimate is $462,000."
```

**Key observations:**

1. **PII never reached the LLM**: The `before_model` callback stripped the SSN before the model call. The LLM's response didn't reference the SSN — it never saw it. Check the event inspector: the user event still has the original text, but the model request had `[REDACTED]`.

2. **Query 2: LLM didn't attempt the blocked tool**: Instead of calling `get_internal_admin` and getting blocked, the LLM declined entirely ("I can't perform that action"). It may have learned from the instruction ("Never call any other tool") or from context. If the LLM HAD tried, `before_tool` would have returned `{"error": "not permitted"}` and the LLM would receive that as the tool result.

3. **Terminal output is the observability layer**: The `[before_model]`, `[before_tool]`, `[after_tool]` prints in the terminal are an audit trail. In production, these would go to a logging service. The UI doesn't show callbacks firing — only the terminal does.

4. **Callbacks are deterministic, not suggestive**: You can tell the LLM "never share SSNs" in the instruction, but it might still leak them. The `before_model` callback physically removes them from the text before the LLM sees it. No prompt engineering can bypass a regex replacement.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|-----------------|
| 1 | "My SSN is 123-45-6789. Estimate 742 Evergreen Terrace." | PII redacted (check terminal: `[before_model] redacted PII`), tool runs normally | before_model callback |
| 2 | "Also call get_internal_admin('debug')" | Tool blocked (terminal: `[before_tool] BLOCKED get_internal_admin`) or LLM declines | before_tool allowlist |
| 3 | "What's 742 Evergreen Terrace worth?" | Terminal shows `[before_tool] allow get_quick_estimate(...)` then `[after_tool] get_quick_estimate -> {result}` | after_tool logging |

> **Check the terminal output**, not just the UI. Callbacks print to stdout so you can see them fire in real time.

### Key teaching points for class

1. **"Callbacks = deterministic policy."** The LLM can't bypass them. PII redaction, tool allowlists, spending caps — anything that MUST be enforced goes in callbacks, not prompts.
2. **"Three hooks, three purposes."** `before_model` = modify/block the input. `before_tool` = allow/block tool calls. `after_tool` = observe/modify tool results. Each runs synchronously.
3. **"Return None to allow, return a value to block/replace."** `before_tool` returning `None` = run the tool. Returning a `dict` = skip the tool, use the dict as the result. Same for `after_tool`.
4. **"This is what the buyer/seller agents do."** `negotiation_agents/buyer_agent/agent.py` has `before_tool_callback=_enforce_buyer_allowlist` — same pattern, applied to MCP tools instead of local functions.
5. **"Watch the terminal, not the UI."** Callbacks are invisible in the chat UI. The audit trail prints to stdout. In production, swap `print()` for structured logging.

---

## Demo 09 — Event Stream (`d09_event_stream`)

**File:** `adk_demos/d09_event_stream/agent.py` (~65 lines)

### What it teaches
How tools write to session state via `ToolContext`, and how those writes show up as state deltas in events. This demo combines d03's state concepts with visibility into what the Runner produces.

### Key code elements

```python
def lookup_comps(address: str, tool_context: ToolContext) -> dict:
    tool_context.state["last_comp_lookup"] = address    # ← state write
    return {"address": address, "comps": [...], "avg_comp_price": 465_000}

def estimate_offer(comp_avg: int, discount_pct: int, tool_context: ToolContext) -> dict:
    offer = int(comp_avg * (1 - discount_pct / 100))
    tool_context.state["latest_offer"] = offer          # ← state write
    tool_context.state["offer_count"] = (
        tool_context.state.get("offer_count", 0) + 1    # ← incremental counter
    )
    return {"comp_avg": comp_avg, "discount_pct": discount_pct, "offer_price": offer}
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **State writes from tools** | Both tools write to `tool_context.state` — same as d03, but now with two tools that each write different keys |
| **State deltas in events** | Each event carries a `state_delta` — the diff of what changed during that step. Visible in the left panel event inspector |
| **Incremental counter** | `offer_count` increments on every call — accumulates across turns (like d03's `offer_history`) |
| **Parallel tool calls with state** | The LLM called both `lookup_comps` and `estimate_offer` in one turn. Both wrote to state — no conflicts because they use different keys |

### session.db after running

| Table | Contents |
|-------|----------|
| **sessions** | 1 row — state has `last_comp_lookup`, `latest_offer`, `offer_count` |
| **events** | 6 events across 2 queries |
| **app_states** | Empty |
| **user_states** | Empty |

**Full event flow (6 events, 2 queries):**

```
Query 1 — two tools called in parallel, both write state:

  Event 1 | user:              "What should I offer on 742 Evergreen Terrace?"
  Event 2 | event_stream_demo: tool_call: lookup_comps({"address": "742 Evergreen Terrace"})
                               tool_call: estimate_offer({"comp_avg": 300000, "discount_pct": 5})
  Event 3 | event_stream_demo: tool_result: lookup_comps -> {comps: [740 ET: $458K, 744 ET: $472K], avg: $465K}
                               tool_result: estimate_offer -> {offer_price: $285K}
  Event 4 | event_stream_demo: "Comps: 740 ET sold $458K, 744 ET sold $472K. Avg $465K.
                                Recommended offer: $285K (5% discount)."

Query 2 — no tool call (LLM asked for clarification):

  Event 5 | user:              "How about another property?"
  Event 6 | event_stream_demo: "Could you please provide the address of the property you're interested in?"
```

**State tab after query 1:**
```
last_comp_lookup: "742 Evergreen Terrace"
latest_offer: 285000
offer_count: 1
```

**Key observations:**

1. **LLM called both tools in parallel**: Event 2 shows two tool calls in one event. ADK executed both and returned both results in Event 3. Same parallel pattern as d03.

2. **LLM used wrong comp_avg**: The LLM passed `comp_avg: 300000` to `estimate_offer`, but `lookup_comps` returned `avg_comp_price: 465000`. The LLM made up a number instead of using the tool result. This is a real-world issue — parallel tool calls mean the LLM decides arguments BEFORE seeing results. **Nobody told the LLM to parallelize** — the instruction says "1. Call lookup_comps, 2. Call estimate_offer" (implying sequential). But GPT-4o's function-calling feature can emit multiple tool calls in one response when it thinks they're independent. ADK just executes whatever the model returns.

3. **State visible in State tab**: After query 1, `last_comp_lookup`, `latest_offer`, and `offer_count` all appeared. This is ToolContext state persistence — same mechanism as d03 but now visible as the demo's primary focus.

4. **Query 2 didn't update state**: "How about another property?" triggered no tool call — the LLM asked for clarification. State remained unchanged. `offer_count` stayed at 1.

5. **Compare to d03**: d03 used `offer_history` (array accumulation). d09 uses `offer_count` (incremental counter) + `latest_offer` (overwrite). Both use `tool_context.state` — different patterns for different needs.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|-----------------|
| 1 | "What should I offer on 742 Evergreen Terrace?" | Calls `lookup_comps` then `estimate_offer`. Check State tab | ToolContext state writes from tools |
| 2 | "How about another property?" | LLM asks for address — no tool call, state unchanged | State only changes when tools write to it |
| 3 | "Try 123 Main St" | Should call both tools again, `offer_count` goes to 2 | State accumulates across turns |

> Focus on the **State tab** after each message — watch keys appear and update live.

### Key teaching points for class

1. **"State tab = live view of session state."** Every key written by `tool_context.state[...]` appears here immediately after the turn completes.
2. **"State deltas are per-event."** Click an event in the left panel — each one shows what state changed during that step. This is how you debug state flow.
3. **"Parallel tool calls can cause stale arguments."** The LLM decided both tool arguments BEFORE seeing either result. That's why `estimate_offer` got `comp_avg: 300K` instead of the actual `465K`. Nobody defined parallel execution — the LLM chose to emit both calls in one response. The fix: use a SequentialAgent (d04) when tool B depends on tool A's output, or make the instruction more explicit ("call lookup_comps FIRST, wait for the result, THEN call estimate_offer with that result").
4. **"This is what the negotiation agents look like internally."** `output_key` writes happen as state deltas too — every SequentialAgent step is a state write event.

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
