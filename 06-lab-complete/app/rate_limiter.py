"""
Rate Limiter — Sliding Window Counter.

Limits requests per API key per minute.
In-memory implementation (Redis-based version scales better for multi-instance).
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import settings

_rate_windows: dict[str, deque] = defaultdict(deque)


def check_rate_limit(key: str) -> None:
    """
    Sliding window rate limiter.
    Raises HTTP 429 if the key has exceeded rate_limit_per_minute requests in the last 60s.
    """
    now = time.time()
    window = _rate_windows[key]

    # Remove timestamps older than 60 seconds
    while window and window[0] < now - 60:
        window.popleft()

    if len(window) >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} req/min. Retry after 60s.",
            headers={"Retry-After": "60"},
        )

    window.append(now)
