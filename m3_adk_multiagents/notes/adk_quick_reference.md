# ADK & A2A Quick Reference

> **Audience:** Engineers reviewing Module 3 after the workshop, or anyone who wants the smallest possible recap of ADK's core constructs.
> **Prerequisites:** None for the recap itself; ideally you've run at least the demos in `adk_demos/d01_basic_agent/` and `adk_demos/d02_mcp_tools/`.
> **Read this after:** Running any Module 3 demo.
> **Read this next:** [`google_adk_overview.md`](google_adk_overview.md) for the deeper version of every construct below.
>
> **TL;DR:**
> 1. **An agent is a declarative `LlmAgent` object.** No class, no boilerplate, no manual orchestration loop — just `root_agent = LlmAgent(...)`.
> 2. **`adk web` is the runtime.** It auto-discovers any folder with `__init__.py` + `agent.py` (defining `root_agent`), creates a Runner + SessionService for you, and gives you a chat UI. Add `--a2a` and every agent also gets a JSON-RPC endpoint and Agent Card for free.
> 3. **MCPToolset is the bridge to MCP servers.** Goes directly in the agent's `tools=[]` list. ADK manages the subprocess, the handshake, and translates LLM tool calls into MCP `tools/call` requests automatically.

---

This file is a one-page reminder of every ADK and A2A construct you'll actually
touch. Each entry has: what it is, the import, a minimal usage from this repo,
and one line of intuition.

---

## 1. LlmAgent — "The agent definition"

The agent's identity: model + instructions + tools.

```python
from google.adk.agents import LlmAgent

# negotiation_agents/buyer_agent/agent.py
root_agent = LlmAgent(
    name="buyer_agent",
    model="openai/gpt-4o",           # provider/model format
    description="Real estate buyer agent for 742 Evergreen Terrace.",
    instruction="...",
    tools=[MCPToolset(...)],          # auto-discovers MCP tools
    before_tool_callback=_enforce_buyer_allowlist,
)
```

> **Intuition:** This is like writing the system prompt + function list for `openai.chat.completions.create()`, but as a reusable, discoverable object. `adk web` finds this automatically.

---

## 2. Runner — "The execution engine"

Runs the LLM ↔ tool-call loop automatically. With `adk web`, you never interact with Runner directly — the framework creates it for you.

Under the hood:
```python
from google.adk.runners import Runner

runner = Runner(
    agent=root_agent,
    app_name="negotiation",
    session_service=session_service,
)
```

> **Intuition:** When you use `adk web`, Runner is created automatically. You only need Runner explicitly when writing standalone scripts.

---

## 3. InMemorySessionService — "Conversation memory"

Stores all turns per session_id. `adk web` creates this automatically — you only configure it for standalone scripts or production databases.

```python
from google.adk.sessions import InMemorySessionService

# adk web uses this automatically.
# For production: --session_service_uri="sqlite:///sessions.db"
```

> **Intuition:** In production, swap for a database-backed service via `--session_service_uri`. Same interface.

---

## 4. MCPToolset — "The MCP bridge"

Spawns MCP server as subprocess, calls `list_tools()`, wraps tools for the LLM.
In idiomatic ADK, MCPToolset goes directly in the agent's `tools` list:

```python
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset, StdioConnectionParams, StdioServerParameters,
)

root_agent = LlmAgent(
    name="buyer_agent",
    model="openai/gpt-4o",
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=["m2_mcp/pricing_server.py"],
                )
            )
        )
    ],
)
```

> **Intuition:** This is the same MCP `tools/list` you'd otherwise call by hand. `MCPToolset` does it for you — and also runs MCP `tools/call` automatically when the LLM picks a tool. ADK manages the subprocess lifecycle.

---

## 5. `adk web` — "Run and interact"

The primary way to run agents in this module. Discovers agent packages automatically.

```bash
# Run agents (buyer, seller, negotiation in dropdown)
adk web m3_adk_multiagents/negotiation_agents/

# Run demos (9 concept demos in dropdown)
adk web m3_adk_multiagents/adk_demos/

# Enable A2A endpoints (auto-generates Agent Cards)
adk web --a2a m3_adk_multiagents/negotiation_agents/
```

> **Intuition:** Each subfolder with `__init__.py` + `agent.py` (defining `root_agent`) becomes an agent in the dropdown. No boilerplate, no manual server setup.

---

## 6. Model ID format — "openai/gpt-4o"

ADK uses `provider/model` format, routed through litellm.

```python
OPENAI_MODEL = "openai/gpt-4o"   # not just "gpt-4o"
```

> **Intuition:** The `openai/` prefix tells ADK which provider to route to. You could swap to `google/gemini-2.0-flash` with one string change.

---

