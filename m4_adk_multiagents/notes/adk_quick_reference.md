# ADK & A2A Quick Reference — Instructor Cheat Sheet

Use this as a 5-minute verbal walkthrough before showing Module 4 code.
Each construct has: what it is, the import, and the minimal usage from our repo.

---

## 1. LlmAgent — "The agent definition"

The agent's identity: model + instructions + tools.

```python
from google.adk.agents import LlmAgent

self._agent = LlmAgent(
    name="buyer_agent",
    model="openai/gpt-4o",           # provider/model format
    instruction=buyer_instruction,    # built dynamically from discovered tool names
    tools=tools,                      # list from MCPToolset.get_tools()
)
```

> **Tell class:** "This is like writing the system prompt + function list for `openai.chat.completions.create()`, but as a reusable object."

---

## 2. Runner — "The execution engine"

Runs the LLM ↔ tool-call loop automatically. You never write this loop.

```python
from google.adk.runners import Runner

self._runner = Runner(
    agent=self._agent,
    app_name="negotiation",
    session_service=self._session_service,
)
```

Call it with `run_async()` — it yields events:

```python
async for event in self._runner.run_async(
    user_id="user1",
    session_id="session1",
    new_message=content,
):
    if event.is_final_response():
        # LLM is done — capture the text
```

> **Tell class:** "In Module 3, you wrote `_plan_mcp_tool_calls()` → execute → second LLM call. Here, Runner does all of that. One call, automatic tool loop."

---

## 3. InMemorySessionService — "Conversation memory"

Stores all turns per session_id. The agent remembers Round 1 when responding in Round 2.

```python
from google.adk.sessions import InMemorySessionService

self._session_service = InMemorySessionService()

await self._session_service.create_session(
    app_name="negotiation",
    user_id="user1",
    session_id="session1",
    state={"round": 0, "status": "negotiating"},
)
```

> **Tell class:** "In production, swap this for a database-backed service. Same interface."

---

## 4. MCPToolset — "The MCP bridge"

Spawns MCP server as subprocess, calls `list_tools()`, wraps tools for the LLM.

```python
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset, StdioConnectionParams, StdioServerParameters,
)

self._pricing_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["m2_mcp/pricing_server.py"],
        )
    )
)
tools = await self._pricing_toolset.get_tools()  # auto list_tools()
```

> **Tell class:** "This is the same `list_tools()` we called manually in Module 3. MCPToolset does it for you — and also handles `call_tool()` automatically when the LLM picks a tool."

---

## 5. Event + EventActions — "Session state updates"

How you update session state without mutating the session directly.

```python
from google.adk.events import Event
from google.adk.events.event_actions import EventActions

await self._session_service.append_event(
    session=session,
    event=Event(
        author="user1",
        actions=EventActions(stateDelta={"round": 2, "status": "negotiating"}),
    ),
)
```

> **Tell class:** "Think of it as an append-only log — same idea as LangGraph's `Annotated[list, operator.add]`, but at the session level."

---

## 6. Model ID format — "openai/gpt-4o"

ADK uses `provider/model` format, routed through litellm.

```python
OPENAI_MODEL = "openai/gpt-4o"   # not just "gpt-4o"
```

> **Tell class:** "The `openai/` prefix tells ADK which provider to route to. You could swap to `google/gemini-2.0-flash` with one string change."

---

## 7. Async context manager — "Lifecycle"

Agents are context managers: `__aenter__` spawns MCP, `__aexit__` cleans up.

```python
async with BuyerAgentADK(session_id="abc") as buyer:
    offer = await buyer.make_initial_offer_envelope()
# MCP subprocesses killed here — no orphans
```

> **Tell class:** "If the agent crashes mid-turn, `__aexit__` still runs and kills the MCP subprocess. No leaked processes."

---

# A2A Protocol Constructs

---

## 8. AgentCard — "The agent's business card"

Published at `GET /.well-known/agent-card.json`. Describes what the agent can do.

```python
from a2a.types import AgentCard, AgentCapabilities, AgentSkill, AgentProvider

card = AgentCard(
    name="seller_agent",
    description="Responds to buyer offers with counter-offers",
    url="http://127.0.0.1:9102",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=False, pushNotifications=False),
    skills=[AgentSkill(
        id="negotiation",
        name="Real Estate Negotiation",
        description="Counter-offers on property purchases",
    )],
)
```

