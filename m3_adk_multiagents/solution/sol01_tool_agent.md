# Solution 1 — Build a Tool Agent

## Complete `agent.py`

```python
"""Exercise 01 — Tool agent with two cooperating tools."""

from google.adk.agents import LlmAgent


def estimate_value(address: str, square_feet: int) -> dict:
    """Return an estimated market value based on $/sqft for Austin 78701."""
    price_per_sqft = 320  # Austin 78701 average
    estimated = square_feet * price_per_sqft
    return {
        "address": address,
        "square_feet": square_feet,
        "price_per_sqft": price_per_sqft,
        "estimated_value": estimated,
    }


def monthly_payment(price: int, down_payment_pct: int, rate: float, years: int) -> dict:
    """Calculate monthly mortgage payment using standard amortization formula."""
    loan = price * (1 - down_payment_pct / 100)
    monthly_rate = rate / 12 / 100
    n = years * 12
    if monthly_rate == 0:
        payment = loan / n
    else:
        payment = loan * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)
    return {
        "purchase_price": price,
        "down_payment_pct": down_payment_pct,
        "loan_amount": round(loan),
        "interest_rate": rate,
        "term_years": years,
        "monthly_payment": round(payment, 2),
    }


root_agent = LlmAgent(
    name="property_evaluator",
    model="openai/gpt-4o",
    description="Evaluates properties using market estimates and mortgage calculations.",
    instruction=(
        "You help users decide whether to buy a property.\n\n"
        "When asked about a property:\n"
        "1. Call estimate_value with the address and square footage\n"
        "2. Call monthly_payment with the estimated value and the user's financing terms\n"
        "3. Summarize: estimated value, monthly payment, and your recommendation\n\n"
        "If the user doesn't provide financing terms, assume 20% down, 6.5% rate, 30 years."
    ),
    tools=[estimate_value, monthly_payment],
)
```

## Key takeaways

- The LLM figures out the dependency order (estimate first, then mortgage calc) from the instructions — no SequentialAgent needed for two tools
- Both tools return dicts with clear field names — this helps the LLM reference specific values
- The `description` parameter on the agent matters for multi-agent discovery (other agents see it)

## Reflection answer
> The LLM can usually figure out 2-3 tool dependencies from instructions alone. For longer chains (5+ steps) or when strict ordering matters, a SequentialAgent is safer because it guarantees execution order regardless of what the LLM decides.
