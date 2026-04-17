# Deployment Information

**Student:** Hàn Quang Hiếu — Mã học viên: 2A202600056  
**Project:** Day 12 — XanhSM Bot (Chainlit AI Customer Service)  
**Date:** 17/04/2026

---

## Public URL

```
https://day12-hanquanghieu-2a202600056-production.up.railway.app
```

> **Note:** Đây là URL thực tế đã deploy thành công trên Railway (17/04/2026).  
> Mở URL trên trình duyệt → giao diện chat Chainlit của XanhSM Bot.

---

## Platform

**Primary:** Railway (recommended — easiest setup)  
**Alternative:** Render (configured via `render.yaml`)

---

## What's deployed

XanhSM Bot là một Chainlit chat bot hỗ trợ khách hàng dịch vụ xe máy chia sẻ XanhSM. Bot được deploy tại Railway, expose web UI chat tại URL trên.

**Endpoints hoạt động:**

| Endpoint | Method | Auth | Mô tả |
|----------|--------|------|-------|
| `/` | GET | ❌ | Giao diện chat Chainlit |
| `/health` | GET | ❌ | Liveness probe (Railway dùng endpoint này để restart container nếu fail) |

### Health Check

```bash
curl https://day12-hanquanghieu-2a202600056-production.up.railway.app/health
# Response:
# {"status":"ok"}
```

### Access the bot

Mở trình duyệt tại:
```
https://day12-hanquanghieu-2a202600056-production.up.railway.app
```

Giao diện chat Chainlit hiện ra. Nhắn tin để bắt đầu (hỏi về giá, đăng ký tài xế...).

> **Auth:** Mặc định `AUTH_ENABLED=false` trong production → không cần đăng nhập.  
> Để bật auth, set `AUTH_ENABLED=true` + `BOT_USERNAME` + `BOT_PASSWORD` + `CHAINLIT_AUTH_SECRET`.

---

## Environment Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `PORT` | Railway inject tự động | Server port |
| `ENVIRONMENT` | `production` | Runtime environment |
| `APP_NAME` | `XanhSM Bot` | App display name |
| `APP_VERSION` | `1.0.0` | Version string |
| `OPENAI_API_KEY` | `<secret>` | OpenAI API key (bắt buộc) |
| `OPENAI_MODEL` | `gpt-4o` | Model chính cho intent/complex queries |
| `OPENAI_MODEL_MINI` | `gpt-4o-mini` | Model nhẹ cho FAQ retrieval |
| `AUTH_ENABLED` | `false` | Bật/tắt Chainlit password auth |
| `BOT_USERNAME` | `admin` | Username (khi AUTH_ENABLED=true) |
| `BOT_PASSWORD` | `<secret>` | Password (khi AUTH_ENABLED=true) |
| `CHAINLIT_AUTH_SECRET` | `<secret>` | JWT secret cho Chainlit session (khi auth bật) |
| `RATE_LIMIT_PER_MINUTE` | `10` | Max tin nhắn / user / phút |
| `DAILY_BUDGET_USD` | `5.0` | Max OpenAI spend / ngày (USD) |
| `CHROMA_PATH` | `/app/.chromadb` | Đường dẫn ChromaDB vector store |
| `COLLECTION_NAME` | `xanhsm_qa` | Tên collection ChromaDB |

---

## Deploy Steps

### Railway (recommended)

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Go to project folder
cd day12_HanQuangHieu_2A202600056

# 4. Initialize Railway project
railway init

# 5. Set required secrets
railway variables set OPENAI_API_KEY=sk-your-key-here
railway variables set ENVIRONMENT=production

# (Optional) Enable login gate
railway variables set AUTH_ENABLED=true
railway variables set BOT_USERNAME=admin
railway variables set BOT_PASSWORD=$(openssl rand -hex 16)
railway variables set CHAINLIT_AUTH_SECRET=$(openssl rand -hex 32)

# 6. Deploy
railway up

# 7. Get public URL
railway domain

# 8. View logs
railway logs
```

> Railway đọc `railway.toml` → build từ `Dockerfile` → chạy `start.sh` → Chainlit lắng nghe trên `$PORT`.

### Render (alternative)

```bash
# 1. Push code to GitHub
git add .
git commit -m "Day 12: XanhSM Bot"
git push origin main

# 2. Go to render.com → New → Blueprint
# 3. Connect GitHub repo (point to day12_HanQuangHieu_2A202600056)
# 4. Render auto-reads render.yaml
# 5. Set secrets in dashboard:
#    - OPENAI_API_KEY
# 6. Deploy!
```

---

## Local Development

```bash
# 1. Go to project folder
cd day12_HanQuangHieu_2A202600056

# 2. Copy env template
cp .env.example .env
# Edit .env: đặt OPENAI_API_KEY=sk-your-key

# 3. Run with Docker Compose
docker compose up

# 4. Open browser
# http://localhost:8000

# 5. Test health check
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## Production Readiness Checklist

```
=======================================================
  XanhSM Bot — Production Readiness Checklist
=======================================================

📁 Required Files
  ✅ Dockerfile (multi-stage build)
  ✅ docker-compose.yml
  ✅ .dockerignore
  ✅ .env.example
  ✅ requirements.txt
  ✅ railway.toml
  ✅ render.yaml

🔒 Security
  ✅ .env in .gitignore
  ✅ No hardcoded secrets in code
  ✅ Non-root user (appuser) in Docker
  ✅ Security headers middleware (X-Content-Type-Options, X-Frame-Options)
  ✅ CORS middleware

🌐 Operations
  ✅ /health endpoint (liveness probe — Railway dùng để restart nếu fail)
  ✅ Graceful shutdown (SIGTERM handler)
  ✅ Structured JSON logging

🛡️ Rate Limiting & Cost Control
  ✅ Sliding-window rate limiter (10 tin nhắn/user/phút)
  ✅ Daily budget guard ($5 USD/ngày mặc định)

🐳 Docker
  ✅ Multi-stage build (builder + runtime)
  ✅ Non-root user
  ✅ HEALTHCHECK instruction
  ✅ Slim base image (python:3.11-slim)
  ✅ .dockerignore covers .env, __pycache__

=======================================================
```

---

## Screenshots

> Screenshots được lưu trong `day12_HanQuangHieu_2A202600056/screenshots/` sau khi deploy.

- `screenshots/Log in screen.png` — Màn hình đăng nhập (khi AUTH_ENABLED=true)
- `screenshots/Main chat screen.png` — Giao diện chat chính của XanhSM Bot