> **Tell class:** "The buyer fetches this card to learn the seller's endpoint and capabilities. No hardcoded URLs, no imports."

---

## 9. AgentExecutor — "Server-side request handler"

Subclass this to handle incoming A2A requests.

```python
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue

class SellerADKA2AExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue,
                              task_id=context.task_id,
                              context_id=context.context_id)
        await updater.start_work()

        incoming_text = context.get_user_input()
        # ... run seller agent, get response ...

        await updater.complete(agent_message)  # or updater.failed(...)
```

> **Tell class:** "This is where the seller's logic lives on the server side. The A2A SDK calls `execute()` for every incoming request."

---

## 10. TaskUpdater — "Task lifecycle"

Emits status events: `start_work()` → `complete()` or `failed()`.

```python
from a2a.server.tasks.task_updater import TaskUpdater

updater = TaskUpdater(event_queue, task_id=context.task_id, context_id=context.context_id)
await updater.start_work()           # status: "working"
# ... do work ...
msg = updater.new_agent_message(parts=[TextPart(text=json.dumps(response))])
await updater.complete(msg)          # status: "completed"
# or: await updater.failed(msg)      # status: "failed"
```

> **Tell class:** "Three states: working → completed or failed. The client sees these status transitions over HTTP."

---

## 11. A2AFastAPIApplication — "Wire it up"

Creates the FastAPI app with two routes: agent card + JSON-RPC.

```python
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.events.in_memory_queue_manager import InMemoryQueueManager

handler = DefaultRequestHandler(
    agent_executor=SellerADKA2AExecutor(),
    task_store=InMemoryTaskStore(),
    queue_manager=InMemoryQueueManager(),
)
app = A2AFastAPIApplication(agent_card=card, http_handler=handler)
fastapi_app = app.build(agent_card_url="/.well-known/agent-card.json", rpc_url="/")
```

> **Tell class:** "Two routes. GET the agent card. POST a JSON-RPC message. That's the entire A2A server."

---

## 12. A2AClient + A2ACardResolver — "Client side"

Discover the agent, then send messages.

```python
from a2a.client import A2AClient, A2ACardResolver

resolver = A2ACardResolver(httpx_client=http_client, base_url="http://127.0.0.1:9102")
card = await resolver.get_agent_card()        # GET /.well-known/agent-card.json

client = A2AClient(httpx_client=http_client, agent_card=card)
response = await client.send_message(request)  # POST / with JSON-RPC
```

> **Tell class:** "Two steps: discover (fetch the card), then send (POST the message). The client doesn't need to know anything about the server's implementation."

---

## 13. SendMessageRequest — "The message envelope"

How you construct a message to send over A2A.

```python
from a2a.types import Message, MessageSendParams, Role, SendMessageRequest, TextPart

request = SendMessageRequest(
    id=f"req_{uuid.uuid4().hex[:8]}",
    params=MessageSendParams(
        message=Message(
            messageId=f"msg_{uuid.uuid4().hex[:8]}",
            role=Role.user,
            parts=[TextPart(text=offer_json_string)],
        )
    ),
)
```

> **Tell class:** "This is JSON-RPC wrapping. The actual offer is in `parts[0].text` as a JSON string. The rest is protocol framing."

---

## Teaching order suggestion

Walk through in this order (5 min total):

1. **LlmAgent** — "here's how you define an agent" (10 sec)
2. **MCPToolset** — "here's how it gets tools from MCP" (15 sec)
3. **Runner** — "here's what runs the tool loop automatically" (15 sec)
4. **InMemorySessionService** — "here's how it remembers across turns" (10 sec)
5. **Model ID** — "note the `openai/gpt-4o` format" (5 sec)
6. **Context manager** — "async with handles cleanup" (10 sec)
7. **AgentCard** — "the seller publishes this so the buyer can find it" (15 sec)
8. **AgentExecutor** — "the server subclass that handles requests" (10 sec)
9. **TaskUpdater** — "working → completed or failed" (10 sec)
10. **A2AClient** — "fetch card, send message — two steps" (15 sec)

Then say: "You'll see all of these in the code. Now let me show you the code."
