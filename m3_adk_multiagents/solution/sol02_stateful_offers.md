# Solution 2 — Add State to the Negotiation Agent

## Complete `agent.py`

```python
"""Exercise 02 — Stateful offer tracking with regression warnings."""

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext


def submit_offer(price: int, tool_context: ToolContext) -> dict:
    """Submit an offer and check it against negotiation history."""
    history = tool_context.state.get("offer_history", [])
    best_so_far = max(history) if history else 0

    history.append(price)
    tool_context.state["offer_history"] = history
    tool_context.state["best_offer"] = max(history)

    result = {
        "recorded_price": price,
        "total_offers": len(history),
        "best_offer": max(history),
        "offers_remaining": 5 - len(history),
    }

    if price < best_so_far:
        result["warning"] = (
            f"This offer (${price:,}) is LOWER than your previous best "
            f"(${best_so_far:,}). The seller will likely reject a regression."
        )

    if len(history) >= 5:
        result["warning"] = result.get("warning", "") + " You have used all 5 rounds."

    return result


def get_offer_history(tool_context: ToolContext) -> dict:
    """Retrieve the full history of offers made."""
    history = tool_context.state.get("offer_history", [])
    return {
        "offers": history,
        "best_offer": max(history) if history else None,
        "total": len(history),
    }


root_agent = LlmAgent(
    name="stateful_negotiator",
    model="openai/gpt-4o",
    description="Negotiation agent that tracks offer history and warns on regressions.",
    instruction=(
        "You help users negotiate on 742 Evergreen Terrace (listed $485,000).\n\n"
        "When the user proposes an offer:\n"
        "  1. Call submit_offer with their price\n"
        "  2. If the tool returns a 'warning', tell the user and suggest reconsidering\n"
        "  3. Report: this offer, best offer so far, offers remaining (max 5)\n\n"
        "When asked about past offers, call get_offer_history.\n"
        "Advise the user strategically based on the full history."
    ),
    tools=[submit_offer, get_offer_history],
)
```

## Key takeaways

- `tool_context.state` is a dict that persists across turns within a session
- Without a prefix, state keys are session-scoped (cleared when session ends)
- `user:` prefix survives across sessions for the same user
- `app:` prefix is global to the entire application
- `temp:` prefix is cleared after each agent turn

## Reflection answer
> - **`app:`** — global counters like total negotiations across all users
> - **`user:`** — per-buyer preferences, total offers made across all properties
> - **`temp:`** — intermediate tool results needed only within a single turn
> - **No prefix** (session-scoped) — the offer history for this specific negotiation
