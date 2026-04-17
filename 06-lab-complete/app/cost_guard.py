"""
Cost Guard — Daily LLM Budget Protection.

Tracks token usage and blocks requests when daily budget is exceeded.
Resets automatically each day.
"""
import time

from fastapi import HTTPException

from app.config import settings

# Pricing (GPT-4o-mini reference)
PRICE_PER_1K_INPUT = 0.00015   # $0.15 / 1M input tokens
PRICE_PER_1K_OUTPUT = 0.0006   # $0.60 / 1M output tokens

_daily_cost: float = 0.0
_cost_reset_day: str = time.strftime("%Y-%m-%d")


def check_and_record_cost(input_tokens: int, output_tokens: int) -> float:
    """
    Check budget before calling LLM; record cost after.
    Raises HTTP 503 if daily budget is exhausted.
    Returns estimated cost for this call.
    """
    global _daily_cost, _cost_reset_day

    today = time.strftime("%Y-%m-%d")
    if today != _cost_reset_day:
        _daily_cost = 0.0
        _cost_reset_day = today

    if _daily_cost >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=503,
            detail=f"Daily budget of ${settings.daily_budget_usd:.2f} exhausted. Try again tomorrow.",
        )

    cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT + (output_tokens / 1000) * PRICE_PER_1K_OUTPUT
    _daily_cost += cost
    return cost


def get_daily_usage() -> dict:
    """Return current day's cost summary."""
    return {
        "daily_cost_usd": round(_daily_cost, 6),
        "daily_budget_usd": settings.daily_budget_usd,
        "budget_used_pct": round(_daily_cost / settings.daily_budget_usd * 100, 1),
        "reset_day": _cost_reset_day,
    }
