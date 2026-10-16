# Module 2 — Demo Walkthrough & Concept Notes

> **Audience:** Learners working through the 9 ADK demos (`d01`–`d09`) and the 3 A2A demos (`a2a_10`–`a2a_12`) plus the orchestrated negotiation (`a2a_13`), result delivery (`a2a_14`) and error handling (`a2a_15`). Use as a guided tour while you run.
> **Prerequisites:** Python + `OPENAI_API_KEY` set. Familiarity with `mcp_deep_dive.md` helps once you reach demo 02.
> **Read this *while* running:** the demos in `m2_adk_multiagents/adk_demos/` and the negotiation system in `m2_adk_multiagents/negotiation_agents/`. Sections are numbered to match the demos.
> **Read this next:** [`google_adk_overview.md`](google_adk_overview.md) and [`a2a_protocols.md`](a2a_protocols.md) for the conceptual deep-dives. [`adk_quick_reference.md`](adk_quick_reference.md) is the one-page lookup.
>
> **TL;DR:** Per-demo narration covering expected output, session.db state changes, key observations, and production patterns. Read alongside the code to consolidate the M2 surface area, which is the largest in the workshop.

---

## Demo 01 — Basic LlmAgent (`d01_basic_agent`)

**File:** `adk_demos/d01_basic_agent/agent.py` (~40 lines)

### What it teaches
The simplest possible ADK agent: one `LlmAgent` with one function tool.

### How to run

```bash
adk web m2_adk_multiagents/adk_demos/
```

Open http://localhost:8000, select `d01_basic_agent` from the dropdown.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|------------------|
| 1 | "What's 742 Evergreen Terrace worth?" | Calls `get_quick_estimate` → $462K, high confidence | Basic tool call flow |
| 2 | "How about 123 Main St?" | Calls tool → $380K, medium confidence | Different data, same tool |
| 3 | "What about 999 Unknown Ave?" | Calls tool → $450K, **low** confidence (fallback) | Tool handles unknown inputs gracefully |
| 4 | "What's the best neighborhood in Austin?" | Does NOT call tool — answers from LLM knowledge | LLM decides when tools are relevant |

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
| `app:total_offers` | 42 (same for everyone) | 42 (same for everyone) |

In `adk web`, the `user_id` is always `"user"` — the UI has no way to switch users — so on its own it can't show the difference between `user:` and `app:`. A real app gets multiple users by creating its own `Runner` and passing each person's `user_id`; the Demo 03 section below walks through what would differ.

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
5. **Compare to M1:** In `github_agent_client.py`, you hand-wrote the tool loop (call LLM → check for tool_calls → execute → feed back). Here, ADK does all of that. You just declare `tools=[fn]`.

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

In the `adk web` demos (d01–d09), you never write session or runner code. `adk web` handles it all:

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

**You don't need this in the workshop.** It's here so you can answer "how would I do this without `adk web`?" if a student asks. For a complete runnable version, see Demo 09's terminal script `adk_demos/d09_event_stream/run_event_stream.py`. The A2A terminal scripts (10–12) don't show this — they're HTTP clients talking to `adk web --a2a`, which handles sessions server-side.

---

## Demo 02 — MCP Tools (`d02_mcp_tools`)

**File:** `adk_demos/d02_mcp_tools/agent.py` (~90 lines)

### What it teaches
How ADK connects to an MCP server and auto-discovers its tools — here a **remote** server over **Streamable HTTP** that requires a **signed token**. The LLM sees MCP tools exactly like local Python functions, and the server decides what this caller may do:

| Layer | Enforced by | Rule | What you see in d02 |
|---|---|---|---|
| Authentication | Pricing server (JWT check) | Valid, unexpired token signed with `PRICING_JWT_SECRET` | Bad token → **401**, ADK loads **no tools** |
| Server authorization | Pricing server | Token must have `pricing:read` | `guest` token → **403**, no tools |
| Tool authorization | Inside each tool | `get_market_price` → `pricing:read`; `calculate_discount` → `pricing:analyze` | `buyer` token: market price ✅, discount ❌ "forbidden" |

### How to run (two terminals)

```bash
# once: put a random PRICING_JWT_SECRET in .env (see .env.example)

# Terminal 1 — the pricing MCP server, protected
python m1_mcp/pricing_server.py --http                        # → http://127.0.0.1:8001/mcp

# Pick an identity — writes PRICING_MCP_TOKEN into .env
python utils/pricing_auth.py --role buyer --write-env         # pricing:read
#   or: --role analyst (pricing:read pricing:analyze) / --role guest (no scopes)

# Terminal 2 — ADK
adk web m2_adk_multiagents/adk_demos/
```

Open http://localhost:8000 and select `d02_mcp_tools`. **To switch identity**, mint another role and restart `adk web` (the token is read when the agent loads):

```bash
python utils/pricing_auth.py --role analyst --write-env   # pricing:read pricing:analyze
python utils/pricing_auth.py --role buyer --write-env     # back to pricing:read only
```

### Walkthrough (actual runs, gpt-4o)

| # | Token | Question | What happened | What it teaches |
|---|-------|----------|---------------|-----------------|
| 1 | buyer | "What's 742 Evergreen Terrace, Austin, TX 78701 worth?" | Calls `get_market_price` → comps, $462K estimate, details | Discovery + an allowed call |
| 2 | buyer | "Calculate the discount range for a 485000 dollar listing in a balanced market, 18 days on market, good condition." | Calls `calculate_discount` → `{"isError": true, "text": "... forbidden: 'buyer-agent' lacks scope 'pricing:analyze' required by this tool (token scopes: pricing:read)"}`. Reply: *"…The specific permission missing is 'pricing:analyze'…"* | **Tool-level authorization**: the tool is listed but not callable for this token |
| 3 | analyst | Same discount question | Calls `calculate_discount` → 2%–5% discount range, suggested offers | Same agent, more scopes, more allowed |
| 4 | invalid | "What's 742 Evergreen Terrace … worth?" | Server log: `401 Unauthorized`; ADK log: `Failed to get tools from toolset MCPToolset`. Reply: *"I can't reach the pricing tools: the MCP server at http://127.0.0.1:8001/mcp rejected the connection or is not running, so no tools were loaded…"* | **Authentication**: no valid token, no tools at all |
| 5 | any valid | "What's the crime rate near 742 Evergreen Terrace?" | No tool call — the agent says it has no crime data | The LLM only knows tools MCPToolset actually discovered |

To try case 4 without editing `.env`, start `adk web` with a bad token in the environment (environment variables win over `.env`): PowerShell `$env:PRICING_MCP_TOKEN='not-a-valid-jwt'; adk web m2_adk_multiagents/adk_demos/` (run `Remove-Item Env:PRICING_MCP_TOKEN` afterwards). For a 403, run `python utils/pricing_auth.py --role guest --write-env` and restart `adk web`.

> If you ask for a discount without giving days on market and condition, the model may ask for them instead of calling the tool. Give all inputs (as in question 2) to make the authorization check happen.

### Key code elements

```python
PRICING_MCP_URL = os.environ.get("PRICING_MCP_URL", "http://127.0.0.1:8001/mcp")
PRICING_MCP_TOKEN = os.environ.get("PRICING_MCP_TOKEN", "").strip()
_headers = {"Authorization": f"Bearer {PRICING_MCP_TOKEN}"} if PRICING_MCP_TOKEN else {}

def _require_tools(callback_context, llm_request):
    """before_model: if the server rejected us, ADK loaded no tools — answer for the model."""
    if llm_request.tools_dict:
        return None
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text="I can't reach the pricing tools: ...")]))

root_agent = LlmAgent(
    name="mcp_tools_agent",
    model="openai/gpt-4o",
    instruction="... If a tool returns an authorization error, tell the user exactly which permission (scope) is missing ...",
    tools=[
        MCPToolset(                                       # ← replaces local function tools
            connection_params=StreamableHTTPConnectionParams(
                url=PRICING_MCP_URL,
                headers=_headers,                          # bearer token on every request
                timeout=30.0,
            )
        )
    ],
    before_model_callback=_require_tools,
)
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`MCPToolset`** | ADK's bridge to MCP servers. Connects, runs `initialize` + `tools/list`, wraps discovered tools for the LLM. All automatic |
| **`StreamableHTTPConnectionParams`** | Connect to a running server by URL, with HTTP headers. The alternatives are `StdioConnectionParams` (ADK spawns the server as a subprocess — what the negotiation agents use) and `SseConnectionParams` (legacy HTTP transport) |
| **Bearer token in headers** | ADK sends `headers` with every MCP request, so the server can authenticate and authorize each call |
| **Auto-discovery** | You don't list tool names anywhere in `agent.py`. ADK discovers them from the server at startup via `tools/list`. Add a new `@mcp.tool()` to the server → ADK picks it up on next restart |
| **Authorization errors are tool results** | A denied call comes back as an MCP error result (`isError: true`); ADK hands it to the model like any tool output, so the model can explain it |
| **Failed connection = no tools** | On 401/403 ADK logs a warning and continues with zero tools from that toolset. The `before_model_callback` turns that into a clear message instead of the model pretending to look things up |
| **Tool source transparency** | The LLM doesn't know (or care) whether a tool is a local Python function (d01) or a remote MCP server (d02). The function-calling interface is identical |

### d01 vs d02 — the key comparison

```
d01: tools=[get_quick_estimate]                                → you wrote the function, ADK reads its signature
d02: tools=[MCPToolset(StreamableHTTPConnectionParams(...))]   → ADK connects to the server, discovers tools via MCP
```

The LLM sees identical function schemas in both cases.

### What happens under the hood

```
adk web starts
  → imports agent.py, sees MCPToolset in tools list
  → POST http://127.0.0.1:8001/mcp  initialize   (Authorization: Bearer <token>)
      pricing server: verify JWT (signature, exp, iss, aud)    → 401 if bad
                      require scope pricing:read                → 403 if missing
  → tools/list → get_market_price, calculate_discount
  → LlmAgent now has 2 callable tools

User: "Calculate the discount range ..."  (buyer token)
  → GPT-4o decides to call calculate_discount
  → ADK sends tools/call with the same bearer token
  → tool runs _require_scope("pricing:analyze") → token has only pricing:read → PermissionError
  → MCP error result → ADK → GPT-4o → "the permission missing is 'pricing:analyze'"
```

### ADK Web UI — what to notice

| UI Element | What to look for |
|------------|------------------|
| **Info tab** | MCP-discovered tool schemas — descriptions come from the `@mcp.tool()` docstrings in `pricing_server.py`. With a bad token, there are none |
| **Tool call badges** | `⚡ calculate_discount` → `✓ calculate_discount` even when denied — click the result to see the `forbidden` error |
| **Pricing server terminal** | `[auth] rejected token: ...` lines for bad tokens |

### Key teaching points for class

1. **"Same agent pattern, different tool source."** Compare d01 and d02 — only `tools=` changed.
2. **"You didn't touch the tools."** `pricing_server.py`'s tools were built in M1; adding auth was a server-side switch (`--http`) plus one scope check per tool.
3. **"401, 403, forbidden — three different layers."** Authentication (who are you), server authorization (may you use this server), tool authorization (may you use this tool).
4. **"Scopes travel in the token."** Switching from buyer to analyst changes nothing in the agent — only the token.
5. **"stdio would bypass all of this."** The negotiation agents launch the same server over stdio, where there's no HTTP request to authenticate — see the M1 study notes ("pricing_server.py --http").

---

## Demo 03 — Sessions & State (`d03_sessions_state`)

**File:** `adk_demos/d03_sessions_state/agent.py` (~100 lines)

### What it teaches
How tools read and write state via `ToolContext`, and how the **key prefix picks the scope** — who the value is shared with and which table of `session.db` it lands in:

| Prefix | Key in this demo | Shared with | Table in `.adk/session.db` |
|---|---|---|---|
| *(none)* | `offer_history` | This conversation only | `sessions` (one row per user per session) |
| `user:` | `user:total_offers` | This user, across all their sessions | `user_states` (one row per user) |
| `app:` | `app:total_offers`, `app:buyers`, `app:highest_offer` | Every user of this agent | `app_states` (one row per agent) |

(`temp:` keys exist too — visible only during the current invocation and never saved.)

### How to run

1. **Before class** (with `adk web` stopped): delete `m2_adk_multiagents/adk_demos/d03_sessions_state/.adk/` so the counters start at 1.
2. `adk web m2_adk_multiagents/adk_demos/` → pick `d03_sessions_state` → keep the **State tab** open.

### Walkthrough (actual run, gpt-4o, empty database)

| # | Type | Tool result | State tab afterwards | Point to make |
|---|------|-------------|----------------------|---------------|
| 1 | "I offer $430,000" | `offers_this_session: 1`, `your_total_offers: 1`, `all_buyers_total_offers: 1` | `offer_history: [430000]`, `user:total_offers: 1`, `app:total_offers: 1`, `app:buyers: ["user"]` | One tool call writes three scopes |
| 2 | "I offer $445,000" | 2 / 2 / 2 | `offer_history: [430000, 445000]`, both counters 2 | State persists across turns |
| 3 | **New Session** (before typing) | — | No `offer_history`; `user:total_offers: 2` and the `app:` keys are already there | Session state is per conversation; `user:` and `app:` outlive it |
| 4 | "How many offers have I made?" | `get_offer_history` → `this_session: []`, `this_buyer: 2`, `all_buyers: 2` | Unchanged | Reading all three scopes |
| 5 | "I offer $450,000" | `offers_this_session: 1`, `your_total_offers: 3`, `all_buyers_total_offers: 3` | `offer_history: [450000]`, `user:total_offers: 3`, `app:total_offers: 3` | User state keeps counting in the new session |

### Why `user:` and `app:` look the same here

The `adk web` UI always runs as one user, `user_id="user"` — it has no login or user switcher. With a single user, `user:` and `app:` counters move together. Explain the difference with a second user:

| | After alice's 3 offers | Then bob makes 1 offer |
|---|---|---|
| alice's `user:total_offers` | 3 | 3 (unchanged — bob has his own row) |
| bob's `user:total_offers` | — | 1 |
| `app:total_offers` (everyone) | 3 | **4** (one shared row) |
| `app:buyers` | `["alice"]` | `["alice", "bob"]` |

All of this lives in the **same** `session.db`: `sessions` and `user_states` rows are keyed by `user_id`, while `app_states` has a single row for the agent. A real app gets multiple users by creating its own `Runner` and passing each person's `user_id` to `runner.run_async(...)` — `adk web` just always passes `"user"`.

### If something goes wrong

| Symptom | Fix |
|---|---|
| State doesn't change after an offer | The model answered without calling `record_offer`. Repeat with an explicit amount: "I offer $430,000" |
| Counts don't start at 1 | Old data in the database. Stop `adk web` and delete the `.adk/` folder |

### Key code elements

```python
def record_offer(price: int, tool_context: ToolContext) -> dict:
    state = tool_context.state

    history = [*state.get("offer_history", []), price]          # session scope — new list, not mutated
    state["offer_history"] = history

    user_total = state.get("user:total_offers", 0) + 1         # user scope — increment its own value
    state["user:total_offers"] = user_total

    state["app:total_offers"] = state.get("app:total_offers", 0) + 1     # app scope — all users
    buyers = state.get("app:buyers", [])
    if tool_context.user_id not in buyers:                      # who is calling
        state["app:buyers"] = [*buyers, tool_context.user_id]
    ...
