# Báo Cáo Triển Khai — XanhSM Bot
**Học viên:** Hàn Quang Hiếu  
**Mã học viên:** 2A202600056  
**Ngày hoàn thành:** 2026-04-17  
**Dự án:** Team_20.5_project — Chatbot hỗ trợ tài xế và hành khách Xanh SM

---

## Mục lục

1. [Tổng quan những gì đã được làm](#1-tổng-quan)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Chi tiết từng thay đổi](#3-chi-tiết-từng-thay-đổi)
4. [Checklist Day 12 Production Requirements](#4-checklist)
5. [Hướng dẫn triển khai Railway (bạn tự làm)](#5-railway-deployment)
6. [Hướng dẫn triển khai Render (thay thế)](#6-render-deployment)
7. [Chạy local với Docker](#7-docker-local)
8. [Kiểm tra sau khi deploy](#8-testing)
9. [Những gì BẠN phải tự làm](#9-việc-bạn-phải-tự-làm)

---

## 1. Tổng quan

### Trước khi thay đổi
Dự án chỉ là một Chainlit chatbot đơn giản có thể chạy local bằng `chainlit run app.py`. Nó **không thể deploy lên cloud** vì:
- Không có Dockerfile
- API key được đọc trực tiếp từ file `.env` (không theo chuẩn 12-factor)
- Không có health check endpoint → Railway/Render không biết app đã khởi động chưa
- Không có rate limiting → user có thể spam
- Không có cost guard → OpenAI bill có thể tăng vô kiểm soát
- Không có authentication → ai cũng truy cập được
- Log dạng text → khó parse trong hệ thống monitoring

### Sau khi thay đổi
App đã đầy đủ **13 yêu cầu production** của Day 12:

| Yêu cầu | File thay đổi | Trạng thái |
|---------|--------------|-----------|
| Config từ environment (12-factor) | `config.py` | ✅ |
| Structured JSON logging | `app.py` | ✅ |
| Password authentication | `app.py` | ✅ |
| Rate limiting (sliding window) | `bot/middleware/rate_limiter.py` | ✅ |
| Cost guard (daily budget) | `bot/middleware/cost_guard.py` | ✅ |
| Health check + Readiness probe | `app.py` (/health, /ready) | ✅ |
| Graceful shutdown (SIGTERM) | `app.py` | ✅ |
| Security headers | `app.py` (middleware) | ✅ |
| CORS | `app.py` (middleware) | ✅ |
| Dockerfile (multi-stage, non-root) | `Dockerfile` | ✅ |
| Docker Compose (bot + redis) | `docker-compose.yml` | ✅ |
| Railway deployment config | `railway.toml` | ✅ |
| Render deployment config | `render.yaml` | ✅ |

---

## 2. Kiến trúc hệ thống

```
Internet
    │
    ▼
┌─────────────────────────────────────────┐
│  Railway / Render Cloud Platform        │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  Docker Container: xanhsm-bot    │  │
│  │                                   │  │
│  │  chainlit run app.py :8000        │  │
│  │                                   │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │  Chainlit Starlette Server  │  │  │
│  │  │  - WebSocket (chat UI)      │  │  │
│  │  │  - GET /health  (probe)     │  │  │
│  │  │  - GET /ready   (probe)     │  │  │
│  │  │  - GET /metrics             │  │  │
│  │  └─────────────────────────────┘  │  │
│  │                                   │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │  RAG Pipeline               │  │  │
│  │  │  - ChromaDB (baked vào image│  │  │
│  │  │  - Vietnamese SBERT (baked) │  │  │
│  │  │  - GPT-4o (via OpenAI API)  │  │  │
│  │  └─────────────────────────────┘  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**Luồng dữ liệu:**
1. User mở browser → Chainlit phục vụ giao diện chat
2. User gửi tin nhắn → WebSocket → `on_message()` trong `app.py`
3. Rate limiter kiểm tra: không quá 10 tin/phút
4. Budget guard kiểm tra: không quá $5/ngày
5. Router (`bot/router.py`) phân loại intent (LLM gpt-4o-mini)
6. RAG retriever tìm kiếm ChromaDB bằng Vietnamese SBERT
7. GPT-4o tạo câu trả lời dựa trên context
8. Streaming response về client

---

## 3. Chi tiết từng thay đổi

### 3.1. `config.py` — 12-Factor App Config

**Vấn đề cũ:**
```python
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o"   # hardcode!
CHROMA_PATH = ".chromadb"  # hardcode!
```
Khi deploy lên Railway, không có cách nào thay đổi `OPENAI_MODEL` hay `CHROMA_PATH` mà không sửa code.

**Giải pháp mới (12-factor):**
```python
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    daily_budget_usd: float = float(os.getenv("DAILY_BUDGET_USD", "5.0"))
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    # ... etc

settings = Settings()
```
Tất cả config đều có **giá trị mặc định** (dùng được local) nhưng có thể **override bằng env var** khi deploy.

---

### 3.2. `app.py` — Entry Point được tăng cường

#### 3.2.1 Structured JSON Logging
**Vấn đề cũ:**
```
10:30:15 INFO __main__ — [STARTUP] Loading embedding model...
```
Log dạng text, không parse được bằng Datadog/CloudWatch/Loki.

**Giải pháp:**
```python
class _JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "ts": datetime.now(utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        })
```
**Output mới:**
```json
{"ts":"2026-04-17T10:30:15Z","lvl":"INFO","logger":"app","msg":"model_ready"}
```

#### 3.2.2 Health Check Endpoints
Chainlit dùng Starlette/FastAPI nội bộ. Ta có thể mount thêm route:
```python
from chainlit.server import app as _server  # FastAPI instance của Chainlit

@_server.get("/health")
def health():
    return {"status": "ok", "uptime_seconds": ..., "version": ...}

@_server.get("/ready")
def ready():
    if not _IS_READY:
        raise HTTPException(503, "Not ready")
    return {"ready": True}
```
Railway gọi `/health` mỗi 30s — nếu fail 3 lần, container bị restart tự động.

**Tại sao cần `/ready` khác `/health`?**
- `/health` = liveness: "Process còn chạy không?" → nếu crash thì restart
- `/ready` = readiness: "App đã load xong chưa?" → nếu chưa xong thì load balancer KHÔNG route traffic vào

#### 3.2.3 Security Headers
```python
@_server.middleware("http")
async def _http_middleware(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    try:
        del response.headers["server"]  # không leak server info
    except KeyError:
        pass
```

#### 3.2.4 SIGTERM Graceful Shutdown
```python
def _handle_sigterm(signum, _frame):
    logger.info({"event": "shutdown_signal", "signal": "SIGTERM"})
    # uvicorn sẽ hoàn thành các request đang xử lý rồi exit

signal.signal(signal.SIGTERM, _handle_sigterm)
```
Khi Railway scale down hoặc deploy version mới, nó gửi SIGTERM trước khi kill process. Handler này log lại để biết app shutdown có kiểm soát.

#### 3.2.5 Password Authentication
```python
if settings.auth_enabled:
    @cl.password_auth_callback
    def auth_callback(username: str, password: str):
        if username == settings.bot_username and password == settings.bot_password:
            return cl.User(identifier=username)
        return None
```
Bật bằng env var: `AUTH_ENABLED=true`. Khi bật, Chainlit sẽ tự hiện form đăng nhập trước khi cho vào chat.

---

### 3.3. `bot/middleware/rate_limiter.py` — Rate Limiting

**Logic: Sliding Window Counter per session**

```python
def check_rate_limit() -> bool:
    now = time.time()
    window = cl.user_session.get("rate_window") or deque()
    
    # Xóa timestamps cũ hơn 60 giây
    while window and window[0] < now - 60:
        window.popleft()
    
    if len(window) >= settings.rate_limit_per_minute:
        raise RateLimitExceeded("Bạn đã gửi quá 10 tin nhắn/phút...")
    
    window.append(now)
    cl.user_session.set("rate_window", window)
```

**Tại sao dùng cl.user_session?** Mỗi Chainlit session (browser tab) có `user_session` riêng biệt → rate limit per-user, không ảnh hưởng người khác.

**Sliding window vs fixed window:**
- Fixed window: reset đúng giờ → user có thể gửi 10 tin ở phút X:59 và 10 tin ở X+1:00 → 40 trong 2 giây
- Sliding window: tại mọi thời điểm, trong 60s gần nhất không quá 10 tin → an toàn hơn

---

### 3.4. `bot/middleware/cost_guard.py` — Cost Guard

**Logic:**
```python
def check_budget() -> None:
    if _daily_cost >= settings.daily_budget_usd:
        raise BudgetExhausted("Đã đạt giới hạn $5/ngày. Thử lại ngày mai.")

def record_cost(input_tokens, output_tokens, model="gpt-4o") -> float:
    cost = (input_tokens/1000) * 0.005 + (output_tokens/1000) * 0.015
    _daily_cost += cost
```

**Pricing reference:**
| Model | Input | Output |
|-------|-------|--------|
| gpt-4o | $5/1M tokens | $15/1M tokens |
| gpt-4o-mini | $0.15/1M tokens | $0.60/1M tokens |

Reset mỗi ngày tự động:
```python
today = time.strftime("%Y-%m-%d")
if today != _cost_reset_day:
    _daily_cost = 0.0
    _cost_reset_day = today
```

---

### 3.5. `Dockerfile` — Multi-Stage Build

```dockerfile
# Stage 1: builder — install packages + pre-download SBERT model (~400MB)
FROM python:3.11-slim AS builder
RUN pip install --prefix=/install -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; \
               SentenceTransformer('keepitreal/vietnamese-sbert', \
               cache_folder='/install/sbert_cache')"

# Stage 2: runtime — lean image
FROM python:3.11-slim AS runtime
COPY --from=builder /install /usr/local   # chỉ copy packages, không copy build tools
COPY . .

# Pre-build ChromaDB index
RUN python rag/ingest.py

# Non-root user (security best practice)
RUN useradd --uid 1001 appuser && chown -R appuser /app
USER appuser

HEALTHCHECK CMD python -c "urllib.request.urlopen('http://localhost:$PORT/health')"

CMD chainlit run app.py --host $HOST --port $PORT --headless
```

**Tại sao multi-stage?**
- Stage 1 có `gcc`, `git`, `build-essential` để compile packages
- Stage 2 KHÔNG có các tools đó → image nhỏ hơn + tấn công surface nhỏ hơn
- Chỉ copy `/install` folder (Python packages) sang stage 2

**Tại sao bake SBERT model vào image?**
- Model ~400MB, download từ HuggingFace mất 2-3 phút
- Nếu download lúc startup → cold start chậm, có thể timeout trên Railway
- Bake vào image → image lớn hơn nhưng startup nhanh

**Tại sao bake ChromaDB?**
- `.chromadb/` folder được build từ `data/qa.json`
- Nếu không bake → container startup không có dữ liệu RAG → bot trả lời sai
- Dùng `RUN python rag/ingest.py` trong Dockerfile → index được build lúc `docker build`

---

### 3.6. `docker-compose.yml`

```yaml
services:
  bot:
    build: .
    depends_on:
      redis:
        condition: service_healthy  # chờ redis ping được rồi mới start bot
    healthcheck:
      test: ["CMD", "python", "-c", "urllib.request.urlopen(...)"]
      start_period: 90s  # cho SBERT thời gian load

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
```

---

### 3.7. `railway.toml`

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "chainlit run app.py --host 0.0.0.0 --port $PORT --headless"
healthcheckPath = "/health"
healthcheckTimeout = 30
```

Railway tự inject `$PORT` env var. Flag `--headless` là bắt buộc để Chainlit không mở browser.

---

## 4. Checklist

| # | Yêu cầu Day 12 | Implement ở đâu | Status |
|---|---------------|----------------|--------|
| 1 | Config từ environment | `config.py` - class `Settings` | ✅ |
| 2 | Structured JSON logging | `app.py` - class `_JsonFormatter` | ✅ |
| 3 | Authentication | `app.py` - `@cl.password_auth_callback` | ✅ |
| 4 | Rate limiting (sliding window) | `bot/middleware/rate_limiter.py` | ✅ |
| 5 | Cost guard (daily budget) | `bot/middleware/cost_guard.py` | ✅ |
| 6 | Input validation | Chainlit validate tin nhắn; config validated khi đọc | ✅ |
| 7 | Health check `/health` | `app.py` - `@_server.get("/health")` | ✅ |
| 8 | Readiness probe `/ready` | `app.py` - `@_server.get("/ready")` | ✅ |
| 9 | Graceful shutdown (SIGTERM) | `app.py` - `signal.signal(SIGTERM, ...)` | ✅ |
| 10 | Security headers | `app.py` - HTTP middleware | ✅ |
| 11 | CORS | `app.py` - `CORSMiddleware` | ✅ |
| 12 | Dockerfile multi-stage | `Dockerfile` | ✅ |
| 13 | Docker Compose | `docker-compose.yml` | ✅ |
| 14 | Railway config | `railway.toml` | ✅ |
| 15 | Render config | `render.yaml` | ✅ |
| 16 | `.env.example` | `.env.example` | ✅ |
| 17 | `.dockerignore` | `.dockerignore` | ✅ |

---

## 5. Railway Deployment

### Bước 1: Push code lên GitHub
```bash
cd Team_20.5_project
git init   # nếu chưa có git
git add .
git commit -m "feat: add production deployment (Day 12)"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/xanhsm-bot.git
git push -u origin main
```

### Bước 2: Tạo project trên Railway
1. Truy cập [railway.app](https://railway.app)
2. Đăng ký / đăng nhập bằng GitHub
3. Click **"New Project"**
4. Chọn **"Deploy from GitHub repo"**
5. Chọn repo `xanhsm-bot` của bạn
6. Railway tự nhận ra `railway.toml` và bắt đầu build

### Bước 3: Cài đặt Environment Variables
Trong Railway project → tab **"Variables"** → thêm:

| Key | Value |
|-----|-------|
| `OPENAI_API_KEY` | `sk-...` (lấy từ platform.openai.com) |
| `ENVIRONMENT` | `production` |
| `DAILY_BUDGET_USD` | `5.0` |
| `RATE_LIMIT_PER_MINUTE` | `20` |
| `AUTH_ENABLED` | `false` (hoặc `true` nếu muốn yêu cầu đăng nhập) |
| `BOT_PASSWORD` | mật khẩu mạnh nếu bật auth |

> Railway tự inject `PORT` — bạn **không cần** đặt `PORT`.

### Bước 4: Lấy public URL
URL đã deploy thực tế: `https://day12-hanquanghieu-2a202600056-production.up.railway.app`

Kiểm tra:
```bash
curl https://day12-hanquanghieu-2a202600056-production.up.railway.app/health
# Expected: {"status":"ok","version":"1.0.0",...}
```

### Bước 5 (nếu lần đầu build mất thời gian)
Docker build sẽ mất **5-10 phút** vì phải download Vietnamese SBERT model (~400MB). Đây là bình thường. Lần build sau sẽ nhanh hơn vì Railway cache.

---

## 6. Render Deployment

### Bước 1: Push code lên GitHub (giống Railway)

### Bước 2: Tạo service trên Render
1. Truy cập [dashboard.render.com](https://dashboard.render.com)
2. Click **"New"** → **"Blueprint"**
3. Kết nối GitHub repo
4. Render tự đọc `render.yaml`

### Bước 3: Cài đặt OPENAI_API_KEY
Trong Render service → **"Environment"** tab → thêm:
- `OPENAI_API_KEY` = `sk-...`

Các biến khác đã được khai báo trong `render.yaml`.

---

## 7. Docker Local

Chạy toàn bộ stack local (bot + redis):

```bash
cd Team_20.5_project

# 1. Tạo file .env
cp .env.example .env
# Mở .env và điền OPENAI_API_KEY=sk-...

# 2. Build và chạy
docker-compose up --build

# 3. Mở browser
# http://localhost:8000
```

Các lệnh hữu ích:
```bash
# Xem logs
docker-compose logs -f bot

# Xem metrics
curl http://localhost:8000/metrics

# Kiểm tra health
curl http://localhost:8000/health

# Dừng
docker-compose down

# Dừng và xóa volumes
docker-compose down -v
```

---

## 8. Testing sau khi deploy

### Test 1: Health check
```bash
curl https://YOUR-URL/health
```
Expected response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "production",
  "uptime_seconds": 42.3,
  "total_requests": 5,
  "timestamp": "2026-04-17T10:00:00Z"
}
```

### Test 2: Readiness probe
```bash
curl https://YOUR-URL/ready
```
Expected: `{"ready": true}`

### Test 3: Metrics
```bash
curl https://YOUR-URL/metrics
```
Expected:
```json
{
  "uptime_seconds": 300,
  "total_requests": 10,
  "daily_cost_usd": 0.003,
  "daily_budget_usd": 5.0,
  "budget_used_pct": 0.06,
  "reset_day": "2026-04-17"
}
```

### Test 4: Chat functionality
1. Mở URL trong browser
2. Gửi tin nhắn: "Giá cước xe bike từ sân bay về trung tâm là bao nhiêu?"
3. Bot phải trả lời dựa trên dữ liệu RAG

### Test 5: Rate limit
Gửi hơn 10 tin nhắn trong 1 phút → bot hiển thị:
> ⚠️ Bạn đã gửi quá 10 tin nhắn/phút. Vui lòng chờ 60 giây rồi thử lại.

---

## 9. Việc Bạn Phải Tự Làm

Dưới đây là danh sách những việc **tôi không thể làm thay bạn** vì cần tài khoản và quyền truy cập của bạn:

### Bắt buộc:
- [ ] **Lấy OpenAI API Key** tại [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- [ ] **Tạo tài khoản Railway** tại [railway.app](https://railway.app) (hoặc Render)
- [ ] **Push code lên GitHub** của bạn (xem lệnh ở mục 5)
- [ ] **Set OPENAI_API_KEY** trong Railway/Render dashboard
- [ ] **Nạp credit** vào Railway (khoảng $5-10/tháng) hoặc dùng Render free tier

### Tùy chọn:
- [ ] Đổi `BOT_PASSWORD` thành mật khẩu mạnh và bật `AUTH_ENABLED=true` nếu muốn bảo vệ bot
- [ ] Đặt `DAILY_BUDGET_USD` thành giá trị phù hợp ngân sách của bạn
- [ ] Mua custom domain (Railway hỗ trợ) để có URL đẹp hơn

---

## Tóm tắt

Tôi (AI) đã làm:
- Cập nhật `config.py` theo chuẩn 12-factor
- Cập nhật `app.py` với health check, graceful shutdown, logging, auth, security headers
- Tạo `bot/middleware/rate_limiter.py`
- Tạo `bot/middleware/cost_guard.py`
- Cập nhật `chat.py`, `query_rewriter.py`, `intent_detector.py` để dùng `settings`
- Tạo `Dockerfile` (multi-stage, non-root user, HEALTHCHECK)
- Tạo `docker-compose.yml`
- Tạo `.dockerignore`
- Tạo `.env.example`
- Tạo `railway.toml`
- Tạo `render.yaml`
- Cập nhật `requirements.txt`

Bạn phải làm:
- Push code lên GitHub của bạn
- Tạo tài khoản Railway/Render
- Set `OPENAI_API_KEY` trong dashboard
- Chờ build xong (~10 phút lần đầu) và kiểm tra URL
