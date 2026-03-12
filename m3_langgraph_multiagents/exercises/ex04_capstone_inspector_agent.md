# Capstone Exercise — Add an Inspector Agent `[Stretch]`

## Goal
Add a third agent (property inspector) to the M3 LangGraph system. The inspector uses a new MCP server to check property condition and can **veto a deal** if the inspection fails, adding a new terminal state (`inspection_failed`). This exercise ties together concepts from all four modules.

## What this covers

| Module | Concept Used |
|---|---|
| M1 | New terminal state in the negotiation lifecycle |
| M2 | New MCP server for property inspection data |
| M3 | New LangGraph node with conditional routing |
| M4 | Structured message format for inspector → orchestrator |

## Steps

### Step 1 — Create the Inspection MCP Server

Create `m2_mcp/inspection_server.py`:

```python
"""
Property Inspection MCP Server
===============================
Provides property condition assessment data.
Used by the inspector agent after buyer and seller reach tentative agreement.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("inspection-server")


@mcp.tool()
def inspect_property(address: str) -> dict:
    """Run a simulated property inspection and return findings."""
    # Simulated inspection results
    return {
        "address": address,
        "overall_condition": "good",
        "findings": [
            {"area": "roof", "condition": "fair", "note": "Shingles show wear, 3-5 years remaining life", "estimated_repair": 8500},
            {"area": "foundation", "condition": "good", "note": "Minor settling, no structural concerns", "estimated_repair": 0},
            {"area": "hvac", "condition": "good", "note": "System is 8 years old, functioning well", "estimated_repair": 0},
            {"area": "plumbing", "condition": "fair", "note": "Water heater nearing end of life", "estimated_repair": 2200},
            {"area": "electrical", "condition": "good", "note": "Panel updated in 2018", "estimated_repair": 0},
        ],
        "total_estimated_repairs": 10700,
        "pass_inspection": True,  # Would be False for serious structural/safety issues
        "inspector_recommendation": "Proceed with purchase; negotiate repair credit of $8,000-$10,000",
    }


@mcp.tool()
def get_repair_estimate(area: str, severity: str = "moderate") -> dict:
    """Get estimated repair cost for a specific area."""
    estimates = {
        ("roof", "minor"): 3000, ("roof", "moderate"): 8500, ("roof", "major"): 18000,
        ("foundation", "minor"): 2000, ("foundation", "moderate"): 8000, ("foundation", "major"): 35000,
        ("hvac", "minor"): 500, ("hvac", "moderate"): 3000, ("hvac", "major"): 8000,
        ("plumbing", "minor"): 500, ("plumbing", "moderate"): 2200, ("plumbing", "major"): 6000,
        ("electrical", "minor"): 800, ("electrical", "moderate"): 3000, ("electrical", "major"): 12000,
    }
    cost = estimates.get((area.lower(), severity.lower()), 5000)
    return {"area": area, "severity": severity, "estimated_cost": cost}


if __name__ == "__main__":
    import sys
    if "--sse" in sys.argv:
        mcp.run(transport="sse")
    else:
        mcp.run()
```

### Step 2 — Add the `inspection_failed` status

In `m3_langgraph_multiagents/negotiation_types.py`, add `"inspection_failed"` to the `NegotiationStatus` type:

```python
NegotiationStatus = Literal[
    "negotiating", "agreed", "deadlocked",
    "buyer_walked", "seller_rejected", "error",
    "inspection_failed",  # NEW
]
```

### Step 3 — Create an Inspector Agent

Create `m3_langgraph_multiagents/inspector_simple.py` with:
- An `InspectorAgent` class that calls the inspection MCP server
- A method `run_inspection(agreed_price: float) -> dict` that:
  1. Calls `inspect_property()` via MCP
  2. If total repairs > 15% of agreed price, returns `{"pass": False, "reason": "..."}`
  3. Otherwise returns `{"pass": True, "repair_credit": suggested_credit}`

### Step 4 — Add an Inspector Node to LangGraph

In `m3_langgraph_multiagents/langgraph_flow.py`:

1. Add a new `inspector_node(state) -> dict` that runs the inspection
2. Add a new router `route_after_inspection()` that checks the inspection result
3. Wire it into the graph: after the seller accepts → inspector node → END (or inspection_failed)

The graph topology becomes:

```
START → init → buyer → seller → (check)
                  ↑                  |
                  └── continue ──────┘
                                     |
                                agreed → inspector → (check)
                                                        |
                                                     passed → END (agreed)
                                                     failed → END (inspection_failed)
```

### Step 5 — Update the state schema

Add fields to `NegotiationState` TypedDict:

```python
inspection_result: Optional[dict]        # Inspector's findings
inspection_repair_credit: Optional[float] # Suggested price reduction
```

### Step 6 — Test the full pipeline

```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py --rounds 5
```

If buyer and seller agree, the inspector should run automatically. The inspection result should appear in the final output.

## Verify
- `python m2_mcp/inspection_server.py` starts without errors
- The inspector node runs after buyer-seller agreement
- If inspection passes, the deal proceeds with an optional repair credit
- If inspection fails, the negotiation ends with `inspection_failed` status
- The negotiation history includes the inspector's findings
- All existing scenarios (deadlock, buyer walk, seller reject) still work

## Reflection questions
1. How did adding a third agent change the graph complexity? Count the edges before and after.
2. Should the inspector be able to restart the negotiation at a lower price (incorporating repair costs), or should it only pass/fail? What are the trade-offs?
3. In a real-world system, would the inspector be in-process (LangGraph node) or a separate A2A agent? Why?
