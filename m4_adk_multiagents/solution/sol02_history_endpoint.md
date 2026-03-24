# Solution 2: Add a Negotiation History Endpoint

## Code change

In `m4_adk_multiagents/a2a_protocol_seller_server.py`, in the `main()` function, add the `/history` route after `app = app_builder.build(...)`:

```python
async def main() -> None:
    # ... existing argparse and card setup ...

    app_builder = A2AFastAPIApplication(agent_card=card, http_handler=handler)
    app = app_builder.build(agent_card_url="/.well-known/agent-card.json", rpc_url="/")

    # NEW: Add history endpoint for debugging/observability
    @app.get("/history/{session_id}")
    async def get_history(session_id: str):
        """Return negotiation history for a session."""
        agent = SESSION_REGISTRY.get_agent(session_id)
        if agent is None:
            return {"error": f"No session found: {session_id}", "sessions": SESSION_REGISTRY.list_sessions()}

        history = await agent.get_negotiation_history()

        return {
            "session_id": session_id,
            "round_count": len(history),
            "history": history,
        }

    import uvicorn
    # ... rest of existing main() ...
```

## Why this works

FastAPI allows adding routes to an `app` object at any time before the server starts. Since `A2AFastAPIApplication.build()` returns a standard FastAPI app, we can extend it with additional REST endpoints.

`SESSION_REGISTRY` provides two public accessors:
- `get_agent(session_id)` — returns the `SellerAgentADK` instance or `None`
- `list_sessions()` — returns all active session IDs (useful for the error response)

Each `SellerAgentADK` stores per-round state deltas (round number, status, message type, counter price) via ADK’s `InMemorySessionService`. The `get_negotiation_history()` method retrieves these stored deltas from the session events.

## Important: Session ID format

The session ID in the registry includes the `seller_a2a_` prefix added by `SellerSessionRegistry.get_or_create()`. So if the orchestrator uses session `a2a_http_abc12345`, the seller registry key is `seller_a2a_a2a_http_abc12345`. Check the orchestrator output for the exact session ID.

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
