# Exercise 3 — MCP Server Failure Handling `[Core]`

## Goal

Build a version of the multi-server agent (from Exercise 2) that **gracefully handles MCP server failures** while still allowing the LLM to **self-correct on argument errors**. This teaches the critical production distinction between *server failures* and *argument errors*.

## Context

Right now, every agent in this workshop assumes its MCP servers are always running. In production, that's never true — servers crash, networks drop, containers restart.

But not all tool errors are equal. There are **three levels** of failure:

| Level | Example | Right action |
|---|---|---|
| **Argument error** | `{"error": "Invalid property_type 'house'. Must be one of: ['single_family', ...]"}` | Pass through to LLM — it reads the message, learns the format, and retries |
| **Runtime failure** | Tool returns `None` (server died mid-request) | Return fallback via `after_tool_callback` — retrying won't help |
| **Startup failure** | MCP server never starts, tools never register | Callback can't help — need infrastructure-level health checks |

If you swallow all errors with a generic fallback, you **kill the LLM's self-correction loop** on argument errors. If you ignore server failures, the agent crashes. You need to handle each level differently.

Your job: build an `after_tool_callback` that intercepts runtime failures and lets argument errors pass through. You'll also observe startup failures and understand why they need a different approach.

## What you're building

A new agent package:

```
m2_mcp/solution/ex03_server_failure_handling/
└── resilient_advisor/
    ├── __init__.py
    └── agent.py
```

Requirements:

- **`root_agent` is an `LlmAgent`** named `resilient_advisor`, model `openai/gpt-4o`.
- **Two `MCPToolset`s** — pricing and inventory servers (same as Exercise 2).
- **`after_tool_callback`** that uses **structural checks** to distinguish runtime failures from argument errors:
  - **Runtime failures** (response is `None` or empty string): log `[DEGRADED]` and return a fallback dict.
  - **Argument errors** (response is a dict with `"error"` key containing a helpful message): return `None` (pass through) so the LLM can read the message and self-correct.
  - **Healthy responses**: return `None` (pass through).
  - **Note:** ADK does NOT route tool exceptions through callbacks. Tools must catch their own exceptions and return `None` or error dicts instead of raising.
- **Agent instruction** that tells the LLM: *"If a tool returns an error or fallback, acknowledge the limitation and provide your best estimate based on general knowledge."*

## Steps

1. Start from your Exercise 2 `property_advisor` agent (or copy the solution).
2. Add an `after_tool_callback` function:
   ```python
   def handle_tool_failure(tool, args, tool_context, tool_response):
       """Intercept server failures. Let argument errors pass through."""

       # Server failures — the tool couldn't run at all
       if tool_response is None:
           print(f"[DEGRADED] {tool.name} — no response (server down?)")
           return _fallback(tool, args)

       if isinstance(tool_response, str) and tool_response.strip() == "":
           print(f"[DEGRADED] {tool.name} — empty response")
           return _fallback(tool, args)

       # Note: no Exception check needed — ADK doesn't route exceptions
       # through after_tool_callback. Tools must catch their own exceptions
       # and return None or error dicts instead of raising.

       # Argument errors — pass through so the LLM can self-correct
       # (e.g., {"error": "property_id must be '742-evergreen-austin-78701'"})
       # The error message IS the teaching signal — don't swallow it.

       return None  # Tool succeeded or returned correctable error
   ```
3. Write the `_fallback()` helper that returns a clean dict for server failures.
4. Update the agent instruction to handle degraded responses.
5. Test all four scenarios (see below).

## Testing — Four Scenarios

### Scenario 1: Happy path (both servers up)

```bash
adk web m2_mcp/solution/ex03_server_failure_handling/
```

Ask: *"What's 742 Evergreen Terrace worth?"*
- Expected: normal response with live pricing data, no `[DEGRADED]` in terminal.

### Scenario 2: Argument error → LLM self-corrects

Ask: *"What's the annual property tax on a single family house worth $462,000 in 78701?"*
- The LLM calls `get_property_tax_estimate` — it will likely pass `property_type="single family"` or `"Single Family Home"` or `"house"` (natural language, not the exact enum).
- The tool returns `{"error": "Invalid property_type 'single family'. Must be one of: ['condo', 'multi_family', 'single_family', 'townhouse']. Use underscores, all lowercase."}`.
- Expected: the callback **does NOT intercept** this — it passes through to the LLM.
- The LLM reads the error, learns the valid enum values, and retries with `property_type="single_family"`.
- Watch the events panel: you should see a failed tool call followed by a successful retry.

This is the **#1 real-world argument error** — enum mismatches between natural language and strict API values. The error message tells the LLM exactly how to fix it.

**Teaching point — Why docstrings matter for tool design:**

Notice that the tool's docstring says `property_type: The type of property (e.g., house, apartment, condo)` — deliberately vague examples that don't match the actual enum values. If the docstring listed the exact enums (`single_family`, `condo`, `townhouse`, `multi_family`), the LLM would get it right on the first call and you'd never see the self-correction loop.