```

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`ToolContext`** | ADK injects this into any tool that declares `tool_context: ToolContext`. ADK hides it from the LLM's JSON schema — the LLM never sees it |
| **One `state` view, three scopes** | Tools read and write `tool_context.state` like one dict; ADK routes each key by prefix to the `sessions`, `user_states`, or `app_states` table, and merges them back when loading the session |
| **`tool_context.user_id`** | Identifies the caller. `adk web` always passes `"user"`; a real app passes real user IDs |
| **Prefix stripped in storage** | `user:total_offers` is stored as `total_offers` in the `user_states` row — the table itself is the scope |
| **Update shared state from its own value** | `user:` and `app:` counters are incremented, never derived from session data. Setting `user:total_offers = len(offer_history)` would reset it in every new session, because `offer_history` starts empty there |
| **App state is shared and unguarded** | Every user can read and write `app:` keys. Here that would expose the highest offer and buyer IDs to everyone — fine for a demo, but a privacy decision in a real app |

### Key observations

1. **One tool call, three tables.** The same `record_offer` call writes `offer_history`, `user:total_offers`, and the `app:` keys — the prefix, not the tool, decides where each lands.

2. **New Session proves the scopes.** Step 3's State tab already shows `user:` and `app:` keys before any message, while `offer_history` is gone.

3. **The State tab shows the merged view.** It lists session keys plus `user:` and `app:` keys (with prefixes) for the current user — the same merged dict the tools see.

4. **One database serves every user.** The `sessions`, `user_states`, `app_states`, and `events` tables are all keyed by `app_name` (and `user_id` where relevant). Many users don't need many databases — the keys keep their data apart.

### Key teaching points for class

1. **"ToolContext is the magic parameter."** Add `tool_context: ToolContext` to any tool function and ADK injects it.
2. **"The prefix is the scope."** No prefix → this conversation. `user:` → this user, forever. `app:` → everyone. `temp:` → this invocation only.
3. **"`adk web` is single-user."** It always uses `user_id="user"`, so `user:` and `app:` look identical here. A production app (FastAPI, Slack bot, …) creates its own `Runner` and passes real user IDs — then they diverge.
4. **"This is how the negotiation agents track rounds."** The `negotiation/agent.py` orchestrator writes session state through tools (`submit_offer`, `submit_decision`) and `output_key`, and reads it back with `{placeholder}`. Exercise 08 uses `app:` state for shared market data.

---

## Demo 04 — SequentialAgent (`d04_sequential`)

**File:** `adk_demos/d04_sequential/agent.py` (~55 lines)

### What it teaches
How to chain multiple agents in a pipeline where each agent's output feeds the next agent's input via session state.

### How to run

```bash
adk web m2_adk_multiagents/adk_demos/
```

Open http://localhost:8000, select `d04_sequential` from the dropdown.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|------------------|
| 1 | "Research this property" (or any message) | Three agents fire in sequence: market_brief → offer_drafter → polisher | Pipeline execution order |
| 2 | After run, check **State tab** | See `market_summary`, `offer_text`, `final_email` keys | `output_key` state passing |

> Watch the Events panel — you'll see 3 different `author` names firing in order.

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

### How to run

```bash
adk web m2_adk_multiagents/adk_demos/
```

Open http://localhost:8000, select `d05_parallel` from the dropdown.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|------------------|
| 1 | "Gather signals" (or any message) | Three agents fire concurrently: schools, comps, inventory | Parallel fan-out |
| 2 | After run, check **State tab** | See `schools`, `comps`, `inventory` keys all populated | Independent state keys |

> Compare timestamps in Events — all 3 agents should start at roughly the same time (unlike d04 which is sequential).

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

### Key teaching points for class

1. **"ParallelAgent = fan-out."** Independent tasks that don't depend on each other. Use it when you'd otherwise call 3 APIs sequentially but they could run at the same time.
2. **"Same `output_key` pattern, different orchestration."** d04 and d05 both use `output_key` to write to state. The difference is SequentialAgent (ordered) vs ParallelAgent (concurrent).
3. **"Each agent MUST write to a different key."** If two agents wrote to the same `output_key`, the last one to finish would overwrite the other. No merge — just overwrite.
4. **"Combine them."** Exercise 03 asks students to nest a ParallelAgent inside a SequentialAgent — parallel research first, then sequential strategy + risk assessment. That's the real-world pattern.

---

## Demo 06 — LoopAgent (`d06_loop`)

**File:** `adk_demos/d06_loop/agent.py` (~55 lines)

### What it teaches
How `LoopAgent` iterates sub-agents until a stop condition — either `max_iterations` or an explicit escalation from a callback. This is the ADK equivalent of an FSM termination guarantee.

### How to run

```bash
adk web m2_adk_multiagents/adk_demos/
```

Open http://localhost:8000, select `d06_loop` from the dropdown.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|------------------|
| 1 | "start" | Haggler proposes prices. Loop breaks when price hits $450K–$470K range or max 5 iterations | LoopAgent + escalation |
| 2 | After run, check **State tab** | See `proposal` (the last price) and `loop_exit_reason` (set only if the loop stopped early) | output_key overwrites each iteration |
| 3 | Run again (New Session) | Different prices each time (LLM varies) but always stops ≤5 iterations | Bounded termination |

> Watch the Events panel for iteration count. If 1 iteration, escalation fired immediately. If 5, the range was never hit.

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
        callback_context.state["loop_exit_reason"] = f"{price:,} is in range"  # ← required (see gotcha)
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
| **`max_iterations`** | Hard upper bound. Guarantees termination even if the callback never fires. Same guarantee as an FSM's `max_turns` |
| **`after_agent_callback`** | Runs after each sub-agent completes. Receives `CallbackContext` with access to session state and actions |
| **`callback_context.actions.escalate = True`** | The line that breaks the loop. Sets an escalation signal that the parent `LoopAgent` reads. Like setting `is_terminal = True` in an FSM. **Must be paired with a state write** — see the gotcha below |
| **`output_key` in a loop** | Each iteration overwrites the same key (`proposal`). Only the last value survives in state |

> **ADK gotcha — a bare escalate in a callback is silently dropped.** ADK only turns an agent callback into an `Event` when the callback returns content **or changes state**. The `LoopAgent` checks `event.actions.escalate` on the events it receives, so a callback that *only* sets `escalate = True` produces no event and the loop keeps going. Writing `loop_exit_reason` to state makes ADK emit the event that carries the escalation. (Verified on ADK 1.39: with the bare escalate, a proposal of 462000 — in range — did not stop the loop and all 5 iterations ran; with the state write, the loop stops on the first in-range proposal.)

### What happens under the hood

```
User: "start"
  → LoopAgent starts, iteration 1
    → haggler produces "465000" → state["proposal"] = "465000"
    → after_agent_callback: 465K is in range → write loop_exit_reason + escalate = True
    → ADK emits the callback's event (it changed state) → LoopAgent sees escalation → STOP
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
| **sessions** | 1 row per run. State has `proposal` (last price) and, if the loop stopped early, `loop_exit_reason` |
| **events** | 3 events for a run that stops on iteration 1 (user, haggler text, callback escalation) |
| **app_states** | Empty |
| **user_states** | Empty |

**Event flow — early exit (actual run, gpt-4o):**

```
  Event 1 | user:    "start"
  Event 2 | haggler: "465000"            state_delta: {proposal: "465000"}   (output_key)
  Event 3 | haggler: (no text)           state_delta: {loop_exit_reason: "465,000 is in range"}
                                         actions.escalate = True  → LoopAgent STOPS
  Final state: proposal = "465000", loop_exit_reason = "465,000 is in range"
```

Event 3 is emitted by the `after_agent_callback`. It exists **only because the callback wrote state** — that event is what carries `escalate` to the `LoopAgent`.

**Event flow — the bug this demo used to have (bare escalate, no state write):**

```
  Event 1 | user:    "start"
  Event 2 | haggler: "462000"  → in range, callback sets escalate... but no event is emitted
  Event 3 | haggler: "478000"
  Event 4 | haggler: "474000"
  Event 5 | haggler: "471000"
  Event 6 | haggler: "466000"  → hit max_iterations=5, STOP
  Final state: proposal = "466000"  (no loop_exit_reason)
```

**Key observations:**

1. **Non-deterministic**: The LLM proposes different prices each run ("vary your answer each time"). gpt-4o often lands in range on the first try, so expect many 1-iteration runs; widen or narrow the range in `stop_when_in_range` to see longer loops.

2. **`proposal` gets overwritten each iteration**: State only shows the LAST value. Unlike d03 where `offer_history` accumulated as an array, `output_key` with LoopAgent overwrites on each iteration.

3. **Escalation needs an event**: The `LoopAgent` reacts to `event.actions.escalate` on events it receives. A callback that only sets `escalate` produces no event, so the signal never arrives — the "in range but the loop continued" behaviour above. Writing `loop_exit_reason` is what makes the callback visible.

4. **`max_iterations=5` is the safety net**: Even when escalation doesn't fire, the loop always stops at 5. This is the same bounded termination guarantee as an FSM — but for multi-agent orchestration.

5. **Connection to FSM pattern**: `max_iterations` = `max_turns`. `escalate = True` = terminal state. Same principle, different level of abstraction.

### Key teaching points for class

1. **"LoopAgent = bounded iteration."** `max_iterations` guarantees termination. Same FSM principle — the loop MUST stop.
2. **"`escalate = True` breaks the loop — if it reaches the loop."** In a callback, pair it with a state write so ADK emits an event carrying it. The parent LoopAgent reads that event and stops iterating. Like setting `is_terminal = True` in an FSM.
3. **"This is the negotiation loop."** `negotiation/agent.py` uses `LoopAgent(sub_agents=[SequentialAgent(buyer, seller)], max_iterations=5)`. Each iteration is one negotiation round. The seller's `after_agent_callback` checks for ACCEPT and escalates.
4. **"Compare to the naive `while True` problem."** A naive baseline has `while True` with no termination guarantee. LoopAgent replaces that with bounded iteration + explicit escalation. No while True, no emergency exits.
5. **"output_key overwrites in loops."** Each iteration writes the same key. Only the last value survives. If you need history, use `ToolContext.state` like d03 to accumulate an array.

---

## Demo 07 — Agent-as-Tool (`d07_agent_as_tool`)

**File:** `adk_demos/d07_agent_as_tool/agent.py` (~40 lines)

### What it teaches
How to wrap an entire `LlmAgent` as a callable tool using `AgentTool`. The coordinator agent calls the valuator like a function — but under the hood it's a full LLM call.

### How to run

```bash
adk web m2_adk_multiagents/adk_demos/
```

