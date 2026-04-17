"""
XanhSM Bot — Production Chainlit Entry Point

Day 12 production features implemented:
  ✅ Config từ environment (12-factor)          — config.py Settings class
  ✅ Structured JSON logging                     — JSON formatter below
  ✅ Password authentication (Chainlit)          — @cl.password_auth_callback
  ✅ Rate limiting (sliding window)              — bot/middleware/rate_limiter.py
  ✅ Cost guard (daily budget)                   — bot/middleware/cost_guard.py
  ✅ Input validation                            — Pydantic in FastAPI routes
  ✅ Health check + Readiness probe              — /health, /ready via chainlit.server
  ✅ Graceful shutdown (SIGTERM)                 — signal handler below
  ✅ Security headers                            — middleware on chainlit.server.app
  ✅ Conversation history                        — cl.user_session (Chainlit built-in)
  ✅ Error handling                              — try/except in router + here
"""
import json
import logging
import os
import signal
import time
from datetime import datetime, timezone

import chainlit as cl
import chainlit.data as cl_data
from chainlit.server import app as _server  # Underlying FastAPI/Starlette instance
from fastapi import Response
from fastapi.middleware.cors import CORSMiddleware

from bot.data_layer import LocalFeedbackDataLayer
from bot.handlers.onboarding import ask_user_type
from bot.middleware.cost_guard import BudgetExhausted, get_daily_usage
from bot.middleware.rate_limiter import RateLimitExceeded, check_rate_limit
from bot.router import route
from config import settings
from rag.vectorstore import get_collection

# ─────────────────────────────────────────────────────────────────────────────
# Structured JSON Logging
# ─────────────────────────────────────────────────────────────────────────────
class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    handlers=[_handler],
)

# Suppress noisy third-party loggers
for _noisy in ("httpx", "watchfiles", "chainlit", "sentence_transformers", "chromadb"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Startup timing
# ─────────────────────────────────────────────────────────────────────────────
_START_TIME = time.time()
_IS_READY = False
_REQUEST_COUNT = 0

# ─────────────────────────────────────────────────────────────────────────────
# Security headers + request logging on the underlying Starlette server
# ─────────────────────────────────────────────────────────────────────────────
_server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@_server.middleware("http")
async def _http_middleware(request, call_next):
    global _REQUEST_COUNT
    _REQUEST_COUNT += 1
    start = time.time()
    response: Response = await call_next(request)
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"  # Allow iframe for Chainlit UI
    try:
        del response.headers["server"]
    except KeyError:
        pass
    ms = round((time.time() - start) * 1000, 1)
    logger.info(json.dumps({
        "event": "http_request",
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "ms": ms,
    }))
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Health & Readiness probes (for Railway / Render / K8s)
# ─────────────────────────────────────────────────────────────────────────────
@_server.get("/health", tags=["Operations"])
def health():
    """
    Liveness probe — returns 200 if the server is alive.
    The platform restarts the container if this fails.
    """
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "total_requests": _REQUEST_COUNT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@_server.get("/ready", tags=["Operations"])
def ready():
    """
    Readiness probe — returns 200 only after the app has finished initialising.
    The load balancer stops routing here while this returns 503.
    """
    from fastapi import HTTPException
    if not _IS_READY:
        raise HTTPException(status_code=503, detail="Not ready yet — still loading model")
    return {"ready": True}


@_server.get("/metrics", tags=["Operations"])
def metrics():
    """Basic cost & request metrics."""
    usage = get_daily_usage()
    return {
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "total_requests": _REQUEST_COUNT,
        **usage,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Graceful Shutdown (SIGTERM from Railway / Docker / K8s)
# ─────────────────────────────────────────────────────────────────────────────
def _handle_sigterm(signum, _frame):
    logger.info(json.dumps({
        "event": "shutdown_signal",
        "signal": "SIGTERM",
        "uptime_seconds": round(time.time() - _START_TIME, 1),
    }))
    # Chainlit / uvicorn will complete in-flight requests and exit cleanly.


signal.signal(signal.SIGTERM, _handle_sigterm)

# ─────────────────────────────────────────────────────────────────────────────
# Data Layer — 👍 / 👎 feedback stored locally
# ─────────────────────────────────────────────────────────────────────────────
@cl.data_layer
def get_data_layer():
    return LocalFeedbackDataLayer()


# ─────────────────────────────────────────────────────────────────────────────
# Authentication — password gate (enabled via AUTH_ENABLED=true env var)
# ─────────────────────────────────────────────────────────────────────────────
if settings.auth_enabled:
    @cl.password_auth_callback
    def auth_callback(username: str, password: str):
        """
        Simple single-user auth.
        Set BOT_USERNAME + BOT_PASSWORD in environment.
        Returns a cl.User on success, None on failure.
        """
        if username == settings.bot_username and password == settings.bot_password:
            logger.info(json.dumps({"event": "login_success", "user": username}))
            return cl.User(identifier=username, metadata={"role": "user"})
        logger.warning(json.dumps({"event": "login_failed", "user": username}))
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Model warm-up + data ingestion (runs at import time so first request isn't slow)
# ─────────────────────────────────────────────────────────────────────────────
logger.info(json.dumps({"event": "startup", "app": settings.app_name,
                         "version": settings.app_version,
                         "environment": settings.environment}))

# Initialize vector store and ingest data if needed
logger.info(json.dumps({"event": "vectorstore_loading"}))
collection = get_collection()

# Check if collection is empty and ingest data if needed
try:
    count = collection.count()
    if count == 0:
        logger.info(json.dumps({"event": "data_ingestion_start"}))
        from rag.ingest import ingest
        ingest()
        logger.info(json.dumps({"event": "data_ingestion_complete"}))
    else:
        logger.info(json.dumps({"event": "vectorstore_ready", "document_count": count}))
except Exception as e:
    logger.error(json.dumps({"event": "vectorstore_error", "error": str(e)}))

_IS_READY = True
logger.info(json.dumps({"event": "ready"}))


# ─────────────────────────────────────────────────────────────────────────────
# Chainlit event handlers
# ─────────────────────────────────────────────────────────────────────────────
@cl.on_chat_start
async def on_chat_start():
    logger.info(json.dumps({
        "event": "chat_start",
        "session_id": cl.context.session.id,
    }))
    await ask_user_type()


@cl.on_message
async def on_message(message: cl.Message):
    """
    Entry point for every user message.
    Enforces rate limit and budget guard before routing to the actual handler.
    """
    # ── Rate limit ────────────────────────────────────────────────────────────
    try:
        check_rate_limit()
    except RateLimitExceeded as exc:
        await cl.Message(content=f"⚠️ {exc}").send()
        return

    # ── Budget guard ──────────────────────────────────────────────────────────
    from bot.middleware.cost_guard import check_budget
    try:
        check_budget()
    except BudgetExhausted as exc:
        await cl.Message(content=f"⛔ {exc}").send()
        return

    # ── Route to appropriate handler ─────────────────────────────────────────
    await route(message)
