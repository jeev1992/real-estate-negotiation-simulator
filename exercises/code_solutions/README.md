# Code Solutions (Runnable)

This folder contains separate runnable code solutions for coding exercises **4–12**.

## Run

From `negotiation_workshop/`:

- `python exercises/code_solutions/ex04_property_inspection_tool.py`
- `python exercises/code_solutions/ex05_anchoring_strategy.py`
- `python exercises/code_solutions/ex06_deadlock_detection_tool.py`
- `python exercises/code_solutions/ex07_sse_client_demo.py` *(requires pricing server in SSE mode)*
- `python exercises/code_solutions/ex08_mediator_agent.py` *(requires OPENAI_API_KEY)*
- `python exercises/code_solutions/ex09_negotiation_memory.py`
- `python exercises/code_solutions/ex10_negotiation_analytics.py`
- `python exercises/code_solutions/ex11_support_triage_langgraph_runner.py` *(requires OPENAI_API_KEY)*
- `python exercises/code_solutions/ex12_support_triage_adk_runner.py` *(requires OPENAI_API_KEY)*

## Prerequisite for Exercise 7 (SSE)

Before running `ex07_sse_client_demo.py`, start the pricing MCP server in SSE mode:

- `python m2_mcp/pricing_server.py --sse --port 8001`

Then, in a separate terminal, run:

- `python exercises/code_solutions/ex07_sse_client_demo.py`

Stop the SSE server with `Ctrl+C` when done.

## Notes

- Exercises 11 and 12 in this folder are standalone implementations (not wrappers).
- Exercise 7 expects pricing server SSE endpoint at `http://localhost:8001/sse`.
