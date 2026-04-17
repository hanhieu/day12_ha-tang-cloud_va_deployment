"""
Production config — 12-Factor App (all settings from environment).
Never hard-code secrets here; use .env locally or platform env vars in production.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── LLM ──────────────────────────────────────────────────────────────────
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    openai_model_mini: str = os.getenv("OPENAI_MODEL_MINI", "gpt-4o-mini")

    # ── Vector Store ─────────────────────────────────────────────────────────
    chroma_path: str = os.getenv("CHROMA_PATH", ".chromadb")
    collection_name: str = os.getenv("COLLECTION_NAME", "xanhsm_qa")
    top_k: int = int(os.getenv("TOP_K", "3"))

    # ── Server ───────────────────────────────────────────────────────────────
    port: int = int(os.getenv("PORT", "8000"))
    host: str = os.getenv("HOST", "0.0.0.0")
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # ── Authentication ───────────────────────────────────────────────────────
    # Bot login credentials (Chainlit password auth)
    bot_username: str = os.getenv("BOT_USERNAME", "admin")
    bot_password: str = os.getenv("BOT_PASSWORD", "changeme")
    # Set to "true" to enable authentication; "false" to skip (dev mode)
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    # Max messages per user per minute (per session sliding window)
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))

    # ── Cost Guard ───────────────────────────────────────────────────────────
    daily_budget_usd: float = float(os.getenv("DAILY_BUDGET_USD", "5.0"))

    # ── Redis (optional — for cross-instance rate limiting / cost guard) ──────
    redis_url: str = os.getenv("REDIS_URL", "")

    # ── App Metadata ──────────────────────────────────────────────────────────
    app_name: str = os.getenv("APP_NAME", "XanhSM Bot")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")

    # ── Data Paths ────────────────────────────────────────────────────────────
    feedback_path: str = os.getenv("FEEDBACK_PATH", "data/feedback.jsonl")
    qa_data_path: str = os.getenv("QA_DATA_PATH", "data/qa.json")


settings = Settings()

# ── Legacy module-level names (backward compat with existing imports) ─────────
OPENAI_API_KEY = settings.openai_api_key
OPENAI_MODEL = settings.openai_model
CHROMA_PATH = settings.chroma_path
COLLECTION_NAME = settings.collection_name
TOP_K = settings.top_k
