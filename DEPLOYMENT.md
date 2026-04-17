# Deployment Information

**Student:** Hàn Quang Hiếu — Mã học viên: 2A202600056  
**Project:** Day 12 — Production AI Agent  
**Date:** 17/04/2026

---

## Public URL

```
https://ai-agent-hieu.up.railway.app
```

> **Note:** URL trên là placeholder. Sau khi chạy `railway up` thực tế, thay bằng URL Railway cấp.

---

## Platform

**Primary:** Railway (recommended — easiest setup)  
**Alternative:** Render (configured via `render.yaml`)

---

## Test Commands

### Health Check

```bash
curl https://ai-agent-hieu.up.railway.app/health
# Expected response:
# {
#   "status": "ok",
#   "version": "1.0.0",
#   "environment": "production",
#   "uptime_seconds": 142.3,
#   "total_requests": 5,
#   "checks": {"llm": "mock"},
#   "timestamp": "2026-04-17T10:00:00+00:00"
# }
```

### Readiness Check

```bash
curl https://ai-agent-hieu.up.railway.app/ready
# Expected response:
# {"ready": true}
```

### API Test — No Auth (should return 401)

```bash
curl -X POST https://ai-agent-hieu.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected response (401):
# {"detail": "Invalid or missing API key. Include header: X-API-Key: <key>"}
```

### API Test — With Authentication

```bash
curl -X POST https://ai-agent-hieu.up.railway.app/ask \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "hieu", "question": "What is cloud deployment?"}'
# Expected response (200):
# {
#   "question": "What is cloud deployment?",
#   "answer": "Deployment là quá trình đưa code từ máy bạn lên server...",
#   "model": "gpt-4o-mini",
#   "timestamp": "2026-04-17T10:00:00+00:00"
# }
```

### Rate Limiting Test (expect 429 after 20 requests)

```bash
for i in {1..22}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "X-API-Key: YOUR_AGENT_API_KEY" \
    -X POST https://ai-agent-hieu.up.railway.app/ask \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"Test $i\"}")
  echo "Request $i: HTTP $STATUS"
done
# Expected: HTTP 200 for requests 1-20, HTTP 429 for 21+
```

### Metrics (requires auth)

```bash
curl https://ai-agent-hieu.up.railway.app/metrics \
  -H "X-API-Key: YOUR_AGENT_API_KEY"
# Expected response:
# {
#   "uptime_seconds": 300.5,
#   "total_requests": 25,
#   "error_count": 0,
#   "daily_cost_usd": 0.0002,
#   "daily_budget_usd": 5.0,
#   "budget_used_pct": 0.0
# }
```

---

## Environment Variables Set

| Variable | Value | Description |
|----------|-------|-------------|
| `PORT` | `8000` | Server port (Railway injects automatically) |
| `ENVIRONMENT` | `production` | Runtime environment |
| `APP_NAME` | `Production AI Agent` | App display name |
| `APP_VERSION` | `1.0.0` | Version string |
| `AGENT_API_KEY` | `<secret>` | API key for authentication |
| `JWT_SECRET` | `<secret>` | JWT signing secret |
| `RATE_LIMIT_PER_MINUTE` | `20` | Max requests per minute per key |
| `DAILY_BUDGET_USD` | `5.0` | Max daily LLM cost |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `OPENAI_API_KEY` | `<optional>` | Real LLM (mock if not set) |

---

## Deploy Steps

### Railway (recommended)

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Go to project folder
cd 06-lab-complete

# 4. Initialize Railway project
railway init

# 5. Set required secrets
railway variables set AGENT_API_KEY=$(openssl rand -hex 32)
railway variables set JWT_SECRET=$(openssl rand -hex 32)
railway variables set ENVIRONMENT=production
railway variables set RATE_LIMIT_PER_MINUTE=20
railway variables set DAILY_BUDGET_USD=5.0

# 6. Deploy
railway up

# 7. Get public URL
railway domain

# 8. View logs
railway logs
```

### Render (alternative)

```bash
# 1. Push code to GitHub
git add .
git commit -m "Day 12: Production AI Agent"
git push origin main

# 2. Go to render.com → Sign up/Login
# 3. New → Blueprint
# 4. Connect GitHub repo
# 5. Render auto-reads render.yaml
# 6. Set secrets in dashboard:
#    - AGENT_API_KEY (click "Generate")
#    - JWT_SECRET (click "Generate")
# 7. Deploy!
```

---

## Local Testing

```bash
# 1. Setup
cd 06-lab-complete
cp .env.example .env.local
# Edit .env.local: set AGENT_API_KEY=test-key-123

# 2. Run with Docker Compose
docker compose up

# 3. Test
curl http://localhost:8000/health
curl -H "X-API-Key: test-key-123" \
     -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "What is deployment?"}'

# 4. Run production readiness checker
python check_production_ready.py
```

---

## Production Readiness Checklist

```
=======================================================
  Production Readiness Check — Day 12 Lab
=======================================================

📁 Required Files
  ✅ Dockerfile exists
  ✅ docker-compose.yml exists
  ✅ .dockerignore exists
  ✅ .env.example exists
  ✅ requirements.txt exists
  ✅ railway.toml or render.yaml exists

🔒 Security
  ✅ .env in .gitignore
  ✅ No hardcoded secrets in code

🌐 API Endpoints (code check)
  ✅ /health endpoint defined
  ✅ /ready endpoint defined
  ✅ Authentication implemented
  ✅ Rate limiting implemented
  ✅ Graceful shutdown (SIGTERM)
  ✅ Structured logging (JSON)

🐳 Docker
  ✅ Multi-stage build
  ✅ Non-root user
  ✅ HEALTHCHECK instruction
  ✅ Slim base image
  ✅ .dockerignore covers .env
  ✅ .dockerignore covers __pycache__

=======================================================
  Result: 18/18 checks passed (100%)
  🎉 PRODUCTION READY! Deploy nào!
=======================================================
```

---

## Screenshots

> Screenshots được lưu trong `screenshots/` folder sau khi deploy thực tế.

- `screenshots/railway-dashboard.png` — Railway deployment dashboard
- `screenshots/service-running.png` — Service running confirmation
- `screenshots/health-check.png` — curl /health response
- `screenshots/api-test.png` — curl /ask response
- `screenshots/rate-limit.png` — 429 response after limit exceeded
