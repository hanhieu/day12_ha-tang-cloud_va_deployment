# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: builder — install Python dependencies
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: production image — no build tools, minimal footprint
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

RUN chmod +x start.sh

# Default environment (can be overridden by Railway / Render / docker-compose)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    ENVIRONMENT=production \
    CHROMA_PATH=/app/.chromadb \
    FEEDBACK_PATH=/app/data/feedback.jsonl

# Create data directory for runtime ingest
RUN mkdir -p /app/data /app/.chromadb

# Create non-root user for security
RUN useradd --system --create-home --uid 1001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE $PORT

# Docker HEALTHCHECK — platform will restart container if /health stops responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" \
    || exit 1

CMD ["./start.sh"]
