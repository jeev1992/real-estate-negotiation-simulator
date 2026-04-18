# Phase 2 — Foundational Concept Coverage Plan

This document is the **authored work plan** for closing the foundational gaps the
instructor/learner feedback flagged for MCP, A2A, and Google ADK. Phase 1
(removing Module 3 LangGraph and re-routing all references) is complete. Phase 2
fills the gaps topic-by-topic, file-by-file, with proposed code, diagrams, and
exercises.

**Scope (revised — Options B + C combined):**
- **Notes** — extend the four `notes/` markdown files with the missing foundational material.
- **Standalone demo scripts** — add small runnable files under each module's new `demos/` folder so every new concept can be launched live in class without disturbing the main negotiation code path.
- **Extend the existing buyer/seller code** — selectively upgrade the working M3 negotiation to actually exercise the most important new features (workflow agents, callbacks, streaming, richer Agent Card) so the headline end-to-end demo itself shows them off.

The plan is grouped by topic area:
1. **MCP** — `m2_mcp/notes/mcp_deep_dive.md` + `m2_mcp/demos/` + light edits to `m2_mcp/inventory_server.py` / `pricing_server.py`.
2. **A2A** — `m3_adk_multiagents/notes/a2a_protocols.md` + `m3_adk_multiagents/demos/` + edits to `a2a_protocol_seller_server.py` / `a2a_protocol_buyer_client_demo.py`.
3. **Google ADK** — `m3_adk_multiagents/notes/google_adk_overview.md` + `m3_adk_multiagents/notes/adk_quick_reference.md` + `m3_adk_multiagents/demos/` + edits to `buyer_adk.py` / `seller_adk.py`.

Each item below lists: **Notes change → Standalone demo → In-place code change (if any)**.

---

## 1. MCP — Foundational Coverage

Target reading time after expansion: **~25 min** (currently ~10 min).
New runnable demos: **5** under `m2_mcp/demos/`.
In-place code touched: `m2_mcp/inventory_server.py`, `m2_mcp/pricing_server.py`.

### 1.1 Protocol internals (initialize handshake, capabilities, versioning)
- **Notes** (`m2_mcp/notes/mcp_deep_dive.md` — new "§2. The initialize handshake"): 2–3 paragraphs + annotated JSON-RPC trace covering `initialize` request (`protocolVersion`, `capabilities`, `clientInfo`), `initializeResult`, and the `notifications/initialized` follow-up.
- **Standalone demo**: `m2_mcp/demos/01_initialize_handshake.py` (~50 lines) — spawn `pricing_server.py` as a subprocess and print every JSON-RPC frame of the handshake.
- **In-place change**: none.

### 1.2 The full tool calling loop (model ↔ host ↔ server)
- **Notes** (new "§3. The tool-calling loop end-to-end"): one ASCII sequence diagram + numbered 8-step walkthrough; side-by-side hand-rolled host vs. ADK `Runner`.
- **Standalone demo**: `m2_mcp/demos/02_tool_loop_trace.py` (~70 lines) — wraps an existing OpenAI call so each `tool_use` ↔ `tools/call` ↔ `tool_result` round-trip is logged with timestamps.
- **In-place change**: none.

### 1.3 Primitives — Tools, Resources, Prompts (and Sampling)
- **Notes** (new "§4. The four MCP primitives"): comparison table + worked example for each primitive.
- **Standalone demo**: `m2_mcp/demos/03_list_all_primitives.py` — connect to both servers, call `tools/list`, `resources/list`, `prompts/list`, print everything.
- **In-place changes**:
  - `m2_mcp/inventory_server.py` — add `@mcp.resource("inventory://floor-prices")` exposing the seller's floor data as a Resource (read-only). Demonstrates Resources without breaking existing Tool consumers.
  - `m2_mcp/pricing_server.py` — add a `@mcp.prompt("negotiation-tactics")` template returning a system-prompt fragment. Demonstrates Prompts.
  - Sampling stays notes-only (it requires a sampling-capable host; ADK does not currently expose this).

