# Exercise 2 — Add a Negotiation History Endpoint `[Core]`

## Goal
Extend the A2A seller server to expose a `/history` REST endpoint that returns all past offers for a given session as JSON. This teaches you how to add **auxiliary endpoints** alongside the A2A protocol — a common pattern for observability and debugging in networked agent systems.

## What to look for
In `m4_adk_multiagents/a2a_protocol_seller_server.py`:
- The server is built on **FastAPI** via `A2AFastAPIApplication`
- `SESSION_REGISTRY` maintains one `SellerAgentADK` instance per session
- The `SellerAgentADK` agent tracks its conversation history internally
- The FastAPI `app` object is available after `app_builder.build()`

## Steps

### Step 1 — Understand the server structure
Read the `main()` function in `a2a_protocol_seller_server.py`. Notice:
- `app_builder.build()` returns a FastAPI `app` object
- You can add standard FastAPI routes to this `app` after it's created

### Step 2 — Add the `/history` endpoint
In `main()`, after `app = app_builder.build(...)`, add a new route:

```python
@app.get("/history/{session_id}")
async def get_history(session_id: str):
    """Return negotiation history for a session."""
    agents = SESSION_REGISTRY._agents
    agent = agents.get(session_id)
    if agent is None:
        return {"error": f"No session found: {session_id}", "sessions": list(agents.keys())}

    # Access the agent's internal conversation history
    history = []
    for msg in agent.llm_messages:
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            history.append({
                "role": msg["role"],
                "content": msg.get("content", "")[:300],
            })

    return {
        "session_id": session_id,
        "message_count": len(history),
        "history": history,
    }
```

### Step 3 — Test the endpoint

1. Start the seller server:
   ```bash
   python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102
   ```

2. Run one round of negotiation:
   ```bash
   python m4_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 1
   ```

3. Check the negotiation history (note the session ID from the orchestrator output):
   ```bash
   curl http://127.0.0.1:9102/history/<session_id>
   ```
   Or from Python:
   ```python
   import httpx, asyncio
   async def check():
       async with httpx.AsyncClient() as c:
           r = await c.get("http://127.0.0.1:9102/history/<session_id>")
           print(r.json())
   asyncio.run(check())
   ```

## Verify
- The `/history/<session_id>` endpoint returns JSON with the negotiation messages
- Non-existent session IDs return an error with a list of valid sessions
- The endpoint is accessible while the A2A protocol endpoints continue to work normally

## Reflection question
> This exercise adds a REST endpoint alongside the A2A JSON-RPC endpoint. What are the trade-offs of exposing agent internals this way? Think about: security (should history be public?), separation of concerns (REST vs A2A on the same server), and operational patterns (is this better suited for a logging/monitoring sidecar?).
