# Stretch — Streaming A2A Client `[Stretch]`

> Use this if you finish Exercise 3 early or want extra practice. Builds on Exercise 3's multi-round client.

## Goal

Convert the multi-round A2A client to use **`message/stream`** instead of `message/send`. Render the task lifecycle (`submitted` → `working` → `completed`) and artifact deliveries to the console as they happen.

## Why this matters

Streaming changes the *user experience*, not the result. With `message/send`, you POST and wait — the seller takes ~5 seconds, your script blocks, you get the response. With `message/stream`, you POST and **observe** — you see "submitted" → "working" → tool calls firing → artifacts arriving → "completed".

In production, this is what powers the "seller is thinking..." progress bars in real chat UIs. It's also how you build cost-tracking and live-trace dashboards.

## What you're building

A modified script `streaming_client.py` that:

1. Uses `message/stream` instead of `message/send`. The endpoint stays the same; only the JSON-RPC method changes.
2. Reads the response as **Server-Sent Events (SSE)**. Each event has a `kind` (`status-update` or `artifact-update`) and metadata.
3. Prints each event as it arrives, with a clear timeline:
   ```
   [+0.1s] status: submitted
   [+0.3s] status: working
   [+1.8s] status: working (tool: get_market_price)
   [+4.2s] artifact: counter-offer text delivered
   [+4.3s] status: completed (final: true)
   ```
4. Validates that the seller's Agent Card declares `capabilities.streaming: true` before attempting — bail with a clear error if not.

## Steps

1. Copy your `multi_round_client.py` from Exercise 3 as a starting point.
2. Replace `send_a2a_message` with a streaming variant that:
   - Uses httpx's `client.stream("POST", url, json=...)` context manager.
   - Iterates `async for line in response.aiter_lines()`.
   - Parses SSE format (`data: {json}` lines).
   - Yields each event to the caller.
3. The caller does single-round demo (not multi-round) — keep it simple. Send one offer, render the full event stream, end.
4. Capability check: fetch the Agent Card first, verify `capabilities.streaming` is true, fail loudly if not.
5. Start the agents with A2A enabled in a separate terminal:
   ```bash
   adk web --a2a m3_adk_multiagents/negotiation_agents/
   ```
6. Run your script:
   ```bash
   python m3_adk_multiagents/solution/stretch_streaming_client/streaming_client.py
   ```
7. Watch the console — you should see timestamped events streaming in over ~5 seconds.

## Verify

- Streaming endpoint hit (`HTTP 200`, `Content-Type: text/event-stream`).
- 5–8 events received over the lifetime of one offer.
- The artifact event arrives **before** the final `completed` event.
- If you set `capabilities.streaming: false` on the agent card (artificially), the script bails with a clear message.

## Reflection

`message/send` and `message/stream` produce **the same final result**. So why does the spec offer both? What does streaming buy you that send can't? What's the cost?

Hint: think about three things — UX, observability, complexity.

---

> **Solution:** see `solution/stretch_streaming_client/` for the complete, runnable script. The instructor will walk through it live during the review session.
