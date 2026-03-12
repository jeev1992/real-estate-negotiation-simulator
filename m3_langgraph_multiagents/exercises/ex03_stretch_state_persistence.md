# Exercise 3 — Add LangGraph State Persistence `[Stretch]`

## Goal
Add SQLite-based state persistence to the LangGraph negotiation so that a negotiation can be **paused and resumed** across process restarts. This teaches you how LangGraph's checkpointing system works and why state persistence matters for production agent workflows.

## Why this matters
In production, agent workflows can take hours or days (e.g., multi-step approvals, human-in-the-loop reviews). If the process crashes, you lose all progress. LangGraph's checkpointer saves state after every node execution, allowing exact resume from the last successful step.

## Steps

### Step 1 — Install the persistence dependency

```bash
pip install langgraph-checkpoint-sqlite
```

### Step 2 — Import the checkpointer

In `m3_langgraph_multiagents/langgraph_flow.py`, add:

```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
```

### Step 3 — Update `create_negotiation_graph()` to accept a checkpointer

Modify the function to optionally accept a checkpointer:

```python
def create_negotiation_graph(checkpointer=None) -> StateGraph:
    # ... existing node and edge setup ...
    
    graph = workflow.compile(checkpointer=checkpointer)
    return graph
```

### Step 4 — Update the runner to use SQLite persistence

In `run_negotiation()` or `main_langgraph_multiagent.py`, create the checkpointer:

```python
async def run_negotiation_with_persistence(session_id: str, **kwargs):
    async with AsyncSqliteSaver.from_conn_string("negotiation_state.db") as checkpointer:
        graph = create_negotiation_graph(checkpointer=checkpointer)
        
        config = {"configurable": {"thread_id": session_id}}
        state = initial_state(session_id=session_id, **kwargs)
        
        result = await graph.ainvoke(state, config=config)
        return result
```

### Step 5 — Test pause and resume

1. Start a negotiation with 5 rounds
2. While it's running, kill the process (Ctrl+C) after round 2
3. Restart the script with the same session ID
4. Verify it resumes from round 3, not round 1

### Step 6 — Inspect the SQLite database

```python
import sqlite3
conn = sqlite3.connect("negotiation_state.db")
cursor = conn.execute("SELECT * FROM checkpoints")
for row in cursor:
    print(row)
```

## Verify
- The negotiation completes normally with persistence enabled
- After a process restart with the same session ID, the graph resumes from the last checkpoint
- The SQLite database contains checkpoint entries for each node execution

## Reflection question
> What are the trade-offs of checkpointing after every node vs. only at certain points? Think about: write overhead, resume granularity, and database size for long negotiations.