Open http://localhost:8000, select `d07_agent_as_tool` from the dropdown.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|------------------|
| 1 | "What should I offer on 742 Evergreen Terrace, Austin TX 78701?" | Coordinator calls `valuator` tool, gets valuation, writes offer recommendation | AgentTool delegation |
| 2 | "What's the weather in Austin?" | Coordinator answers directly (no valuation needed) | Coordinator decides WHEN to delegate |

> In Events, look for the `valuator` tool call — it looks like a function call but it's actually running a full LlmAgent under the hood.

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

### Key teaching points for class

1. **"AgentTool = agent as a function."** The coordinator calls `valuator(...)` like any other tool. Under the hood, ADK runs a full LlmAgent and returns its text as the tool result.
2. **"The coordinator stays in control."** Unlike `sub_agents` where the LLM transfers to a sub-agent, `AgentTool` returns the result to the caller. The coordinator can combine results from multiple agent-tools in one response.
3. **"`description` is the function docstring."** The coordinator's LLM reads `valuator.description` to decide when to call it. Write it like you'd write a tool description — clear, specific, actionable.
4. **"Notice the hallucinated price."** Without MCP tools, the valuator estimated $750K–$900K (Austin downtown LLM knowledge). With d02's MCP tools, `get_market_price` returned $462K. This is the difference between LLM reasoning and grounded data.
5. **"Two LLM calls = more expensive."** Each delegation costs an extra model call. Use AgentTool when the specialist has genuinely different expertise or tools — not just for code organization.

---

## Demo 08 — Callbacks (`d08_callbacks`)

**File:** `adk_demos/d08_callbacks/agent.py` (~150 lines)

### What it teaches
How to inject policy into an agent WITHOUT changing its instruction. Five hooks, in the order they fire, each doing something visible:

| Hook | Policy in this demo | Type of control |
|---|---|---|
| `before_agent_callback` | Count turns | Agent-level (the only hooks workflow agents also have) |
| `before_model_callback` | Redact SSNs from the request | Input guardrail |
| `before_tool_callback` | Block `get_internal_admin` | Access control |
| `after_tool_callback` | Strip `seller_floor_usd` from tool results | Data filtering |
| `after_model_callback` | Remove phone numbers from the reply | Output guardrail |

The instruction is just "Use your tools to answer questions about property values, sellers, and listing agents." It does **not** forbid the admin tool, mention SSNs, or ask for privacy — every rule above lives only in code.

### How to run

```bash
adk web m2_adk_multiagents/adk_demos/
```

Open http://localhost:8000, select `d08_callbacks` from the dropdown. Watch the **State tab** (`turn_count`, `callback_audit`) — or the terminal, where each callback also prints a `[hook] ...` line.

### Questions to try in order (same session)

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|------------------|
| 1 | "My SSN is 123-45-6789. What's 742 Evergreen Terrace worth?" | SSN redacted; `get_quick_estimate` allowed; `seller_floor_usd` stripped; if the reply mentions the listing agent's phone, it becomes `[phone removed]` | before_model, before_tool (allow), after_tool, after_model |
| 2 | "What's the seller's minimum acceptable price for 742 Evergreen Terrace?" | The model **calls** `get_internal_admin` (its description invites it) → `before_tool` BLOCKS it → model says it can't access that | before_tool (block) |
| 3 | "Who is the listing agent for 742 Evergreen Terrace and how do I contact them?" | Name is shared, phone number is not | after_model output guardrail |

### Key code elements

```python
def get_quick_estimate(address: str) -> dict:
    return {"address": address, "estimate_usd": 462_000,
            "listing_agent": "Jane Doe, (512) 555-0143",
            "seller_floor_usd": 445_000}            # confidential — after_tool strips it

def get_internal_admin(query: str) -> dict:
    """Internal admin lookup: seller records, minimum prices, and owner details...
    Use this for questions about a seller's minimum price."""   # ← tempting on purpose

def redact_pii(callback_context, llm_request):          # before_model
    for content in llm_request.contents or []:
        for part in content.parts or []:
            if part.text and SSN_RE.search(part.text):
                part.text = SSN_RE.sub("[REDACTED-SSN]", part.text)
    return None                                         # None = call the LLM with the edited request

def enforce_allowlist(tool, args, tool_context):        # before_tool
    if tool.name not in ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not permitted for this agent"}  # dict = skip the tool
    return None

def strip_confidential(tool, args, tool_context, tool_response):   # after_tool
    if CONFIDENTIAL_FIELDS & tool_response.keys():
        return {k: v for k, v in tool_response.items() if k not in CONFIDENTIAL_FIELDS}  # replaces the result
    return None

def scrub_reply(callback_context, llm_response):        # after_model
    for part in llm_response.content.parts or []:
        if part.text and PHONE_RE.search(part.text):
            part.text = PHONE_RE.sub("[phone removed]", part.text)
            return llm_response                         # LlmResponse = replaces the model's reply
    return None

root_agent = LlmAgent(..., tools=[get_quick_estimate, get_internal_admin],
    before_agent_callback=count_turns,
    before_model_callback=redact_pii,
    before_tool_callback=enforce_allowlist,
    after_tool_callback=strip_confidential,
    after_model_callback=scrub_reply)
```

