"""
Cost Guard — Daily LLM Budget Protection.

Tracks estimated OpenAI token spend globally and blocks new requests
when the daily budget is exhausted. Resets automatically each day.

GPT-4o pricing reference (2024):
  Input:  $5.00 / 1M tokens  → $0.000005 per token
  Output: $15.00 / 1M tokens → $0.000015 per token

GPT-4o-mini pricing reference:
  Input:  $0.15 / 1M tokens
  Output: $0.60 / 1M tokens
"""
import time
import threading

from config import settings

# Pricing per 1K tokens
_PRICE_4O_INPUT_PER_1K   = 0.005     # $5/1M = $0.005/1K
_PRICE_4O_OUTPUT_PER_1K  = 0.015     # $15/1M
_PRICE_MINI_INPUT_PER_1K = 0.00015   # $0.15/1M
_PRICE_MINI_OUTPUT_PER_1K = 0.0006   # $0.60/1M

_lock = threading.Lock()
_daily_cost: float = 0.0
_cost_reset_day: str = time.strftime("%Y-%m-%d")


def _reset_if_new_day() -> None:
    global _daily_cost, _cost_reset_day
    today = time.strftime("%Y-%m-%d")
    if today != _cost_reset_day:
        _daily_cost = 0.0
        _cost_reset_day = today


def check_budget() -> None:
    """
    Raises BudgetExhausted if daily spend >= settings.daily_budget_usd.
    Call this BEFORE making an OpenAI request.
    """
    with _lock:
        _reset_if_new_day()
        if _daily_cost >= settings.daily_budget_usd:
            raise BudgetExhausted(
                f"Hệ thống đã đạt giới hạn chi phí hàng ngày "
                f"(${settings.daily_budget_usd:.2f}). Vui lòng thử lại vào ngày mai."
            )


def record_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "gpt-4o",
) -> float:
    """
    Record token usage after an OpenAI call.
    Returns estimated cost in USD for this call.
    """
    global _daily_cost
    if "mini" in model:
        cost = (input_tokens / 1000) * _PRICE_MINI_INPUT_PER_1K + \
               (output_tokens / 1000) * _PRICE_MINI_OUTPUT_PER_1K
    else:
        cost = (input_tokens / 1000) * _PRICE_4O_INPUT_PER_1K + \
               (output_tokens / 1000) * _PRICE_4O_OUTPUT_PER_1K

    with _lock:
        _reset_if_new_day()
        _daily_cost += cost

    return cost


def get_daily_usage() -> dict:
    """Return current day's cost summary (for /metrics endpoint)."""
    with _lock:
        _reset_if_new_day()
        return {
            "daily_cost_usd": round(_daily_cost, 6),
            "daily_budget_usd": settings.daily_budget_usd,
            "budget_used_pct": round(_daily_cost / settings.daily_budget_usd * 100, 1)
            if settings.daily_budget_usd > 0 else 0.0,
            "reset_day": _cost_reset_day,
        }


class BudgetExhausted(Exception):
    """Raised when the daily LLM budget has been exhausted."""
    pass