## 7. `adk web --a2a` — "A2A endpoints + Agent Cards"

With the `--a2a` flag, each agent gets a JSON-RPC endpoint and an auto-generated Agent Card.

```bash
adk web --a2a m3_adk_multiagents/negotiation_agents/

# Agent Cards at:
# http://localhost:8000/a2a/buyer_agent/.well-known/agent-card.json
# http://localhost:8000/a2a/seller_agent/.well-known/agent-card.json
```

> **Intuition:** No custom server code needed. ADK builds the A2A server, generates Agent Cards from your agent's name/description, and serves everything.

---

# A2A Protocol Constructs

---

## 8. Agent Card — "The agent's business card"

Auto-generated by `adk web --a2a`. Published at `GET /<agent_name>/.well-known/agent-card.json`. Describes what the agent can do.

Browse it directly:
```
http://localhost:8000/a2a/seller_agent/.well-known/agent-card.json
```

Or fetch programmatically:
```python
import httpx
resp = httpx.get("http://localhost:8000/a2a/seller_agent/.well-known/agent-card.json")
card = resp.json()
print(card["name"], card["description"], card["capabilities"])
```

> **Intuition:** ADK generates this from your agent's `name`, `description`, and tools. The buyer fetches it to discover the seller. No manual card creation needed.

---

## 9. A2A Client — "Client side discovery + messaging"

For demos 09–10, use `a2a-sdk` or raw `httpx` to talk to `adk web --a2a` endpoints.

```python
from a2a.client import A2AClient, A2ACardResolver

# Discover
resolver = A2ACardResolver(httpx_client=http, base_url="http://localhost:8000/a2a/seller_agent")
card = await resolver.get_agent_card()

# Send message
client = A2AClient(httpx_client=http, agent_card=card)
response = await client.send_message(request)
```

Or raw HTTP (demo 09):
```python
body = {
    "jsonrpc": "2.0",
    "id": "req_1",
    "method": "message/send",
    "params": {"message": {"messageId": "msg_1", "role": "user",
                           "parts": [{"kind": "text", "text": offer_json}]}}
}
resp = await httpx.AsyncClient().post("http://localhost:8000/a2a/seller_agent", json=body)
```

> **Intuition:** Two steps: discover (fetch the card), then send (POST the message). Demo 09 shows raw HTTP; demo 10 uses the SDK.

---

## 10. Task Lifecycle — "submitted → working → completed"

When a client sends `message/send`, the A2A server creates a Task. Demo 09 shows the states:

```
Client sends message  →  Task status: "submitted"
                      →  Agent processes  →  status: "working"
                      →  Agent done       →  status: "completed"
                         (or error        →  status: "failed")
```

> **Intuition:** `adk web --a2a` handles this lifecycle automatically. Demo 09 lets you see it from the client side.

---

## 11. Context Threading — "Multi-turn conversations"

A2A's `contextId` field is what threads multiple `message/send` calls into one
conversation. Round 1 omits it (server assigns one); rounds 2+ pass it back so
the agent remembers prior turns. **Equivalent to `session_id` in ADK** — same
idea, just at the network layer instead of in-process.

See `m3_adk_multiagents/adk_demos/a2a_11_context_threading.py` and the matching
section in [`a2a_protocols.md`](a2a_protocols.md).

---

## Recommended way to skim this file

Read entries 1, 4, 5 first — those three are 80% of what you'll touch on day
one. Entries 2, 3, 6 are background you only revisit if you're writing a
standalone script (no `adk web`). Entries 7–11 are the A2A surface — read
them when you're ready to expose your agent over the network.

---

## ToolContext (advanced)

Once your tools need to read/write session state or save artifacts,
declare a `ToolContext` parameter — ADK injects it automatically:

```python
from google.adk.tools.tool_context import ToolContext

def bump_offer_counter(tool_context: ToolContext) -> dict:
    n = tool_context.state.get("user:offer_attempts", 0) + 1
    tool_context.state["user:offer_attempts"] = n
    return {"offer_attempts": n}
```

- `tool_context.state` — dict-like, with prefixes:
  - no prefix → session-scoped
  - `user:` → user-scoped (survives across sessions for same user_id)
  - `app:` → app-scoped (shared across all users)
  - `temp:` → invocation-only, not persisted
- `tool_context.actions.escalate = True` — break out of the nearest LoopAgent
- `tool_context.actions.transfer_to_agent = "other"` — hand control off
- `await tool_context.save_artifact(name, ...)` / `load_artifact(name)` — binary blobs

> **Intuition:** ToolContext is how a tool talks back to the runtime —
> not just to the model. State is for memory; actions are for control flow.

Demo: `m3_adk_multiagents/adk_demos/d03_sessions_state/agent.py`.
