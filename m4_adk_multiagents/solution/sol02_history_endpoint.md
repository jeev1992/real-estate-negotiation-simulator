# Solution 2: Add a Negotiation History Endpoint

## How to apply

The code is already in `m4_adk_multiagents/a2a_protocol_seller_server.py` as a **commented-out block** marked with `── Exercise 2 ──`. Search for `Exercise 2` in `main()` and uncomment the `@app.get("/history/{session_id}")` route.

## Why this works

FastAPI allows adding routes to an `app` object at any time before the server starts. Since `A2AFastAPIApplication.build()` returns a standard FastAPI app, we can extend it with additional REST endpoints.

`SESSION_REGISTRY` provides two public accessors:
- `get_agent(session_id)` — returns the `SellerAgentADK` instance or `None`
- `list_sessions()` — returns all active session IDs (useful for the error response)

Each `SellerAgentADK` stores per-round state deltas (round number, status, message type, counter price) via ADK’s `InMemorySessionService`. The `get_negotiation_history()` method retrieves these stored deltas from the session events.

## Finding the session ID

The orchestrator prints the session ID at startup (e.g. `Session: a2a_http_750929b6`). However, the seller's `SESSION_REGISTRY` may store it under a different key. To discover the actual key, hit a nonexistent session:

```powershell
Invoke-RestMethod http://127.0.0.1:9102/history/doesnotexist
# Returns: {"error": "No session found: doesnotexist", "sessions": ["a2a_http_750929b6_buyer"]}
```

Then use the session ID from the `sessions` list in your request.

## Security considerations

This endpoint exposes agent internals and should **not** be deployed to production without:
- Authentication (API key, JWT, etc.)
- Rate limiting
- Content filtering (agent messages may contain sensitive negotiation data)

In a production system, this observability data would go to a logging/monitoring service (e.g., OpenTelemetry) rather than a public REST endpoint.

## Verify
```bash
# Terminal 1:
python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102

# Terminal 2:
python m4_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 1

# Terminal 3 (after orchestrator finishes):
curl http://127.0.0.1:9102/history/<session_id>
```
