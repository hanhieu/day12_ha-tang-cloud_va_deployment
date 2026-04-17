"""
Rate Limiter — Sliding Window per Chainlit session.

Usage in @cl.on_message:
    from bot.middleware.rate_limiter import check_rate_limit
    check_rate_limit()   # raises cl.AskTimeoutError / sends error message if exceeded
"""
import time
from collections import deque

import chainlit as cl

from config import settings


def check_rate_limit() -> bool:
    """
    Sliding-window rate limiter using cl.user_session as per-user storage.
    Returns True if request is allowed, raises Exception if rate limit exceeded.
    """
    now = time.time()
    window: deque = cl.user_session.get("rate_window") or deque()

    # Remove timestamps older than 60 seconds
    while window and window[0] < now - 60:
        window.popleft()

    if len(window) >= settings.rate_limit_per_minute:
        raise RateLimitExceeded(
            f"Bạn đã gửi quá {settings.rate_limit_per_minute} tin nhắn/phút. "
            f"Vui lòng chờ 60 giây rồi thử lại."
        )

    window.append(now)
    cl.user_session.set("rate_window", window)
    return True


class RateLimitExceeded(Exception):
    """Raised when a user exceeds the rate limit."""
    pass
