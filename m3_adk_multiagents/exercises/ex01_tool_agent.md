# Exercise 1 — Build a Tool Agent `[Starter]`

## Goal
Create an `adk web`-compatible agent that uses two function tools to help a user evaluate whether to buy a property. This reinforces Demo 01 (basic agent) and Demo 02 (tools).

## Context
You've seen `d01_basic_agent` which has one tool. Now build an agent with **two** tools that work together: one estimates market value, one calculates monthly mortgage payment.

## Steps

### Step 1 — Create the agent package
Create a new folder `m3_adk_multiagents/adk_demos/ex01_tool_agent/` with `__init__.py` and `agent.py`.

Your `__init__.py`:
```python
from . import agent
```

### Step 2 — Write two tools

In `agent.py`, define:

1. `estimate_value(address: str, square_feet: int) -> dict` — Returns an estimated value based on a simple $/sqft formula. Use $320/sqft for Austin 78701.

2. `monthly_payment(price: int, down_payment_pct: int, rate: float, years: int) -> dict` — Calculates monthly mortgage payment using the standard formula:
   - Loan = price × (1 - down_payment_pct/100)
   - Monthly rate = rate / 12 / 100
   - Payment = Loan × (monthly_rate × (1 + monthly_rate)^(years×12)) / ((1 + monthly_rate)^(years×12) - 1)

### Step 3 — Define root_agent

Create an `LlmAgent` with:
- `model="openai/gpt-4o"`
- Both tools in the `tools` list
- Instructions that tell it to use `estimate_value` first, then `monthly_payment` with the result

### Step 4 — Test with adk web

```bash
adk web m3_adk_multiagents/adk_demos/ex01_tool_agent/
```

Try: "Should I buy 742 Evergreen Terrace? It's 2,100 sqft. I can put 20% down at 6.5% for 30 years."

## Verify
- Agent appears in the `adk web` dropdown
- Agent calls `estimate_value` first, then `monthly_payment`
- Response includes both the estimated value and monthly payment
- Tool call traces visible in the ADK web UI

## Reflection question
> Your tools are deterministic (no LLM inside them). What happens if you make one tool's output depend on calling another tool first? Can the LLM figure out the dependency order, or do you need a SequentialAgent?