This reveals a tension in tool design:
- **Good docstrings prevent errors** — list exact enum values, and the LLM calls correctly every time.
- **Bad docstrings cause errors** — but the error message is the safety net that enables self-correction.
- **In production, write clear docstrings** — preventing errors is cheaper than correcting them. But your error messages must STILL be helpful, because even good docstrings can't prevent every mistake.

### Scenario 3: Runtime server crash → callback catches it

This simulates a tool that connects successfully but crashes mid-execution — the most common production failure.

1. Stop `adk web` (Ctrl+C).
2. Set the environment variable to enable crash mode:
   ```powershell
   $env:CRASH_ZONING = "true"
   ```
3. Restart:
   ```bash
   adk web m2_mcp/solution/ex03_server_failure_handling/
   ```
4. Pick `resilient_advisor`, start a **new session**, and ask: *"What's the zoning for 742 Evergreen Terrace?"*
   - The `get_zoning_info` tool returns `None` (simulating a server that died mid-request).
   - Expected in **terminal**: `[DEGRADED] get_zoning_info — no response (server down?)`
   - Expected in **UI**: Agent acknowledges it can't access zoning data and provides a general answer.
   - Agent **never crashes**.
5. Unset the variable when done:
   ```powershell
   Remove-Item Env:CRASH_ZONING
   ```

### Scenario 4: Startup failure → tools silently disappear

This simulates a server that never starts (wrong path, Docker container down, etc.).

1. Stop `adk web` (Ctrl+C).
2. Open `resilient_advisor/agent.py`. Find the line:
   ```python
   _PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "pricing_server.py")
   ```
   Change it to:
   ```python
   _PRICING_SERVER = str(_REPO_ROOT / "m2_mcp" / "nonexistent_server.py")
   ```
3. Restart:
   ```bash
   adk web m2_mcp/solution/ex03_server_failure_handling/
   ```
4. Pick `resilient_advisor`, start a **new session**, and ask: *"What's 742 Evergreen Terrace worth?"*
   - Expected: **No `[DEGRADED]` message.** The pricing tools simply don't exist in the catalog.
   - The agent uses whatever tools ARE available (inventory, tax, zoning) and answers based on those.
   - Check the **Info tab** — pricing tools are missing entirely.
5. **Revert the path change** back to `"pricing_server.py"` when done.

**Key insight:** Scenarios 3 and 4 are fundamentally different failures:

| | Scenario 3 (runtime failure) | Scenario 4 (startup failure) |
|---|---|---|
| **When** | Tool exists, returns `None` mid-call | Server never starts, tools never register |
| **What the callback sees** | `None` response → returns fallback | Nothing — callback never fires |
| **What the agent sees** | Fallback dict with degradation message | Reduced tool catalog (tools missing) |
| **Production fix** | `after_tool_callback` (what you built) | Health checks at startup, monitoring for missing tools |

### Three levels of server failure in production

Your `after_tool_callback` handles **one** level. In production, you need all three:

| Level | What happens | Who handles it |
|---|---|---|
| **Tool returns error** | Tool runs, returns `None` or error dict | `after_tool_callback` (what you built) |
| **Tool throws exception** | Tool code raises, ADK propagates the crash | Tool code must catch its own exceptions — wrap in `try/except` and return an error dict, never `raise` |
| **Server never starts** | MCP subprocess fails at boot, tools never register | Infrastructure: health checks at startup, monitoring for expected vs. actual tool count |

**Important: ADK does not route exceptions through `after_tool_callback`.** If your tool raises an unhandled exception, ADK crashes the turn — your callback never sees it. That's why scenario 3 uses `return None` (a structural signal) instead of `raise ConnectionError`. In production, **always wrap your tool code in try/except and return error dicts instead of raising.**

## Verify

- **Scenario 1 — Both servers up**: agent calls tools normally, no `[DEGRADED]` messages
- **Scenario 2 — Wrong arguments**: tool returns `{"error": "..."}`, callback passes it through, LLM retries with corrected arguments and succeeds
- **Scenario 3 — Runtime crash**: `[DEGRADED]` in terminal, agent provides caveated answer, never crashes
- **Scenario 4 — Startup failure**: tools silently missing from catalog, agent uses remaining tools, no crash
- Agent **never crashes** in any scenario

## Reflection

You've built a callback that distinguishes two error types. This is a real production pattern:

- **Why not just retry all errors?** Server failures are persistent — retrying a crashed server wastes time and API calls. Argument errors are correctable — the retry has value because the LLM adapts. Treating them the same means you either waste retries on dead servers OR lose the self-correction loop on argument errors.
- **What if a server returns a 500 error with a message instead of crashing?** Your structural check (None/empty/Exception) wouldn't catch it — the tool would return a dict, which passes through. How would you detect HTTP-level errors vs. argument-level errors?
- **Should the fallback say "unavailable" or silently skip the tool?** In production, transparency matters. An agent that silently omits data sources looks confident but is wrong. An agent that says "I couldn't access X" lets the user decide whether to trust the response.

---

> **Solution:** see `solution/ex03_server_failure_handling/` for the complete, runnable agent. The instructor will walk through it live during the review session.
