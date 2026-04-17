# XanhSM AI Support Chatbot

Chatbot AI hỗ trợ khách hàng và tài xế **Xanh SM**, phân loại theo vai trò (Hành khách, Tài xế Taxi, Tài xế Bike, Nhà hàng).  
Dùng RAG + GPT-4o để trả lời từ knowledge base chính thức. Có tool calling tra cứu giá cước thực tế theo thành phố.

**Live URL:** https://day12-hanquanghieu-2a202600056-production.up.railway.app/

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose v2
- An **OpenAI API key** (required — the bot calls GPT-4o)

---

## Quickstart (Docker Compose — recommended)

```bash
# 1. Clone and enter the project folder
git clone <repo-url>
cd day12_HanQuangHieu_2A202600056

# 2. Copy the env template and add your OpenAI key
cp .env.example .env
# Open .env and set:  OPENAI_API_KEY=sk-...your-key...

# 3. Build and start
docker compose up --build

# 4. Open the chatbot
#    http://localhost:8000
```

> First startup takes ~90 seconds while the SBERT embedding model downloads and ChromaDB ingests 112 FAQ documents. Wait for the log line: `{"event": "ready"}`.

---

## Verify it's working

```bash
# Health check — should return {"status":"ok", ...}
curl http://localhost:8000/health

# Readiness probe — returns {"ready":true} after startup completes
curl http://localhost:8000/ready

# Metrics
curl http://localhost:8000/metrics
```

---

## Environment Variables

Copy `.env.example` to `.env`. Only `OPENAI_API_KEY` is required to run locally.

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `PORT` | `8000` | Server port |
| `AUTH_ENABLED` | `false` | Set `true` to enable login screen |
| `BOT_USERNAME` | `admin` | Login username (when AUTH_ENABLED=true) |
| `BOT_PASSWORD` | `changeme` | Login password (when AUTH_ENABLED=true) |
| `CHAINLIT_AUTH_SECRET` | — | Required when AUTH_ENABLED=true (random 32-char string) |
| `DAILY_BUDGET_USD` | `5.0` | Max OpenAI spend per day in USD |
| `RATE_LIMIT_PER_MINUTE` | `10` | Max messages per user per minute |
| `REDIS_URL` | *(auto in compose)* | Redis for cross-instance state |

---

## Run without Docker (local Python)

```bash
# Requires Python 3.11+
cd day12_HanQuangHieu_2A202600056
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set OPENAI_API_KEY

chainlit run app.py --host 0.0.0.0 --port 8000 --headless
```

---

## Stop

```bash
docker compose down
```

To also delete persisted data (ChromaDB + feedback):
```bash
docker compose down -v
```

---

## Project Structure

```
day12_HanQuangHieu_2A202600056/
├── app.py                  # Chainlit entry point (auth, health, logging)
├── config.py               # All config from environment (12-factor)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml      # Bot + Redis
├── railway.toml            # Railway deployment config
├── render.yaml             # Render deployment config
├── .env.example            # Environment template
├── bot/
│   ├── router.py           # Intent routing
│   ├── handlers/           # chat, onboarding, driver_registration
│   ├── middleware/         # rate_limiter.py, cost_guard.py
│   └── tools/              # fare_data, intent_detector, query_rewriter
├── rag/
│   ├── vectorstore.py      # ChromaDB setup
│   ├── retriever.py        # RAG retrieval
│   └── ingest.py           # Load data/qa.json into ChromaDB
└── data/
    └── qa.json             # 112 FAQ documents (auto-ingested on first boot)
```

---

## Cloud Deployment (Railway)

The app is already deployed at:  
**https://day12-hanquanghieu-2a202600056-production.up.railway.app/**

To redeploy your own instance:
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
npx @railway/cli up
```

Set these environment variables in the Railway dashboard:
- `OPENAI_API_KEY`
- `CHAINLIT_AUTH_SECRET` (generate: `python -c "import secrets; print(secrets.token_hex(32))"`)
- `AUTH_ENABLED=true`
- `BOT_USERNAME` / `BOT_PASSWORD`
- `ENVIRONMENT=production`