### 1.4 Content types (text, image, embedded resource, audio)
- **Notes** (new "§5. Content blocks"): JSON shape of each `Content` variant.
- **Standalone demo**: `m2_mcp/demos/04_content_types.py` — a tiny MCP server that returns each content block type for the same query; client prints the structured response.
- **In-place change**: none (the negotiation domain doesn't naturally need image/audio).

### 1.5 Transports — stdio, Streamable HTTP, SSE (deprecated)
- **Notes** (new "§6. Transports"): one paragraph each + transport-selection decision table; spec direction (Streamable HTTP > SSE).
- **Standalone demo**: re-use existing `m2_mcp/sse_agent_client.py` for SSE; add `m2_mcp/demos/05_streamable_http_transport.py` (~40 lines) — spin up a tiny FastMCP server in Streamable HTTP mode and call a tool from a vanilla `httpx` client.
- **In-place change**: none — keep stdio as the default for the workshop demo.

### 1.6 Security and auth
- **Notes** (new "§7. Security model"): host-mediated trust, per-tool authorization, OAuth resource-server pattern, credential injection, tool-poisoning threat list.
- **Standalone demo**: covered by the ADK callback demo in §3.5 (a `before_tool_callback` allowlist).
- **In-place change**: none for M2 servers (they're trusted local subprocesses).

### 1.7 Client/server architectural patterns
- **Notes** (new "§8. Patterns"): one-server-per-domain (current), aggregator/proxy, hosted multi-tenant, local subprocess.
- **Standalone demo / in-place change**: none — pattern catalog is reference material.

---

## 2. A2A — Foundational Coverage

Target reading time after expansion: **~30 min** (currently ~12 min).
New runnable demos: **5** under `m3_adk_multiagents/demos/`.
In-place code touched: `a2a_protocol_seller_server.py`, `a2a_protocol_buyer_client_demo.py`.

### 2.1 JSON-RPC envelope structure
- **Notes** (`m3_adk_multiagents/notes/a2a_protocols.md` — new "§3. The JSON-RPC envelope"): annotated request/success/error samples.
- **Standalone demo**: `m3_adk_multiagents/demos/01_handcraft_message_send.py` (~60 lines) — POST a hand-built JSON-RPC envelope to the running seller using `httpx` only (no `a2a-sdk`); print raw response, then send a malformed envelope to see the error code.
- **In-place change**: none.

### 2.2 Task lifecycle (states + transitions)
- **Notes** (new "§4. Task lifecycle"): state diagram + per-state guidance for `submitted`, `working`, `input-required`, `completed`, `failed`, `canceled`, `rejected`, `auth-required`.
- **Standalone demo**: `m3_adk_multiagents/demos/02_task_lifecycle.py` — issue `message/send`, then `tasks/get` to inspect the full state-history; force a `failed` task by submitting an invalid envelope.
- **In-place change**: `a2a_protocol_seller_server.py` — extend `SellerADKA2AExecutor` to emit explicit `working` updates via `TaskUpdater` while the ADK runner is mid-turn (today it goes straight to `completed`).

### 2.3 Message / Part / Artifact types
- **Notes** (new "§5. Message, Part, Artifact"): paragraph + JSON example each + "when to use which" table; explain why our seller uses a `data` part for the negotiation envelope.
- **Standalone demo**: `m3_adk_multiagents/demos/03_parts_and_artifacts.py` — send a message that combines `text` + `data` parts, and have the seller respond with both a message and an `Artifact`.
- **In-place change**: `a2a_protocol_seller_server.py` — when the negotiation reaches a terminal outcome, attach a final `Artifact` (`negotiation-summary`) to the task in addition to the existing message reply. Visible in the demo, no breaking change to the buyer client.

### 2.4 Streaming + push notifications
- **Notes** (new "§6. Streaming & long-running tasks"): `message/stream`, `tasks/resubscribe`, push notifications via webhook.
- **Standalone demo**: `m3_adk_multiagents/demos/04_streaming_negotiation.py` — buyer uses `A2AClient.send_message_streaming(...)`; print every `TaskStatusUpdateEvent` and `TaskArtifactUpdateEvent` as it arrives.
- **In-place change**: `a2a_protocol_seller_server.py` — declare `capabilities.streaming = True` in the Agent Card and have the executor surface intermediate status events. `a2a_protocol_buyer_client_demo.py` — gain a `--stream` flag that switches between sync and streaming.

### 2.5 Context IDs and threading
- **Notes** (new "§7. Context IDs"): `contextId` (groups related tasks) vs `taskId`.
- **Standalone demo**: `m3_adk_multiagents/demos/05_context_threading.py` — three sequential `message/send` calls sharing one `contextId` (one negotiation), each producing a separate `taskId`; show how the seller correlates them via session state.
- **In-place change**: `a2a_protocol_buyer_client_demo.py` and `a2a_protocol_http_orchestrator.py` — already pass a `contextId`; add a comment block explaining its role.

### 2.6 Agent Card depth
- **Notes** (expand existing card section): walk every field (`name`, `description`, `url`, `version`, `protocolVersion`, `provider`, `capabilities`, `defaultInputModes`, `defaultOutputModes`, `skills[*]`, `securitySchemes`, `security`).
- **Standalone demo**: handled by §2.1 demo (it already prints the card).
- **In-place change**: `a2a_protocol_seller_server.py` — flesh out the Agent Card with `provider`, `version`, `protocolVersion`, multiple `skills`, `defaultInputModes/OutputModes`, and the new `capabilities.streaming`. The demo card will be a complete, real-world example.

### 2.7 Security and auth
- **Notes** (new "§8. Authentication"): `securitySchemes` and `security` blocks, HTTP Bearer / API key / OAuth 2.0 client credentials, mTLS for trust-boundary deployments.
- **Standalone demo / in-place change**: notes-only. Adding real auth to the seller server complicates every other demo and isn't worth the friction in a workshop. Show the Agent Card snippet in the notes; production deployment is out of scope.

### 2.8 Error handling
- **Notes** (new "§9. Error model"): JSON-RPC standard codes (-32700/-32600/-32601/-32602/-32603), A2A-specific codes (-32001 task not found, -32002 task not cancelable, -32003 push not supported), retry strategy by code class.
- **Standalone demo**: covered by the malformed-envelope branch of §2.1 demo.
- **In-place change**: none.

### 2.9 Relationship between A2A and MCP
- **Notes** (new "§10. A2A vs MCP"): comparison table (scope, discovery, invocation model, transport, statefulness) + architecture diagram showing the buyer using MCP downward and A2A sideways.
- **Standalone demo / in-place change**: none — the existing end-to-end demo already exercises both protocols at once; the notes just make this explicit.

### 2.10 Agent interaction patterns
- **Notes** (new "§11. Interaction patterns"): catalog — request/response, streaming, push notification, multi-turn with `input-required`, delegation chain.
- **Standalone demo / in-place change**: none — covered by the §2.4 streaming demo and the existing sync demo.

---

## 3. Google ADK — Foundational Coverage

Target reading time after expansion: **~25 min** (currently ~15 min).
New runnable demos: **6** under `m3_adk_multiagents/demos/` (numbering continues the A2A series).
In-place code touched: `buyer_adk.py`, `seller_adk.py`.

### 3.1 Workflow agents — `SequentialAgent`, `ParallelAgent`, `LoopAgent`
- **Notes** (`m3_adk_multiagents/notes/google_adk_overview.md` — new "§5. Workflow agents"): one paragraph + runnable snippet per workflow type; call out `LoopAgent` as the ADK analogue of the M1 FSM termination guarantee.
- **Standalone demos**:
  - `m3_adk_multiagents/demos/06_sequential_agent.py` — research → draft → review pipeline that produces a single artifact.
  - `m3_adk_multiagents/demos/07_parallel_agent.py` — fan-out three price-check sub-agents, gather results.
  - `m3_adk_multiagents/demos/08_loop_agent.py` — body proposes a number, terminator sub-agent sets `state["done"] = True` at target.
- **In-place change**: `seller_adk.py` — wrap the seller's per-turn ADK call in a `LoopAgent` whose body re-runs the ADK turn until either (a) the buyer's offer is acceptable or (b) `max_internal_iterations` is hit. Demonstrates a real workflow agent inside the headline demo while preserving the existing public interface.

### 3.2 Multi-agent composition (sub-agents, agent transfer, AgentTool)
- **Notes** (new "§6. Multi-agent composition"): `sub_agents=[...]` (LLM-driven routing), `AgentTool` (agent-as-callable), workflow vs sub-agents decision guidance.
- **Standalone demo**: `m3_adk_multiagents/demos/09_agent_as_tool.py` — a buyer agent that exposes a "comp_lookup_agent" wrapped as `AgentTool` and decides on its own when to invoke it.
- **In-place change**: none — keeping the main negotiation agents simple keeps the headline demo readable.

### 3.3 State, memory, sessions
- **Notes** (new "§7. State, memory, sessions"): `Session` + `SessionService`; state-key scope prefixes (none / `user:` / `app:` / `temp:`); `MemoryService` vs `SessionService`; when to use which.
- **Standalone demo**: covered inline in the §3.1 LoopAgent demo (state read/write between iterations).
- **In-place change**: `buyer_adk.py` — change one ad-hoc dict field to use a scoped state key (e.g. `user:max_budget`) so the demo shows scope prefixes in action.

### 3.4 `ToolContext` deep dive
- **Notes** (`m3_adk_multiagents/notes/adk_quick_reference.md` — new "ToolContext" section): `tool_context.state`, `tool_context.actions`, `tool_context.invocation_id`, `tool_context.agent_name`, `tool_context.function_call_id`; `transfer_to_agent("...")`; `actions.escalate = True`.
- **Standalone demo**: `m3_adk_multiagents/demos/10_tool_context.py` — a tool that reads/writes `state`, sets `escalate`, and triggers `transfer_to_agent`; print the resulting event stream.
- **In-place change**: none.

### 3.5 Callbacks
- **Notes** (new "§8. Callbacks"): six hooks (`before/after` × `agent/model/tool`); use cases — PII redaction, audit logging, cost guards, tool allowlisting.
- **Standalone demo**: `m3_adk_multiagents/demos/11_callbacks.py` — minimal `LlmAgent` with all six callbacks wired to print their payloads; show the firing order.
- **In-place change**: `buyer_adk.py` and `seller_adk.py` — wire a `before_tool_callback` that enforces the per-agent MCP tool allowlist (buyer = pricing only; seller = pricing + inventory) and logs every tool call. Doubles as the live MCP-security demo from §1.6.

### 3.6 Events and streaming
- **Notes** (new "§9. Events"): event shape (`content`, `tool_calls`, `tool_responses`, `partial`, `is_final_response()`); how to stream partial output to a UI; map events back to the existing `buyer_adk.py` console output.
- **Standalone demo / in-place change**: covered by §3.5 demo + §2.4 A2A streaming.

### 3.7 Authentication in ADK tools
- **Notes** (new "§10. Tool auth"): `AuthConfig` / `AuthScheme`, OAuth flow via `tool_context.request_credential(...)`, credential persistence under the `temp:` prefix.
- **Standalone demo / in-place change**: notes-only — the workshop's MCP servers are local subprocesses with no real auth surface.

### 3.8 ADK agent discovery + ADK ↔ A2A bridge
- **Notes** (new "§11. Exposing an ADK agent over A2A"): walk `SellerADKA2AExecutor` showing how `AgentExecutor.execute(...)` calls the ADK `Runner`; how the Agent Card is generated from the `LlmAgent` description + skills; "no special A2A mode on the ADK side — the wrapper is the bridge".
- **Standalone demo / in-place change**: none — the existing seller server *is* the live demo for this section; the notes just narrate it.

---

## 4. Suggested execution order

If implemented in a single sweep, do it in this order to minimize re-reads:

1. **MCP §§2–8** in `m2_mcp/notes/mcp_deep_dive.md`
2. **MCP in-place additions**: Resource on `inventory_server.py`, Prompt on `pricing_server.py`
3. **MCP demos 01–05** under `m2_mcp/demos/`
4. **ADK §§5–11** in `google_adk_overview.md` + ToolContext addendum in `adk_quick_reference.md`
5. **ADK in-place additions**: scoped state key in `buyer_adk.py`; `LoopAgent` wrap + callback wiring in `seller_adk.py` (and matching `before_tool_callback` in `buyer_adk.py`)
6. **ADK demos 06–11** under `m3_adk_multiagents/demos/`
7. **A2A §§3–11** in `a2a_protocols.md`
8. **A2A in-place additions**: streaming + richer Agent Card + final `Artifact` in `a2a_protocol_seller_server.py`; `--stream` flag in `a2a_protocol_buyer_client_demo.py`
9. **A2A demos 01–05** under `m3_adk_multiagents/demos/`
10. Final smoke test: run the headline negotiation end-to-end (default sync) and again with `--stream` to confirm both code paths still pass.

**Estimated additional content**: ~3,500 lines of notes + 11 standalone demo scripts (~50–80 lines each) + targeted edits to 6 existing source files (no breaking changes to public interfaces).
