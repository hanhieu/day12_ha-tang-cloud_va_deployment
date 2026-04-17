"""
Production AI Agent — Kết hợp tất cả Day 12 concepts

Checklist:
  ✅ Config từ environment (12-factor)
  ✅ Structured JSON logging
  ✅ API Key authentication
  ✅ Rate limiting (sliding window)
  ✅ Cost guard (daily budget)
  ✅ Input validation (Pydantic)
  ✅ Health check + Readiness probe
  ✅ Graceful shutdown (SIGTERM)
  ✅ Security headers
  ✅ CORS
  ✅ Conversation history (Redis-backed, stateless)
  ✅ Error handling
"""
import os
import time
import signal
import logging
import json
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_and_record_cost, get_daily_usage

# Mock LLM (replace with OpenAI/Anthropic when API key is set)
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# ─────────────────────────────────────────────────────────
# Redis — Conversation History (optional, fallback to dict)
# ─────────────────────────────────────────────────────────
_USE_REDIS = False
_memory_store: dict = {}

if settings.redis_url:
    try:
        import redis as _redis_lib
        _redis = _redis_lib.from_url(settings.redis_url, decode_responses=True)
        _redis.ping()
        _USE_REDIS = True
        logger.info(json.dumps({"event": "redis_connected", "url": settings.redis_url}))
    except Exception as e:
        logger.warning(json.dumps({"event": "redis_unavailable", "error": str(e)}))


def _save_history(user_id: str, history: list, ttl: int = 3600) -> None:
    key = f"history:{user_id}"
    if _USE_REDIS:
        _redis.setex(key, ttl, json.dumps(history))
    else:
        _memory_store[key] = history


def _load_history(user_id: str) -> list:
    key = f"history:{user_id}"
    if _USE_REDIS:
        raw = _redis.get(key)
        return json.loads(raw) if raw else []
    return _memory_store.get(key, [])


# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "storage": "redis" if _USE_REDIS else "in-memory",
    }))
    time.sleep(0.1)  # simulate init
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))

    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))


# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        try:
            del response.headers["server"]
        except KeyError:
            pass
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception:
        _error_count += 1
        raise


# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Your question for the agent")
    user_id: str | None = Field(
        default=None,
        description="Optional user ID for conversation history tracking"
    )


class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    user_id: str
    timestamp: str


# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics (requires X-API-Key)",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    """
    Send a question to the AI agent.

    **Authentication:** Include header `X-API-Key: <your-key>`

    Optionally send `user_id` to maintain conversation history across requests.
    """
    # Use provided user_id or generate a session-scoped one from key
    user_id = body.user_id or f"anon-{_key[:8]}"

    # Rate limit per API key
    check_rate_limit(_key[:8])

    # Load conversation history
    history = _load_history(user_id)

    # Budget check (input tokens estimate)
    input_tokens = len(body.question.split()) * 2
    check_and_record_cost(input_tokens, 0)

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": user_id,
        "q_len": len(body.question),
        "history_turns": len(history),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    # Call LLM (mock or real depending on OPENAI_API_KEY)
    answer = llm_ask(body.question)

    # Record output token cost
    output_tokens = len(answer.split()) * 2
    check_and_record_cost(0, output_tokens)

    # Save conversation history (keep last 20 messages = 10 turns)
    history.append({"role": "user", "content": body.question,
                     "ts": datetime.now(timezone.utc).isoformat()})
    history.append({"role": "assistant", "content": answer,
                     "ts": datetime.now(timezone.utc).isoformat()})
    if len(history) > 20:
        history = history[-20:]
    _save_history(user_id, history)

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        user_id=user_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/history/{user_id}", tags=["Agent"])
def get_history(user_id: str, _key: str = Depends(verify_api_key)):
    """Get conversation history for a user (requires auth)."""
    history = _load_history(user_id)
    if not history:
        raise HTTPException(404, f"No history found for user_id: {user_id}")
    return {"user_id": user_id, "messages": history, "count": len(history)}


@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe. Platform restarts container if this fails."""
    checks = {"llm": "mock" if not settings.openai_api_key else "openai"}
    if settings.redis_url:
        try:
            if _USE_REDIS:
                _redis.ping()
            checks["redis"] = "ok" if _USE_REDIS else "unavailable"
        except Exception:
            checks["redis"] = "error"

    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe. Load balancer stops routing here if not ready."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
def metrics(_key: str = Depends(verify_api_key)):
    """Basic metrics (protected)."""
    usage = get_daily_usage()
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        **usage,
    }


# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal_received", "signum": signum}))


signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"API Key (first 4 chars): {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