Each callback also calls `_audit(...)`, which prints a line and appends to `state["callback_audit"]`.

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`before_agent_callback`** | Runs once per turn, before any model call. Return `Content` to skip the agent entirely. Workflow agents (`LoopAgent`, `SequentialAgent`, `ParallelAgent`) have this and `after_agent_callback` — but none of the model/tool hooks |
| **`before_model_callback`** | Runs before EVERY LLM call. Mutate `llm_request` in place to edit it, or return an `LlmResponse` to skip the LLM entirely (the ex05 solution does this to block prompt injection) |
| **`before_tool_callback`** | Runs before EVERY tool call. Return `None` to allow, return a `dict` to block (the dict becomes the tool's "result") |
| **`after_tool_callback`** | Runs after EVERY tool returns. Return `None` to keep the result, or a `dict` to replace it — here, to remove a confidential field before the LLM sees it |
| **`after_model_callback`** | Runs after EVERY LLM response. Return `None` to keep it, or an `LlmResponse` to replace it — the last chance to stop something leaving the agent |
| **Policy without prompts** | None of these rules is in the instruction. Prompt rules are suggestive; callbacks are deterministic |
| **Callbacks can write state** | `callback_context.state` / `tool_context.state` work in callbacks too — that's how `callback_audit` reaches the State tab |

### What happens under the hood (actual run, gpt-4o)

```
Turn 1: "My SSN is 123-45-6789. What's 742 Evergreen Terrace worth?"
  [before_agent] turn 1 started
  [before_model] redacted SSN in 1 message(s)       → LLM sees [REDACTED-SSN]
  LLM → get_quick_estimate("742 Evergreen Terrace")
  [before_tool]  allowed get_quick_estimate
  [after_tool]   stripped ['seller_floor_usd']       → LLM gets estimate + listing agent only
  [before_model] redacted SSN in 1 message(s)       → history still contains the SSN, so it is scrubbed again
  [after_model]  removed phone number(s) from the reply
  Reply: "...approximately $462,000. The listing agent ... is Jane Doe, and you can contact her at [phone removed]."

Turn 2: "What's the seller's minimum acceptable price for 742 Evergreen Terrace?"
  [before_agent] turn 2 started
  LLM → get_internal_admin("742 Evergreen Terrace")   ← the model DID try
  [before_tool]  BLOCKED get_internal_admin           → result: {"error": "... not permitted ..."}
  Reply: "I'm unable to access information about the seller's minimum acceptable price..."

Turn 3: "Who is the listing agent ... and how do I contact them?"
  [before_agent] turn 3 started
  Reply: "The listing agent ... is Jane Doe. You can contact her by phone at [phone removed]."
```

### session.db after running

| Table | Contents |
|-------|----------|
| **sessions** | 1 row — state has `turn_count: 3` and a 12-entry `callback_audit` list |
| **events** | User messages, tool calls/results, replies, plus state-delta events from `before_agent` |
| **app_states** | Empty |
| **user_states** | Empty |

### Key observations

1. **The block now actually fires.** With no "never call other tools" line in the prompt, the model reaches for `get_internal_admin` as soon as it's asked about the seller's minimum. Only the callback stops it — which is the whole point: the policy holds even when the prompt says nothing.

2. **The redaction only edits the model's copy.** ADK deep-copies session content into each `llm_request`, so the stored user event still contains `123-45-6789`. That's also why `[before_model] redacted SSN` repeats on every later model call: the history still has it, and every request is scrubbed again.

3. **`after_tool` controls what the LLM can know.** `seller_floor_usd` never appears in the tool result the model sees, so it can't leak it no matter what it's asked. Same idea as the buyer/seller allowlists, but at field level.

4. **`after_model` catches things regardless of source.** Turn 1's phone number came from a tool result the model chose to quote. In turn 3 the model repeated `[phone removed]` from its own earlier (already scrubbed) reply, so the guard had nothing new to remove. Either way, no number left the agent.

5. **State tab = audit trail.** Callbacks are invisible in the chat UI, but every firing is recorded in `callback_audit`. In production you'd send these to structured logging as well.

### Key teaching points for class

1. **"Callbacks = deterministic policy."** The LLM can't bypass them. PII redaction, tool allowlists, field filtering, spending caps — anything that MUST be enforced goes in callbacks, not prompts.
2. **"Five hooks, five jobs."** `before_agent` = per-turn setup. `before_model` = guard the input. `before_tool` = allow/block actions. `after_tool` = filter what the model learns. `after_model` = guard the output.
3. **"Return None to allow, return a value to block/replace."** `before_tool` → `dict` skips the tool. `after_tool` → `dict` replaces the result. `before_model` → `LlmResponse` skips the LLM. `after_model` → `LlmResponse` replaces the reply.
4. **"This is what the buyer/seller agents do."** `negotiation_agents/buyer_agent/agent.py` has `before_tool_callback=_enforce_buyer_allowlist` — same pattern, applied to MCP tools. The seller's `after_tool_callback` captures its floor for `submit_decision`.
5. **"Workflow agents get the agent-level hooks only."** `before_agent` / `after_agent` work on `LoopAgent`, `SequentialAgent`, and `ParallelAgent` too (ex06, ex07, ex08 use them); the model and tool hooks are `LlmAgent`-only.

---

## Demo 09 — Event Stream (`d09_event_stream`)

**Files:**
- `adk_demos/d09_event_stream/agent.py` (~75 lines) — the agent (`adk web`)
- `adk_demos/d09_event_stream/run_event_stream.py` (~140 lines) — terminal script that drives the same agent with `Runner.run_async()` and prints every `Event`

### What it teaches
How tools write to session state via `ToolContext`, and how those writes show up as state deltas in events. This demo combines d03's state concepts with visibility into what the Runner produces — first through the web UI, then by printing the raw event stream yourself.

### How to run

```bash
# Option A — web UI
adk web m2_adk_multiagents/adk_demos/

# Option B — terminal: print every Event the Runner yields
python m2_adk_multiagents/adk_demos/d09_event_stream/run_event_stream.py
python m2_adk_multiagents/adk_demos/d09_event_stream/run_event_stream.py --raw   # + raw Event JSON
```

For option A, open http://localhost:8000, select `d09_event_stream` from the dropdown.

### Questions to try in order

| # | Question | Expected behavior | What it teaches |
|---|----------|-------------------|------------------|
| 1 | "What should I offer on 742 Evergreen Terrace?" | Calls `lookup_comps` then `estimate_offer`. Check State tab | ToolContext state writes from tools |
| 2 | "How about another property?" | LLM asks for address — no tool call, state unchanged | State only changes when tools write to it |
| 3 | "Try 123 Main St" | Should call both tools again, `offer_count` goes to 2 | State accumulates across turns |

> Focus on the **State tab** after each message — watch keys appear and update live.

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
| **Sequential tool chaining** | The LLM called `lookup_comps` first, got the result, then called `estimate_offer` with the actual comp average. The instruction's numbered steps ("1. Call lookup_comps, 2. Call estimate_offer") guided the model to chain them correctly |

### session.db after running

| Table | Contents |
|-------|----------|
| **sessions** | 1 row — state has `last_comp_lookup`, `latest_offer`, `offer_count` |
| **events** | 6 events for 1 query |
| **app_states** | Empty |
| **user_states** | Empty |

**Full event flow (6 events, 1 query):**

```
Query 1 — two tools called sequentially, both write state:

  Event 1 | user:              "What should I offer on 742 Evergreen Terrace?"
  Event 2 | event_stream_demo: tool_call: lookup_comps({"address": "742 Evergreen Terrace"})
  Event 3 | event_stream_demo: tool_result: lookup_comps -> {comps: [740 ET: $458K, 744 ET: $472K], avg: $465K}
  Event 4 | event_stream_demo: tool_call: estimate_offer({"comp_avg": 465000, "discount_pct": 5})
  Event 5 | event_stream_demo: tool_result: estimate_offer -> {offer_price: $441,750}
  Event 6 | event_stream_demo: "Comps: 740 ET sold $458K, 744 ET sold $472K. Avg $465K.
                                Recommended offer: $441,750 (5% discount)."
```

**State tab after query 1:**
```
last_comp_lookup: "742 Evergreen Terrace"
latest_offer: 441750
offer_count: 1
```

**Key observations:**

1. **LLM called tools sequentially**: The instruction says "1. Call lookup_comps, 2. Call estimate_offer" and the LLM followed this order. Event 2 calls `lookup_comps`, Event 3 returns the result, Event 4 calls `estimate_offer` with the actual `comp_avg: 465000` from the lookup. The LLM chained the calls correctly — it used the real data, not a hallucinated number.

2. **Correct offer calculation**: $465,000 × 0.95 = $441,750. The LLM passed the actual comp average to `estimate_offer`, so the math checks out. Compare this to what happens if the LLM parallelizes (it would have to guess `comp_avg` before seeing the lookup result).

3. **State visible in State tab**: After the query, `last_comp_lookup`, `latest_offer`, and `offer_count` all appeared. This is ToolContext state persistence — same mechanism as d03 but now visible as the demo's primary focus.

4. **Compare to d03**: d03 used `offer_history` (array accumulation). d09 uses `offer_count` (incremental counter) + `latest_offer` (overwrite). Both use `tool_context.state` — different patterns for different needs.

> **Note on parallel tool calls:** Some models may call both tools in parallel (deciding arguments BEFORE seeing results), which can cause `estimate_offer` to receive a hallucinated `comp_avg`. If you see a wrong offer price, this is why — the fix is to use a SequentialAgent (d04) when tool B depends on tool A's output.

### Terminal version — `run_event_stream.py`

The web UI renders events for you. The terminal script shows what is underneath: an explicit `InMemoryRunner`, an explicit session, and a plain `async for event in runner.run_async(...)` loop that prints each field of every `Event`. It sends two turns in the same session by default.

```python
runner = InMemoryRunner(agent=root_agent, app_name="d09_event_stream")
session = await runner.session_service.create_session(app_name=..., user_id=...)

async for event in runner.run_async(user_id=..., session_id=session.id, new_message=message):
    event.author                    # who produced it
    event.content.parts             # function_call / function_response / text
    event.actions.state_delta       # state keys changed by this step
    event.actions.escalate          # loop-exit signal (None here)
    event.is_final_response()       # True only for the turn's last text answer
```

**Actual output (gpt-4o, turn 1 — trimmed):**

```
TURN 1  user: What should I offer on 742 Evergreen Terrace, Austin, TX 78701?

  [Event 1] author=event_stream_demo  final_response=False
    function_call      lookup_comps({"address": "742 Evergreen Terrace, Austin, TX 78701"})

  [Event 2] author=event_stream_demo  final_response=False
    function_response  lookup_comps -> {"address": ..., "comps": [...], "avg_comp_price": 465000}
    state_delta        {"last_comp_lookup": "742 Evergreen Terrace, Austin, TX 78701"}

  [Event 3] author=event_stream_demo  final_response=False
    function_call      estimate_offer({"comp_avg": 465000, "discount_pct": 5})

  [Event 4] author=event_stream_demo  final_response=False
    function_response  estimate_offer -> {"comp_avg": 465000, "discount_pct": 5, "offer_price": 441750}
    state_delta        {"latest_offer": 441750, "offer_count": 1}

  [Event 5] author=event_stream_demo  final_response=True
    text               ... The average comp price is $465,000. After considering a 5% discount,
                       I recommend making an offer of $441,750.

  -> run_async yielded 5 events this turn. The session now stores 6 events in total
     (your user messages are stored too, but are not yielded).
  -> session state: {"last_comp_lookup": "...", "latest_offer": 441750, "offer_count": 1}
```

Turn 2 ("Now do the same for 123 Main St, Austin, TX.") yields the same 5-event shape; `offer_count` becomes 2 and the session holds 12 events.

**What to notice in the terminal output:**

1. **5 yielded vs 6 stored.** The web UI shows 6 events because it reads the session; `run_async()` yields only the 5 agent-authored ones. Your message is appended to the session before the agent runs.
2. **State deltas ride on the tool-result events** (2 and 4), not on the tool-call events — the delta is recorded when the tool actually runs.
3. **`final_response=True` appears exactly once per turn**, on the text answer. This is the predicate you use in your own code to pick "the answer" out of the stream.
4. **No hidden magic.** This loop is all `adk web` does on each chat message — plus persisting the session to SQLite and rendering the events.

### Key teaching points for class

1. **"State tab = live view of session state."** Every key written by `tool_context.state[...]` appears here immediately after the turn completes.
2. **"State deltas are per-event."** Click an event in the left panel — each one shows what state changed during that step. This is how you debug state flow.
3. **"Sequential chaining worked here."** The LLM called `lookup_comps` first, got the real comp average ($465K), then called `estimate_offer` with that value. The numbered instruction steps guided the model. If the LLM had parallelized, it would have had to guess `comp_avg` — the fix for that is a SequentialAgent (d04) to enforce ordering.
4. **"This is what the negotiation agents look like internally."** `output_key` writes happen as state deltas too — every SequentialAgent step is a state write event.

---

## Demo 10 — A2A Wire Format & the Task (`a2a_10_wire_lifecycle.py`)

**File:** `a2a_demos/a2a_10_wire_lifecycle.py` (terminal script)

### What it teaches
The A2A protocol on the wire — Agent Card discovery, the JSON-RPC `message/send` request and response — and the **Task** that comes back, taken apart field by field. The script hooks the HTTP client (`httpx` `event_hooks`), so what you see is exactly what was sent and received, not a re-serialization.

It uses the a2a-sdk's current client: `ClientFactory(ClientConfig(...)).create(card)` → `Client`. (The older `A2AClient` class is deprecated.)

### How to run

```bash
# Terminal 1: Start the seller agent with A2A support
adk web --a2a m2_adk_multiagents/negotiation_agents/

# Terminal 2: Run the script
python m2_adk_multiagents/a2a_demos/a2a_10_wire_lifecycle.py
```

> **Before running the script**, try browsing the Agent Cards directly in your browser. `adk web --a2a` reads each agent's `agent.json` and serves it automatically:
> - http://127.0.0.1:8000/a2a/buyer_agent/.well-known/agent-card.json
> - http://127.0.0.1:8000/a2a/seller_agent/.well-known/agent-card.json
>
> (The `negotiation` agent is served by its own A2A server with push notifications — see Demo 14 — at http://127.0.0.1:8003/.well-known/agent-card.json.)
>
> These are the same Agent Cards the script fetches programmatically in Step 1. The JSON you see in the browser comes from `agent.json` in each agent's folder (e.g., `negotiation_agents/buyer_agent/agent.json`).

> **How did the script know where the agent lives?** `--seller-url` is *direct configuration*; the card itself is then found at the *well-known URI*. The third discovery strategy is a **registry**: agents publish their cards to a catalog, and clients search it by skill, tag or keyword (Google Cloud Agent Registry, AGNTCY Agent Directory). A2A doesn't standardize a registry API, so each one differs — see [`a2a_protocols.md` §13.1](a2a_protocols.md#131-how-clients-find-agent-cards--discovery-strategies-and-registries).

### A2A Protocol Objects (the building blocks)

Before reading the output, understand these 4 objects:

**1. Task** — the unit of work in A2A. Created when you POST `message/send`.

```
Task
├── id: "03ca4e87-..."           ← unique identifier
├── contextId: "4f0fff3e-..."    ← ties multiple tasks into one conversation
├── status: "completed"          ← lifecycle: submitted → working → completed/failed
├── history: [Message, ...]      ← all messages exchanged in this task
└── artifacts: [Artifact, ...]   ← durable outputs (the "deliverable")
```

Think of a Task like a support ticket — you submit it, it gets worked on, it completes with a result.

**2. Message** — one turn in the conversation.

```
Message
├── messageId: "msg_4a6c..."
├── role: "user" or "agent"      ← who sent it
├── parts: [Part, ...]           ← the actual content (one or more Parts)
├── contextId                    ← which conversation thread
└── taskId                       ← which task this belongs to
```

**3. Part** — the atomic unit of content inside a Message. Three kinds:

| Kind | What it carries | JSON shape |
|------|----------------|------------|
| **TextPart** | Plain text | `{"kind": "text", "text": "I offer $440K"}` |
| **DataPart** | Structured JSON | `{"kind": "data", "data": {"price": 440000}}` |
| **FilePart** | Binary file | `{"kind": "file", "file": {"uri": "...", "mimeType": "..."}}` |

Demo 10 sends a TextPart and a DataPart together (the offer as text and as structured data). Demo 12 looks at where Parts end up in the returned Task, and Demo 15 sends a FilePart.

**4. Artifact** — a durable output attached to the Task (not the Message).

```
Artifact
├── artifactId: "dd72d5b4-..."
└── parts: [Part, ...]           ← same Part types as Messages
```

Messages are conversational (the back-and-forth). Artifacts are the result — what the Task produced. Think: Messages = email thread, Artifact = the attached report.

**How they relate to what you already know:**

| A2A concept | ADK equivalent | MCP equivalent |
|-------------|---------------|----------------|
| Task | One `runner.run_async()` call | One `tools/call` request |
| Message | User/agent turn in conversation | Request/response |
| Part (TextPart) | `Content.parts[0].text` | `CallToolResult.content[0].text` |
| Artifact | No direct equivalent | No direct equivalent |
| contextId | Session ID | No equivalent (MCP is stateless) |
| Task status | Event stream (`is_final_response()`) | Synchronous (returns when done) |

### What happens in demo 10 (actual run, gpt-4o — abridged)

**Step 1 — Agent Card discovery**
```
──► GET http://127.0.0.1:8000/a2a/seller_agent/.well-known/agent-card.json
◄── HTTP 200  application/json
{
  "capabilities": {"pushNotifications": false, "streaming": true},
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "description": "Real estate seller agent for 742 Evergreen Terrace, Austin TX. ...",
  "name": "seller_agent",
  "preferredTransport": "JSONRPC",
  "protocolVersion": "0.3.0",
  "skills": [{"id": "negotiation_response", "name": "Real Estate Seller Negotiation",
              "tags": ["real_estate", "seller", "negotiation", "mcp"], "examples": [...]}],
  "url": "http://localhost:8000/a2a/seller_agent",
  "version": "1.0.0"
}
```

This is how a client learns what the agent does, where to send messages, which transport to use, and what features are supported — before sending a single message. `ClientFactory.create(card)` reads `url` and `preferredTransport` from it. Like MCP's `tools/list`, but for entire agents.

**Step 2 — `message/send` on the wire**
```
──► POST http://localhost:8000/a2a/seller_agent          ← card.url, not the URL we typed
{
  "id": "b23808c5-...",
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "configuration": {"acceptedOutputModes": [], "blocking": true},   ← wait for the final result
    "message": {
      "kind": "message",
      "messageId": "msg_7af7c873",
      "parts": [
        {"kind": "text", "text": "Opening offer at $440k, 30-day close, pre-approved."},
        {"kind": "data", "data": {"round": 1, "from_agent": "buyer", "message_type": "OFFER",
                                  "price": 440000, "closing_timeline_days": 30, ...}}
      ],
      "role": "user"
    }
  }
}

◄── HTTP 200  application/json
{
  "id": "b23808c5-...",                    ← same id: this is the reply to that request
  "jsonrpc": "2.0",
  "result": {                              ← the Task
    "artifacts": [{"artifactId": "bee4354b-...",
                   "parts": [{"kind": "text", "text": "SELLER: We COUNTER at $477,000 due to the extensive $75,000 in recent upgrades, ..."}]}],
    "contextId": "0918bf29-...",
    "history": [ ...7 messages... ],
    ...
  }
}
```

**Step 3 — the Task, taken apart**
```
  id          162a296b-5515-4458-9601-4eb8b5af4bb5        ← this unit of work (tasks/get uses it)
  contextId   0918bf29-218b-4011-86b2-e21b2dd517c4        ← the conversation it belongs to
  status      completed  at 2026-10-16T12:11:08.856948+00:00
  history     7 message(s) — the conversation so far:
    [0] user  text "Opening offer at $440k, 30-day close, pre-approved.", data keys=['round', 'from_agent', ...]
    [1] user  text "Opening offer at $440k, 30-day close, pre-approved.", data keys=['round', 'from_agent', ...]
    [2] agent data (tool_call get_market_price), data (tool_call get_inventory_level), data (tool_call get_minimum_acceptable_price)
    [3] agent data (tool_result get_market_price), data (tool_result get_inventory_level), data (tool_result get_minimum_acceptable_price)
    [4] agent data (tool_call submit_decision)
    [5] agent data (tool_result submit_decision)
    [6] agent text "SELLER: We COUNTER at $477,000 due to the extensive $75,000 in recent upgrades, including "
  artifacts   1 — the deliverable:
    artifactId=bee4354b-0938-4159-b8ba-967f479b332a  text "SELLER: We COUNTER at $477,000 due to the extensive $75,000 in recent upgrades, including "
```

What to notice:
- **The Task is the response.** `message/send` returned a Task with an `id`, the `contextId` it belongs to, a `status`, the `history`, and `artifacts`.
- **History is the audit trail.** It contains our message (recorded twice — an ADK quirk), the seller's MCP tool calls and results as DataParts, the `submit_decision` call, and the final text.
- **The artifact is the deliverable.** The final reply appears both as the last history message and as the artifact. Code that consumes the result should read the artifact (Demos 11, 13 and 14 do).
- **Only the final state is visible.** `blocking: true` means the server answered once the task was `completed`. Demo 14 shows `submitted → working → completed` as it happens.

> "`completed` means the agent processed the request — not that it agreed, or even understood." Demo 15 (layer 4) sends an offer with no price in it: still `completed`.

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **Agent Card** | JSON discovery document at `/.well-known/agent-card.json`. Contains name, description, skills, capabilities, URL, preferred transport |
| **JSON-RPC `message/send`** | The A2A invocation method. Wraps a Message in a JSON-RPC 2.0 envelope; `configuration.blocking` says whether to wait for the result |
| **Task** | What `message/send` returns: `id`, `contextId`, `status`, `history`, `artifacts` |
| **Task lifecycle** | submitted → working → completed (or failed / canceled / rejected). `completed` = agent responded, not necessarily agreement |
| **contextId** | Returned in the response. Reuse it in subsequent requests to thread a multi-turn conversation (demo 11) |
| **Artifacts** | Durable outputs of the task. The counter-offer text lives here as well as in the history |
| **Parts** | Atomic content units: TextPart, DataPart, FilePart. Demo 10 sends TextPart + DataPart |
| **`ClientFactory` / `Client`** | a2a-sdk's current client. Built from the Agent Card; picks the transport the card declares |

### Key teaching points for class

1. **"MCP and A2A use the same pattern."** MCP: list_tools → tool schema → tools/call. A2A: Agent Card → skills → message/send. Same three operations, different level (tools vs agents).
2. **"The card drives the client."** The request went to `card.url` over `card.preferredTransport`. The client didn't need to be told anything but where the card is.
3. **"Every message/send creates a Task."** It has an id you can look up later (`tasks/get`), a status, and its outputs. Demo 11 shows that each round is a new Task in the same context.
4. **"Artifacts are separate from messages."** History is the conversation (including tool calls); the artifact is the result you hand to the next system.
5. **"No custom server code."** The Agent Card came from `agent.json`. The JSON-RPC endpoint was created by `adk web --a2a`. The seller agent is just a `root_agent = LlmAgent(...)` — ADK did the rest.

---

## Demo 11 — A2A Context Threading (`a2a_11_context_threading.py`)

**File:** `a2a_demos/a2a_11_context_threading.py` (terminal script)

### What it teaches
How `contextId` threads multiple A2A requests into one conversation — and the difference between a **Task** (one unit of work, new every time) and a **context** (the conversation the tasks belong to). Without a contextId, each message starts a new conversation and the agent forgets everything.

### How to run

```bash
# Terminal 1: Start the seller agent with A2A support
adk web --a2a m2_adk_multiagents/negotiation_agents/

# Terminal 2: Run the script
python m2_adk_multiagents/a2a_demos/a2a_11_context_threading.py
```

### What happens

The script sends 3 rounds of offers ($432K → $440K → $446K) to the seller agent, reusing the `contextId` from round 1. Then it calls `tasks/get` on round 1's taskId, and finally sends a **bonus round 4** at $440K (same price as round 2) **without contextId** — proving the seller has no memory without it.

```
Round 1: message/send (no contextId)        → new task A, server assigns context X
Round 2: message/send (contextId X)         → new task B, context X — seller sees round 1
Round 3: message/send (contextId X)         → new task C, context X — seller sees rounds 1-2
tasks/get(A)                                → round 1's task, still there, unchanged
Round 4: message/send (no contextId)        → new task D, NEW context Y — no memory
```

For each round the script prints the taskId, contextId, state, the tools the seller called in that task (read from the task's history DataParts) and the seller's reply (read from the artifact).

### Actual results (gpt-4o, abridged — prices vary run to run)

```
=== round 1 — $432,000 (sent contextId=none) ===
  taskId    3fc7f67a-f40d-4c46-ad2a-482b517ea1c7
  contextId 06264516-70ea-4471-b354-33b94c73f3fc
  state     completed
  tools     get_market_price, get_inventory_level, get_minimum_acceptable_price, submit_decision
  seller    SELLER: COUNTER at $477,000. ...

=== round 2 — $440,000 (sent contextId=X) ===
  taskId    d6a7db58-2ab2-4a61-8b36-599556a9a30e
  contextId 06264516-70ea-4471-b354-33b94c73f3fc
  tools     submit_decision
  seller    SELLER: COUNTER at $472,000. ...

=== round 3 — $446,000 (sent contextId=X) ===
  taskId    5c78919f-83e5-448e-8e2a-e09eec522ac9
  contextId 06264516-70ea-4471-b354-33b94c73f3fc
  tools     submit_decision
  seller    SELLER: ACCEPT at $446,000. ...

=== tasks/get on round 1's taskId ===
  taskId    3fc7f67a-f40d-4c46-ad2a-482b517ea1c7
  state     completed
  tools     get_market_price, get_inventory_level, get_minimum_acceptable_price, submit_decision
  seller    SELLER: COUNTER at $477,000. ...

=== round 4 — $440,000, NO contextId ===
  taskId    b7befb6e-7e6f-4e53-a708-3576692342e6
  contextId 1de09dfa-5de8-48b1-8320-7a6749be13e5
  tools     get_market_price, get_inventory_level, get_minimum_acceptable_price, submit_decision
  seller    SELLER: We must COUNTER at $469,000. ...
```

> **The contrast between round 2 and round 4 is the proof.** Same price ($440K), same seller — but round 2 makes no MCP calls (it already knows the market data and floor from round 1's history), while round 4 calls all three MCP tools again because it has zero memory. The only difference is contextId.

> **Four rounds, four taskIds; two contexts.** Each `message/send` is its own Task. `tasks/get` on round 1's id returns that task exactly as it finished — the conversation moving on doesn't change it.

> **The floor is enforced in code.** Any offer at or above the $445K floor is recorded as ACCEPT by `submit_decision`, whatever the model sent; it reads the floor saved to session state in round 1, which is still there because the contextId is the same. (In an earlier run the model sent `COUNTER $461,000` in round 3 and `submit_decision` recorded `ACCEPT $446,000`.)

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **`contextId`** | A string that ties multiple Tasks into one conversation. Assigned by the server on round 1, reused by the client on rounds 2+. Round 4 proves: drop contextId → drop memory |
| **Task vs context** | Every `message/send` creates a new Task (new taskId). The contextId groups them. `tasks/get` fetches any one task by id |
| **Conversation memory via protocol** | With the same contextId the seller reuses what it learned (no repeat MCP calls). Without it, it starts over and calls every tool again |
| **A2A threading vs ADK sessions** | `contextId` in A2A = `session_id` in ADK. Same concept (conversation continuity), different level (HTTP vs in-process). ADK session state — like the saved floor — persists per contextId too |
| **Acceptance enforced in code** | The seller's `submit_decision` records any offer at or above the floor as ACCEPT, whatever the model sent |

### Key teaching points for class

1. **"contextId = session_id for HTTP."** In d03, session state persisted across turns within `adk web`. Here, `contextId` does the same across HTTP requests. Without it, every POST is a brand new conversation.
2. **"A task is one job; a context is the conversation."** Three rounds → three taskIds, one contextId. You poll or cancel a *task*; you continue a *context*.
3. **"The seller's behavior changed across rounds."** Round 1: full MCP research. Rounds 2–3: no research, just a decision — it remembered. Round 4: full research again.
4. **"$446K crossed the $445K floor — and code made sure it was accepted."** A rule that must hold lives in code (`submit_decision`), not in the prompt.
5. **"Round 4 is the proof by contradiction."** Same $440K as round 2, but no contextId → the seller re-runs every MCP tool as if it were the first offer. **contextId is the ONLY difference.**

---

## Demo 12 — A2A Parts and Artifacts (`a2a_12_parts_and_artifacts.py`)

**File:** `a2a_demos/a2a_12_parts_and_artifacts.py` (terminal script)

### What it teaches
How to send multi-part Messages (TextPart + DataPart in one message), and **where content lives in the Task that comes back**: `history` (the conversation, including MCP tool calls as DataParts), `status.message`, and `artifacts` (the deliverable).

### How to run

```bash
# Terminal 1: Start the seller agent with A2A support
adk web --a2a m2_adk_multiagents/negotiation_agents/

# Terminal 2: Run the script
python m2_adk_multiagents/a2a_demos/a2a_12_parts_and_artifacts.py
```

### What happened (actual run, gpt-4o — abridged)

**Request sent with 2 Parts:**
```
parts[0]: TextPart  → "Final-and-best offer at $445k for 742 Evergreen Terrace."
parts[1]: DataPart  → {"hint": "machine-readable copy of the offer", "offer": {..., "price": 445000}}
```

**The Task, in three places:**
```
=== 1. history (7 messages) ===
  (0) role=user, 2 part(s):  [0] TextPart ..., [1] DataPart {"hint": ..., "offer": {...}}
  (1) role=user, 2 part(s):  (the same message again — an ADK quirk)
  (2) role=agent, 3 part(s): DataParts — tool CALLS get_market_price, get_inventory_level, get_minimum_acceptable_price
  (3) role=agent, 3 part(s): DataParts — tool RESULTS (id, name, response)
  (4) role=agent, 1 part(s): DataPart  {"args": {"action": "ACCEPT", "price": 445000, "buyer_offer": 445000}, "name": "submit_decision"}
  (5) role=agent, 1 part(s): DataPart  {"name": "submit_decision", "response": {"recorded": "ACCEPT", "price": 445000}}
  (6) role=agent, 1 part(s): TextPart  SELLER: I ACCEPT your offer of $445,000 for 742 Evergreen Terrace. ...

=== 2. status.message ===
  (none — the final 'completed' update carries no message; the reply is in the artifact)

=== 3. artifacts (1) ===
  artifactId=79ee2ece-b0ce-4460-9eb7-6ad5493d5bf7  name=None
    [0] TextPart  SELLER: I ACCEPT your offer of $445,000 for 742 Evergreen Terrace. ...

=== tools the seller called (from history DataParts) ===
  call   get_market_price({"address": "742 Evergreen Terrace, Austin, TX 78701"})
  call   get_inventory_level({"zip_code": "78701"})
  call   get_minimum_acceptable_price({"property_id": "742-evergreen-austin-78701"})
  result get_market_price → {"content": [{"type": "text", "text": "{\n  \"address\": ...
  ...
  call   submit_decision({"action": "ACCEPT", "price": 445000, "buyer_offer": 445000})
  result submit_decision → {"recorded": "ACCEPT", "price": 445000}
```

**The seller ACCEPTED at $445K** — exactly at the floor price. The decision went through `submit_decision`, which records any offer at or above the floor as ACCEPT.

### Concepts introduced

| Concept | Detail |
|---------|--------|
| **Multi-part Messages** | One Message can carry multiple Parts of different types. TextPart for humans, DataPart for machines |
| **DataPart** | Structured JSON content: `{"kind": "data", "data": {...}}`. Unlike TextPart (free text), DataPart is machine-parseable without LLM inference |
| **Tool calls as DataParts** | ADK puts MCP tool calls and results — and the `submit_decision` call — in the history as DataParts: structured, not text |
| **history vs status.message vs artifacts** | history = the conversation; status.message = the latest status update's message (here empty once completed; on failure it holds the reason — Demo 15); artifacts = the deliverable, each with an `artifactId` |
| **ADK → artifact** | ADK's A2A server turns the agent's final reply into one artifact when the task completes |

### Key teaching points for class

1. **"Use DataPart when you need both human and machine representations."** The offer was sent as TextPart (LLM reads it) AND DataPart (code parses it). Both travel in the same Message.
2. **"Read the answer from the artifact; read the audit trail from history."** A downstream system doesn't replay the conversation to find the result.
3. **"Tool calls show up as DataParts in history."** You can programmatically inspect what tools were called — and what `submit_decision` recorded — without parsing text.
4. **"$445K = exact floor = guaranteed acceptance."** `submit_decision` records any offer at or above the floor as ACCEPT — the instruction asks for it, the code guarantees it.

---

## Negotiation Agents — Full System

### buyer_agent

**File:** `negotiation_agents/buyer_agent/agent.py` (~90 lines)

**How to run:**

```bash
adk web m2_adk_multiagents/negotiation_agents/
```

Open http://localhost:8000, select `buyer_agent` from the dropdown.

**What it is:** A standalone `LlmAgent` with `MCPToolset(pricing_server)` and a `before_tool_callback` allowlist. Represents the buyer's perspective — can see market prices and discount analysis but NOT the seller's floor price.

**Key code elements:**

```python
_BUYER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
}

def _enforce_buyer_allowlist(tool, args, tool_context):
    if tool.name not in _BUYER_ALLOWED_TOOLS:
        return {"error": f"tool '{tool.name}' is not authorized for the buyer"}
    return None

root_agent = LlmAgent(
    name="buyer_agent",
    model="openai/gpt-4o",
    instruction="... budget $460K max, target $445K–$455K ...",
    tools=[MCPToolset(pricing_server)],
    before_tool_callback=_enforce_buyer_allowlist,
)
```

**Concepts used:** LlmAgent (d01), MCPToolset (d02), before_tool_callback (d08)

**session.db after running (2 queries):**

| Table | Contents |
|-------|----------|
| **sessions** | 2 rows (1 used session, 1 empty) |
| **events** | 8 events across 2 queries |
| **app_states** | Empty |
| **user_states** | Empty |

**Full event flow (8 events):**

```
Query 1: "What's 742 Evergreen Terrace worth?"

  Event 1 | user:        "What's 742 Evergreen Terrace worth?"
  Event 2 | buyer_agent: tool_call: get_market_price({"address": "742 Evergreen Terrace, Austin, TX 78701"})
  Event 3 | buyer_agent: tool_result: {address, property_details, estimated_value: 462000, ...}
  Event 4 | buyer_agent: "The estimated market value is $462,000..."

Query 2: "I want to make an offer. What do you recommend?"

  Event 5 | user:        "I want to make an offer. What do you recommend?"
  Event 6 | buyer_agent: tool_call: calculate_discount(base=485000, balanced, 18 DOM, good)
  Event 7 | buyer_agent: tool_result: {suggested_offer_prices, negotiation_tips, ...}
  Event 8 | buyer_agent: "I recommend an initial offer of ~$425,000 (12% below asking)"
```

**Key observations:**

1. **LLM inferred extra parameters**: User just said "make an offer" — the LLM supplied `base_price: 485000`, `market_condition: "balanced"`, `days_on_market: 18`, `property_condition: "good"` from context (listing price from instruction + reasonable defaults from the tool schema).

2. **Matched the instruction's strategy**: The instruction says "Round 1: offer ~12% below asking (~$425,000)" and the LLM did exactly that.

3. **Only pricing tools available**: The allowlist blocks anything not in `_BUYER_ALLOWED_TOOLS`. If the LLM tried to call `get_minimum_acceptable_price`, it would get `{"error": "not authorized"}`.

### seller_agent

**File:** `negotiation_agents/seller_agent/agent.py` (~200 lines)

**How to run:**

```bash
adk web m2_adk_multiagents/negotiation_agents/
```

Open http://localhost:8000, select `seller_agent` from the dropdown.

**What it is:** A standalone `LlmAgent` with TWO `MCPToolset`s (pricing + inventory), a `before_tool_callback` allowlist, and a `submit_decision` tool that enforces the seller's floor in code. Has access to `get_minimum_acceptable_price` — the seller's secret floor. This is also the agent the A2A demos (10–15) talk to.

**Key code elements:**

```python
_SELLER_ALLOWED_TOOLS = {
    "get_market_price",
    "calculate_discount",
    "get_inventory_level",
    "get_minimum_acceptable_price",  # seller-only secret
    "submit_decision",               # structured decision, floor enforced in code
}

def submit_decision(action: str, price: int, buyer_offer: int, tool_context: ToolContext) -> dict:
    """Records ACCEPT/COUNTER; an offer at or above the floor is always recorded as ACCEPT."""
    decision = _apply_floor_policy(action, price, buyer_offer, tool_context.state.get("seller_floor_price"))
    ...

root_agent = LlmAgent(
    name="seller_agent",
    model="openai/gpt-4o",
    instruction="... call submit_decision every round; your reply MUST follow what it recorded ...",
    tools=[
        MCPToolset(pricing_server),
        MCPToolset(inventory_server),    # ← second MCP server
        submit_decision,
    ],
    before_tool_callback=_enforce_seller_allowlist,
    after_tool_callback=_remember_seller_floor,   # saves the floor into session state
)
```

Unlike the orchestrator's version, this `submit_decision` takes `buyer_offer` as an argument — a standalone seller has no `submit_offer` from a buyer in its session.

**Concepts used:** LlmAgent (d01), MCPToolset ×2 (d02), before_tool_callback (d08), information asymmetry

**Buyer vs Seller — the tool gap:**

| Tool | Buyer | Seller |
|------|-------|--------|
| `get_market_price` | Yes | Yes |
| `calculate_discount` | Yes | Yes |
| `get_inventory_level` | No | Yes |
| `get_minimum_acceptable_price` | **No** | **Yes** |
| `submit_decision` (floor enforced in code) | No | Yes |

**session.db after running (2 queries):**

| Table | Contents |
|-------|----------|
| **sessions** | 1 row — state has `seller_floor_price: 445000` and `seller_decision: {"action": "ACCEPT", "price": 446000}` |
| **events** | 10 events across 2 queries |
| **app_states** | Empty |
| **user_states** | Empty |

**Full event flow (actual run, gpt-4o):**

```
Query 1: "Buyer offers $440,000 with 30-day close"

  Event 1 | user:         "Buyer offers $440,000 with 30-day close"
  Event 2 | seller_agent: tool_call: get_market_price(...)
                          tool_call: get_inventory_level(...)
                          tool_call: get_minimum_acceptable_price(...)   ← ALL 3 IN PARALLEL
  Event 3 | seller_agent: tool_results (market, inventory, floor=$445K → saved to state)
  Event 4 | seller_agent: tool_call: submit_decision(COUNTER, 477000, buyer_offer=440000)
  Event 5 | seller_agent: tool_result: {recorded: COUNTER, price: 477000}
  Event 6 | seller_agent: "SELLER: We must COUNTER at $477,000..."

Query 2: "Buyer increases to $446,000"

  Event 7  | user:         "Buyer increases to $446,000"
  Event 8  | seller_agent: tool_call: submit_decision(COUNTER, 470000, buyer_offer=446000)   ← model tried to counter
  Event 9  | seller_agent: tool_result: {recorded: ACCEPT, price: 446000, note: "...Your reply MUST accept it..."}
  Event 10 | seller_agent: "SELLER: We ACCEPT the offer of $446,000..."
```

**Key observations:**

1. **3 tools in ONE turn (parallel)**: The LLM called `get_market_price`, `get_inventory_level`, and `get_minimum_acceptable_price` simultaneously. These are truly independent — no data dependencies, so parallel is correct here. (If one tool needed another's output, parallel calls would force the LLM to guess arguments — use a SequentialAgent (d04) to enforce ordering.)

2. **No MCP calls on query 2**: The seller remembered the market data and floor from query 1. Only `submit_decision` ran — and it didn't need the floor tool again, because `_remember_seller_floor` had saved it to session state.

3. **The model tried to counter $446K — code accepted it.** The instruction says to accept anything at or above the minimum, but the model sent `COUNTER $470,000`. `submit_decision` recorded `ACCEPT $446,000` and its note made the reply accept. This is why the floor rule lives in code.

4. **Two MCPToolset instances**: The seller connects to two separate MCP servers — `pricing_server.py` and `inventory_server.py`. ADK merges their tools into one unified set for the LLM.

### negotiation orchestrator

**File:** `negotiation_agents/negotiation/agent.py` (~375 lines)

**How to run:**

```bash
adk web m2_adk_multiagents/negotiation_agents/
```

Open http://localhost:8000, select `negotiation` from the dropdown. Type "Start negotiation for 742 Evergreen Terrace" to kick off a full buyer ↔ seller loop.

**What it is:** A `LoopAgent` wrapping a `SequentialAgent(buyer, seller)` where both agents have real MCP tools. The seller calls a `submit_decision` tool to write a structured signal to state — the `after_agent_callback` reads that dict, not free text.

**Key code elements:**

```python
def submit_decision(action: str, price: int, tool_context: ToolContext) -> dict:
    """Structured decision signal — writes to state, not prose.
    Also enforces the seller's floor in code (see below)."""
    action_upper = action.strip().upper()
    if action_upper not in ("ACCEPT", "COUNTER"):
        return {"error": f"action must be ACCEPT or COUNTER, got: {action}"}
    decision = _apply_floor_policy(action_upper, price,
        buyer_offer=tool_context.state.get("buyer_offer_price"),   # from submit_offer
        floor=tool_context.state.get("seller_floor_price"))       # from _remember_seller_floor
    if "error" in decision:
        return decision
    tool_context.state["seller_decision"] = {"action": decision["action"], "price": decision["price"]}
    return {"recorded": decision["action"], "price": decision["price"], "note": decision["note"]}

def _remember_seller_floor(tool, args, tool_context, tool_response):
    """after_tool_callback: store the floor from get_minimum_acceptable_price in state."""
    if tool.name == "get_minimum_acceptable_price":
        tool_context.state["seller_floor_price"] = _floor_from_tool_response(tool_response)

def _check_agreement(callback_context):
    """Reads structured state — NOT free text."""
    decision = callback_context.state.get("seller_decision")
    if isinstance(decision, dict) and decision.get("action") == "ACCEPT":
        # State write required — a bare escalate is dropped (see Demo 06).
        callback_context.state["loop_exit_reason"] = f"ACCEPT at ${decision['price']:,}"
        callback_context.actions.escalate = True
    return None

buyer = LlmAgent(output_key="buyer_offer",
    tools=[MCPToolset(pricing_server)],
    before_tool_callback=_enforce_buyer_allowlist,
    before_agent_callback=_init_round_state, ...)
seller = LlmAgent(output_key="seller_response",
    tools=[MCPToolset(pricing), MCPToolset(inventory), submit_decision],
    before_tool_callback=_enforce_seller_allowlist,
    after_tool_callback=_remember_seller_floor,
    after_agent_callback=_check_agreement, ...)

negotiation_round = SequentialAgent(sub_agents=[buyer, seller])
root_agent = LoopAgent(sub_agents=[negotiation_round], max_iterations=5)
```

**Concepts used:** LoopAgent (d06), SequentialAgent (d04), MCPToolset (d02), output_key + {placeholder} (d04), after_agent_callback escalation (d06), before_tool_callback allowlists (d08), submit_decision tool (structured signal)

**Why `submit_decision` instead of text parsing?**

The seller's MCP tool `get_minimum_acceptable_price` returns data containing the word "acceptable." If the callback did `"ACCEPT" in response.upper()`, it would match "ACCEPTABLE" and false-trigger on every counter-offer that mentions the floor price. This is exactly the fragile parsing problem that an FSM with structured tool output avoids.

**Why enforce the floor in code, not just in the prompt?**

The seller's instruction says "if the offer is at or above your minimum, you MUST ACCEPT". In a live gpt-4o run the seller still countered a $448,480 offer (floor $445,000) at $463,000 — the model held out for more. A rule that *must* hold belongs in code, exactly like the buyer's $460K cap in `submit_offer`:

| Situation | `submit_decision` records |
|---|---|
| Offer ≥ floor, seller sent COUNTER (or ACCEPT at another price) | **ACCEPT at the buyer's price**, with a `note` telling the seller its reply must accept |
| Offer < floor, seller sent ACCEPT | Error — "you cannot ACCEPT it, COUNTER instead" |
| Seller counters below its floor | Error — "use a price at or above your minimum" |
| Floor not looked up yet | Error — "call get_minimum_acceptable_price first" |

The floor comes from the seller's own MCP call: `_remember_seller_floor` (an `after_tool_callback`) copies it into `state["seller_floor_price"]`. No buyer prompt templates that key, so the buyer never sees it. The same pattern is used by the standalone `seller_agent` (A2A demos) and by every exercise solution with a seller.

> **Known limitation:** the policy runs *inside* `submit_decision`, so it only applies when the seller actually calls the tool. The instructions make the call mandatory every turn and gpt-4o follows that in practice, but nothing forces it — if the model answers in prose without calling `submit_decision`, that turn's decision is unchecked (and in the orchestrators, an acceptance written only in prose won't end the loop). Closing this fully would mean forcing a tool call until the decision is recorded (OpenAI's `tool_choice="required"` / ADK's `tool_config` mode `ANY`, applied per request from a `before_model_callback`). ADK 1.x's LiteLLM bridge ignores `tool_config`, so with OpenAI models that needs a small `LiteLlm` subclass — a good stretch exercise.

The `submit_decision` tool writes a structured dict: `{"action": "ACCEPT", "price": 445000}`. The callback reads `state["seller_decision"]["action"]` — a dict field, not prose. No substring matching, no regex, no false positives.

**The `{seller_response}` pitfall and fix:**

On round 1, the buyer's instruction contains `{seller_response}` but the seller hasn't responded yet — the key doesn't exist in session state. ADK throws: `Context variable not found: 'seller_response'`.

Fix: `before_agent_callback=_init_round_state` on the buyer. It checks if the key exists; if not, writes a default string.

**session.db after running (1 query, "Start negotiation"):**

| Table | Contents |
|-------|----------|
| **sessions** | 1 row — state has `offer_history`, `buyer_offer_price`, `seller_floor_price`, `seller_decision`, `loop_exit_reason`, plus `buyer_offer` / `seller_response` (output_key text) |
| **events** | One user message, then per round: buyer MCP calls + `submit_offer` + offer text, seller MCP calls + `submit_decision` + reply text, and the escalation event at the end |
| **app_states** | Empty |
| **user_states** | Empty |

**Event flow (actual run, gpt-4o — 3 rounds):**

```
  user:   "Start the negotiation."

Round 1:
  buyer:  get_market_price + calculate_discount  →  submit_offer(425000) → {recorded: 425000}
  buyer:  "BUYER: ... $425,000 ..."
  seller: get_market_price + get_inventory_level + get_minimum_acceptable_price
          (_remember_seller_floor saves seller_floor_price = 445000)
  seller: submit_decision(COUNTER, 477000) → {recorded: COUNTER, price: 477000}
  seller: "SELLER: ... $477,000 ..."

Round 2:
  buyer:  submit_offer(438000) → {recorded: 438000}
  seller: submit_decision(COUNTER, 470000) → {recorded: COUNTER, price: 470000}

Round 3:
  buyer:  submit_offer(447000) → {recorded: 447000}
  seller: submit_decision(ACCEPT, 447000) → {recorded: ACCEPT, price: 447000}
  seller: after_agent_callback → state["loop_exit_reason"] = "ACCEPT at $447,000", escalate
          ← LoopAgent stops here. No round 4, no extra messages.
```

**State tab after completion:**
```json
{
  "offer_history": [
    {"role": "buyer",  "action": "OFFER",   "price": 425000},
    {"role": "seller", "action": "COUNTER", "price": 477000},
    {"role": "buyer",  "action": "OFFER",   "price": 438000},
    {"role": "seller", "action": "COUNTER", "price": 470000},
    {"role": "buyer",  "action": "OFFER",   "price": 447000},
    {"role": "seller", "action": "ACCEPT",  "price": 447000}
  ],
  "buyer_offer_price": 447000,
  "seller_floor_price": 445000,
  "seller_decision": {"action": "ACCEPT", "price": 447000},
  "loop_exit_reason": "ACCEPT at $447,000",
  "buyer_offer": "BUYER: ...", "seller_response": "SELLER: ..."
}
```

**Key observations:**

1. **MCP tools grounded every decision**: The buyer used `get_market_price` ($462K estimated) and `calculate_discount` to justify $425K. The seller used `get_minimum_acceptable_price` ($445K floor) and `get_inventory_level` to justify the $477K counter.

2. **Both sides decide through tools**: `submit_offer` records the buyer's price (and rejects anything over $460K); `submit_decision` records the seller's ACCEPT/COUNTER (and enforces the floor). `offer_history` is built from those tool calls, not from parsing text.

3. **The loop ends on the ACCEPT round.** The seller is the last agent in the round, so after its `after_agent_callback` escalates there is nothing left to run — no post-acceptance chatter. (An earlier version of this demo did show an extra round of "congratulations" messages: its callback set `escalate` without writing state, so ADK never emitted the escalation event and the loop kept going. See the gotcha in Demo 06.)

4. **The floor is checked in code every round.** Here the model accepted $447K on its own, but `submit_decision` would have turned a COUNTER into ACCEPT anyway — as it did in the seller_agent run above and in Demo 11 round 3.

### A2A Orchestrated Negotiation (Demo 13)

**File:** `m2_adk_multiagents/a2a_demos/a2a_13_orchestrated_negotiation.py`

**What it teaches:** How to orchestrate a full buyer ↔ seller negotiation using Agent Card discovery — and how an orchestrator **reads each card's capabilities and talks to each agent the way it supports**: the buyer (`streaming: false`) by non-blocking `message/send` + `tasks/get` polling, the seller (`streaming: true`) by `message/stream`.

**How to run:**
```bash
# Terminal 1:
adk web --a2a m2_adk_multiagents/negotiation_agents/

# Terminal 2:
python m2_adk_multiagents/a2a_demos/a2a_13_orchestrated_negotiation.py
```

**What the script does:**
1. Discovers both agents via `GET /.well-known/agent-card.json` and prints their capabilities
2. Builds one `Client` per agent from its card: `ClientConfig(streaming=False, polling=True)` for the buyer, `ClientConfig(streaming=True)` for the seller
3. Sends "make an offer" to buyer_agent → task comes back `submitted` → polls `tasks/get` until `completed` → reads the offer from the artifact
4. Forwards the buyer's offer to seller_agent → streams events (the seller's tool calls appear live) → reads COUNTER or ACCEPT from the artifact
5. If COUNTER: sends the counter back to the buyer for next round
6. Repeats until ACCEPT, WALK AWAY, a task that doesn't complete, or max rounds

**Actual output (gpt-4o, abridged):**
```
STEP 1: Agent Card Discovery
Buyer Agent Card:
  Name:   buyer_agent
  Capabilities: streaming=False, pushNotifications=False  → use message/send + tasks/get polling
Seller Agent Card:
  Name:   seller_agent
  Capabilities: streaming=True, pushNotifications=False  → use message/stream

ROUND 1
    [buyer ⇠ poll] task 294b01f5 submitted — polling tasks/get
    [buyer] task 294b01f5 completed after 4 polls
← Buyer says (artifact): ...
    [seller ⇢ stream] working: calling get_market_price, get_inventory_level, get_minimum_acceptable_price
    [seller ⇢ stream] working: calling submit_decision
    [seller ⇢ stream] artifact received
    [seller] task 496292e2 completed via stream
← Seller says (artifact): ...
ROUND 2
    [buyer ⇠ poll] task e9d52173 submitted — polling tasks/get
    [buyer] task e9d52173 completed after 2 polls
    [seller ⇢ stream] working: calling submit_decision
    ...
ROUND 3
    ...
← Seller says (artifact):
SELLER: ACCEPT your offer of $448,000. ...
DEAL REACHED in round 3!
Buyer's final offer was accepted by the seller. Agreed price: $448,000.

A2A Protocol Summary:
  Outcome:          deal
  Buyer  contextId: 70a23b70-...  (reached by polling)
  Seller contextId: 286a9e64-...  (reached by streaming)
  A2A tasks created: 6 (one per message)
```

**Key details:**
- **The card decides the mechanism**: the orchestrator never hard-codes "poll the buyer"; it checks `card.capabilities.streaming`.
- **Separate contextIds**: Each agent has its own conversation thread. The script bridges them.
- **One Task per message**: 3 rounds × 2 agents = 6 tasks, each with its own id and artifact.
- **Neither agent knows about the other**: They only see messages from the script.
- **Each agent calls its own MCP tools**: Buyer calls pricing, seller calls pricing + inventory, then records its decision with `submit_decision` (floor enforced in code). The seller only researches in round 1 — its context remembers.
- **The script still reads the seller's reply text** for ACCEPT/COUNTER — over A2A it only sees the reply, not the seller's session state. The seller's prompt makes the reply match what `submit_decision` recorded.
- **A task that doesn't complete stops the negotiation**: the script checks `task.status.state` before reading the reply (see Demo 15 for why).

### Key teaching points

1. **"Information asymmetry is the design."** Buyer sees pricing tools. Seller sees pricing + inventory + floor price. The allowlist callbacks enforce this at runtime — it's not just prompt-level trust.

2. **"The orchestrator composes everything."** LoopAgent (d06) + SequentialAgent (d04) + MCPToolset (d02) + output_key (d04) + callbacks (d08) + submit_decision tool. Students can identify every piece from the demos.

3. **"Use structured signals, not text parsing — and enforce rules in the tool."** `submit_decision` writes `{"action": "ACCEPT", "price": 445000}` to state. The callback reads a dict field. The seller's MCP tool returns "minimum acceptable price" — text parsing would match "ACCEPT" in "acceptable" and false-trigger. The same tool also enforces the floor, so a must-accept offer can't be countered.

4. **"Watch for `{placeholder}` initialization."** If agent B reads `{key}` from agent A's output, but A hasn't run yet (round 1), ADK throws. Fix: `before_agent_callback` to initialize the key.

5. **"Escalate from the last agent, and make the escalation visible."** The seller runs last in each round, so escalating from its `after_agent_callback` ends the loop with no extra messages. The callback must also write state (`loop_exit_reason`) — a bare `escalate` is silently dropped and the loop keeps running.

6. **"The A2A demo shows the production pattern."** Agents discovered via Agent Cards, each reached the way its card says (polling or streaming), each with separate contextIds. The script is just a matchmaker — swap it for another agent, and you have agent-to-agent negotiation over HTTP.

---

## Demo 14 — Result Delivery: Polling, Streaming, Push (`a2a_14_result_delivery.py`)

**Files:** `a2a_demos/a2a_14_result_delivery.py` (client), `a2a_demos/negotiation_a2a_server.py` (negotiation agent's A2A server)

### What it teaches
The three ways an A2A client can get a task's result — and that **the Agent Card decides which one an agent offers**. Each negotiation agent advertises one:

| Agent | Card `capabilities` | Mechanism | Fits because |
|---|---|---|---|
| `buyer_agent` | `streaming: false`, `pushNotifications: false` | **Polling** — `message/send` with `blocking: false`, then `tasks/get` until a final state | Short task; check back later |
| `seller_agent` | `streaming: true` | **Streaming** — `message/stream` (Server-Sent Events) | Multi-step work you can watch live |
| `negotiation` | `pushNotifications: true` | **Push** — `message/send` with a webhook; the server POSTs task updates | Long-running job; no connection held open |

The `ClientConfig` passed to `ClientFactory` picks the mechanism: `streaming=True` (used only if the card allows it), `polling=True` (non-blocking `message/send`), and `push_notification_configs=[...]` for a webhook. Asking an agent for something its card doesn't offer is refused — see Demo 15.

### Why the negotiation agent has its own server
`adk web --a2a` stores a client's push-notification config but never sends notifications — ADK 1.39 creates the A2A request handler without a push sender. `negotiation_a2a_server.py` builds the same server from parts and adds the sender:

```python
runner = Runner(app_name=root_agent.name, agent=root_agent, session_service=InMemorySessionService(), ...)
push_configs = InMemoryPushNotificationConfigStore()
handler = DefaultRequestHandler(
    agent_executor=A2aAgentExecutor(runner=runner),        # ADK: A2A request → Runner → A2A events
    task_store=InMemoryTaskStore(),
    push_config_store=push_configs,
    push_sender=BasePushNotificationSender(httpx.AsyncClient(timeout=30.0), push_configs),   # ← what adk web leaves out
)
app = A2AStarletteApplication(agent_card=card, http_handler=handler).build()   # card from a2a_card.json
```

Its card lives in `negotiation_agents/negotiation/a2a_card.json` — not `agent.json` — so `adk web --a2a` doesn't also publish the agent without push support. (`adk web` without `--a2a` still shows it in the dropdown.)

### How to run (three terminals)

```bash
adk web --a2a m2_adk_multiagents/negotiation_agents/              # buyer + seller on :8000
python m2_adk_multiagents/a2a_demos/negotiation_a2a_server.py     # negotiation on :8003

python m2_adk_multiagents/a2a_demos/a2a_14_result_delivery.py --mode polling
python m2_adk_multiagents/a2a_demos/a2a_14_result_delivery.py --mode streaming
python m2_adk_multiagents/a2a_demos/a2a_14_result_delivery.py --mode push
```

The buyer and seller cards say `http://localhost:8000/...`, so stop any other server on port 8000 first.

### Actual output (gpt-4o, abridged — wording, timings and the final price differ run to run)

**Polling — buyer** (`ClientConfig(streaming=False, polling=True)`)
```
Agent Card: buyer_agent @ http://localhost:8000/a2a/buyer_agent
  capabilities: streaming=False, pushNotifications=False

t+  1.0s  message/send (blocking=false) → task 45356018  state=submitted
           taskId=45356018-8188-4d20-9e95-cbc812c39a4f
           contextId=ed413092-99ef-4e20-be7e-84b2cc077091  (the conversation; a new message gets a new taskId)
t+  2.0s  tasks/get #1 → state=working
t+  4.0s  tasks/get #3 → state=completed
t+  4.0s  done after 3 polls
  result: BUYER: Our opening offer for 742 Evergreen Terrace is $425,000. ...
```

**Streaming — seller** (`ClientConfig(streaming=True)`)
```
Agent Card: seller_agent @ http://localhost:8000/a2a/seller_agent
  capabilities: streaming=True, pushNotifications=False

t+  4.1s  status      state=submitted final=False text "The buyer offers $440,000 for 742 Evergreen Terrace with a 30-day close. ..."
t+  4.1s  status      state=working   final=False -
t+  5.8s  status      state=working   final=False tool_call get_minimum_acceptable_price, tool_call get_market_price, tool_call get_inventory_level
t+  5.8s  status      state=working   final=False tool_result get_minimum_acceptable_price, tool_result get_market_price, tool_result get_inventory_level
t+  7.0s  status      state=working   final=False tool_call submit_decision
t+  7.0s  status      state=working   final=False tool_result submit_decision
t+  8.1s  status      state=working   final=False text "SELLER: We COUNTER the offer at $477,000. ..."
t+  8.1s  artifact    text "SELLER: We COUNTER the offer at $477,000. ..."
t+  8.1s  status      state=completed final=True  -

  final task: state=completed, artifacts=1
```

**Push — negotiation** (`ClientConfig(streaming=False, polling=True, push_notification_configs=[...])`; 30 webhook POSTs in this run)
```
Webhook listening on http://127.0.0.1:9010/webhook

Agent Card: negotiation @ http://localhost:8003/
  capabilities: streaming=False, pushNotifications=True

t+  8.6s  webhook #1: state=working
t+  8.6s  webhook #2: state=working
t+  8.6s  message/send (blocking=false, webhook registered) → task 669ec356 state=working
t+  8.6s  the client is free now — no open connection, no polling. Waiting for POSTs...

t+ 19.6s  webhook #3: state=working   tool_call get_market_price, tool_call calculate_discount
t+ 19.6s  webhook #4: state=working   tool_result get_market_price, tool_result calculate_discount
t+ 20.7s  webhook #5: state=working   tool_call submit_offer
t+ 20.7s  webhook #6: state=working   tool_result submit_offer
t+ 22.1s  webhook #7: state=working   text "BUYER: We offer $425,000 for 742 Evergreen Terrace ..."
t+ 27.2s  webhook #8: state=working   tool_call get_market_price, tool_call get_inventory_level, tool_call get_minimum_acceptable_price
   ...
t+ 29.6s  webhook #12: state=working   text "SELLER: We appreciate your interest in 742 Evergreen Terrace ..."
   ... rounds 2–3 ...
t+ 41.6s  webhook #28: state=working   text "SELLER: Thank you for your revised offer of $450,000. ..."
t+ 41.6s  webhook #30: state=completed

  final result: SELLER: Thank you for your revised offer of $450,000. We appreciate your acknowledgment of the recent upgrades ...
```
(Captured with buyer/seller served on a different port; URLs shown as they appear with the default `:8000`.)

### Key observations

1. **taskId vs contextId.** Polling prints both: the **task** is this one piece of work (what `tasks/get` looks up); the **context** is the conversation it belongs to. Sending another message in the same context (Demo 11) creates a new task with the same contextId.

2. **The full lifecycle is finally visible.** Demos 10–12 use blocking `message/send`, which only returns the final `completed` task. Non-blocking send + polling shows `submitted → working → completed`; streaming shows every step in between, including the seller's MCP tool calls. (Demo 13 uses polling and streaming the same way inside the negotiation.)

3. **Artifacts arrive as their own event.** In the stream, the final text comes once as a status message and once as a `TaskArtifactUpdateEvent` — the durable output of the task. The `Client` merges each update into the task it yields, so the final task has the artifact attached.

4. **Asking for what the card doesn't offer is an error.** Demo 15 sends `message/stream` and a push-config request to the buyer and shows both refusals. (The a2a-sdk server checks the push capability on `tasks/pushNotificationConfig/set`, but not on a `message/send` that carries a push config inline, as this demo's push mode does. Whether anything is ever POSTed depends on the server having a push sender — which is why `negotiation_a2a_server.py` exists.)

5. **Push is fire-and-forget.** The client registers a webhook and a shared token, then holds no connection at all. The server POSTs a full Task snapshot for each update and includes the token in an `X-A2A-Notification-Token` header, which the webhook checks before trusting the POST.

### Key teaching points for class

1. **"How long is the job?"** Seconds → just wait or poll. Want progress → stream. Minutes, or the client may go away → push.
2. **"Read the card before choosing."** The client checks `capabilities` and picks the mechanism the agent actually offers.
3. **"Runner + executor is how you put any ADK agent behind A2A."** `adk web --a2a` does this for you; `negotiation_a2a_server.py` shows the parts — and why you'd assemble them yourself (here: to add push).

---

## Demo 15 — Error Handling (`a2a_15_error_handling.py`)

**File:** `a2a_demos/a2a_15_error_handling.py` (terminal script)

### What it teaches
Things go wrong at four different layers in A2A, and each one reaches your code differently. The script triggers each one against the real agents and shows how to detect and handle it.

| Layer | How it shows up in the client | Example in the demo |
|---|---|---|
| **1. Transport** | An exception: `A2AClientHTTPError` (with `status_code`) or `A2AClientTimeoutError` | Agent not running, wrong agent path, request timed out |
| **2. Protocol** | An exception: `A2AClientJSONRPCError`, with the JSON-RPC error in `.error.code` / `.error.message` | Unknown task, can't cancel, capability not offered, malformed request |
| **3. Task** | **No exception.** The Task comes back with `status.state == "failed"` and the reason in `status.message` | A file the model can't read |
| **4. Application** | **No exception, state `completed`** — but the agent didn't do what you asked | An "offer" with no price in it |

### How to run

```bash
# Terminal 1:
adk web --a2a m2_adk_multiagents/negotiation_agents/

# Terminal 2:
python m2_adk_multiagents/a2a_demos/a2a_15_error_handling.py
```

### Actual output (gpt-4o, abridged)

```
LAYER 1 — TRANSPORT (exceptions: A2AClientHTTPError, A2AClientTimeoutError)

▶ Agent Card from a port with nothing running (retry 3x, then give up)
  attempt 1: HTTP 503 (transient) — retrying in 0.5s
  attempt 2: HTTP 503 (transient) — retrying in 1.0s
  A2AClientHTTPError  status=503  Network communication error fetching agent card from http://127.0.0.1:8099/...: All connection attempts failed

▶ Agent Card for an agent that doesn't exist (404 — fail fast)
  A2AClientHTTPError  status=404  Failed to fetch agent card from http://127.0.0.1:8000/a2a/no_such_agent/.well-known/agent-card.json: ...

▶ Blocking message/send with a 2s timeout
  A2AClientTimeoutError  Client Request timed out
  ⚠ The server never heard that we gave up — the seller may still be working on it.
    We have no taskId, so we can't check. Resending could repeat the work.

▶ Recovery: message/send with blocking=false, then poll tasks/get
  task 87132b5b submitted — returned immediately
  task 87132b5b completed: SELLER: We must COUNTER at $477,000 ...

LAYER 2 — PROTOCOL (exception: A2AClientJSONRPCError with a JSON-RPC error code)

▶ tasks/get with a taskId the server doesn't know
  A2AClientJSONRPCError  code=-32001  message='Task not found'

▶ tasks/cancel on task 87132b5b, which already completed
  A2AClientJSONRPCError  code=-32002  message='Task cannot be canceled - current state: TaskState.completed'

▶ tasks/cancel on task 96be8c5e, still submitted
  A2AClientJSONRPCError  code=-32603  message='Cancellation is not supported'

▶ tasks/pushNotificationConfig/set on buyer_agent (pushNotifications: false)
  A2AClientJSONRPCError  code=-32603  message='Push notifications are not supported by the agent'

▶ raw message/stream to buyer_agent (streaming: false)
  HTTP 200  {"error":{"code":-32603,"message":"Streaming is not supported by the agent"},"id":"1","jsonrpc":"2.0"}

▶ raw request with an unknown method
  HTTP 200  {"error":{"code":-32601,"message":"Method not found"},"id":"2","jsonrpc":"2.0"}

▶ raw message/send missing messageId and parts
  HTTP 200  {"error":{"code":-32602,"data":[{"type":"missing","loc":["params","message","messageId"],"msg":"Field required",...

LAYER 3 — TASK FAILED (no exception: check task.status.state)

▶ message/send with a TextPart + a FilePart (application/zip)
  no exception. task 71e66f85 state=failed
  reason (status.message): LiteLlm(BaseLlm) does not support content part with MIME type application/zip.
  → don't retry as-is: the same input will fail the same way.

LAYER 4 — APPLICATION (no exception, state=completed — check the content)

▶ message/send with no price in it
  no exception. task faee45dc state=completed
  seller: SELLER: Could you clarify your offer or any questions you may have? ...
  submit_decision was NOT called → completed, but no decision. Treat as 'ask again'.
```

### Key observations

1. **"Agent not running" arrives as HTTP 503.** Nothing answered on that port, yet the card resolver reports `A2AClientHTTPError(status_code=503)`. The demo's `get_card_with_retry` retries 5xx with backoff (0.5 s, 1 s) and fails fast on 4xx, because retrying a 404 can't help.

2. **A timeout doesn't cancel anything.** The blocking `message/send` timed out on the client after 2 s, but the server kept going. With no taskId the client can't check or cancel, and resending may do the work twice. The recovery — `blocking=false`, then poll `tasks/get` — gets the taskId back immediately, and each poll is a short request.

3. **JSON-RPC errors come back with HTTP 200.** The HTTP request succeeded; the *RPC* failed. The SDK turns the error object into `A2AClientJSONRPCError`; the raw POSTs show what's actually on the wire. Standard JSON-RPC codes (-32601 method not found, -32602 invalid params, with field-level details) sit alongside A2A's own (-32001 task not found, -32002 task not cancelable).

4. **What the card doesn't offer is refused — with a generic code.** The spec defines -32003 (push notifications not supported) and -32004 (unsupported operation); a2a-sdk 0.3.26's server returned -32603 with a descriptive message. Check the message, not just the code. ADK's executor also doesn't implement cancel, so cancelling a running task fails the same way.

5. **The typed client prevents some errors.** The `Client` won't send `message/stream` to an agent whose card says `streaming: false` (it falls back to `message/send`), and won't build a request without `messageId` or `parts`. That's why those cases use raw JSON-RPC — that's what a buggy or non-SDK client might send.

6. **A FilePart is valid A2A, but the agent's model couldn't read it.** The task was created and then `failed`; the reason is in `status.message`. There is no exception — code that only catches exceptions treats this as success.

7. **`completed` ≠ success.** The seller asked for clarification and never called `submit_decision`. ADK records tool calls in history as DataParts, so the demo checks for a recorded decision instead of trusting the state. (Responses vary: in an earlier version of Demo 10, the same kind of vague message got the seller to dump its whole analysis, including the $445K floor.)

> **Security observation:** A vague or confusing message can make an agent over-share. The seller's `before_tool_callback` allowlist does **not** help here — the seller is *allowed* to call `get_minimum_acceptable_price`; the allowlist only keeps that tool away from the buyer. Defenses are the confidentiality rules in the seller's instruction and input screening such as Exercise 05's `before_model_callback` (prompt-injection defense).

### Key teaching points for class

1. **"Four layers, two of them silent."** Transport and protocol errors raise. Task failures and application failures don't — check `task.status.state`, then the content.
2. **"Retry what's transient, fix what's wrong."** Connection errors and 5xx: retry with backoff. 4xx and JSON-RPC errors: retrying sends the same mistake again.
3. **"For long work, don't block."** A timeout on a blocking call leaves you without a taskId. Non-blocking send + polling (or streaming, or push — Demo 14) keeps you in control.
4. **"Read the card first."** Most protocol errors in practice are clients asking for something the card never offered.

---

## Cross-cutting concepts

| Concept | First introduced | Revisited in |
|---------|-----------------|-------------|
| `LlmAgent` | d01 | Every demo |
| `root_agent` convention | d01 | Every adk web demo |
| Function tools | d01 | d03, d08, d09 |
| `MCPToolset` | d02 | buyer_agent, seller_agent, negotiation orchestrator |
| `ToolContext` + state | d03 | d09, negotiation (`submit_offer`, `submit_decision`) |
| `output_key` + `{placeholder}` | d04 | d05, negotiation |
| `SequentialAgent` | d04 | negotiation |
| `ParallelAgent` | d05 | — |
| `LoopAgent` + escalation (with a state write) | d06 | negotiation |
| `AgentTool` | d07 | — |
| Callbacks (before/after) | d08 | buyer_agent, seller_agent, negotiation |
| Event stream | d09 | — |
| Agent Card | a2a_10 | a2a_11, a2a_12, a2a_13, a2a_14 |
| Task (id, status, history, artifacts) | a2a_10 | a2a_11 (taskId vs contextId, `tasks/get`), a2a_12, a2a_14 |
| `contextId` threading | a2a_11 | a2a_13 |
| Parts (Text/Data/File) | a2a_10 | a2a_12, a2a_15 (FilePart) |
| Artifacts | a2a_10 | a2a_12, a2a_13, a2a_14 |
| `ClientFactory` / `Client` | a2a_10 | a2a_11–15 |
| Information asymmetry | buyer vs seller | negotiation orchestrator |
| `before_tool_callback` allowlist | d08 | buyer_agent, seller_agent, negotiation |
| Structured decision tool (+ floor enforced in code) | negotiation | seller_agent, a2a_10–13 |
| A2A orchestration | a2a_13 | — |
| Polling / streaming / push | a2a_14 | a2a_13 (polling + streaming), a2a_15 (refusals) |
| Error handling (transport / protocol / task / application) | a2a_15 | a2a_13 (stops on a task that doesn't complete) |
| `A2aAgentExecutor` + `Runner` (custom A2A server) | a2a_14 (negotiation_a2a_server.py) | — |
