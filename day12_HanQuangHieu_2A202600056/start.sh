#!/bin/bash
set -e

# Railway injects PORT automatically, default to 8000 if not set
PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}

# Chainlit reads CHAINLIT_PORT env var before processing CLI args;
# force it to the resolved integer so '$PORT' literals don't break it.
export CHAINLIT_PORT=${PORT}

echo "Starting Chainlit on ${HOST}:${PORT}"
exec chainlit run app.py --host "${HOST}" --port "${PORT}" --headless