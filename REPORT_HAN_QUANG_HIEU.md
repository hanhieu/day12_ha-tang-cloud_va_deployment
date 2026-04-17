# Báo Cáo Lab Day 12 — Hạ Tầng Cloud & Deployment

**Họ và tên:** Hàn Quang Hiếu  
**Mã học viên:** 2A202600056  
**Ngày:** 17/04/2026  
**Môn:** AICB-P1 · VinUniversity 2026  
**Lab:** Day 12 — Đưa AI Agent Lên Cloud

---

## Mục Lục

1. [Tổng quan](#1-tổng-quan)
2. [Part 1 — Localhost vs Production](#2-part-1--localhost-vs-production)
3. [Part 2 — Docker Containerization](#3-part-2--docker-containerization)
4. [Part 3 — Cloud Deployment](#4-part-3--cloud-deployment)
5. [Part 4 — API Security](#5-part-4--api-security)
6. [Part 5 — Scaling & Reliability](#6-part-5--scaling--reliability)
7. [Part 6 — Final Project (Lab 06 Complete)](#7-part-6--final-project-lab-06-complete)
8. [Kết Luận](#8-kết-luận)

---

## 1. Tổng Quan

Lab Day 12 dạy cách đưa một AI agent từ môi trường development lên production cloud. Toàn bộ lab chia thành 6 phần liên tiếp nhau, mỗi phần xây dựng trên kiến thức của phần trước:

```
Part 1: Nhận ra vấn đề dev/prod gap
    ↓
Part 2: Đóng gói bằng Docker
    ↓
Part 3: Deploy lên Cloud
    ↓
Part 4: Bảo mật API
    ↓
Part 5: Scale và tin cậy
    ↓
Part 6: Kết hợp tất cả → Production-ready agent
```

**Công nghệ sử dụng:**
- Python 3.11 + Chainlit + FastAPI (Chainlit dùng FastAPI nội bộ)
- OpenAI API — `gpt-4o` / `gpt-4o-mini` (LLM thật)
- ChromaDB + Vietnamese SBERT (vector store cho RAG)
- Docker + Docker Compose
- Railway / Render (cloud platforms)

---

## 2. Part 1 — Localhost vs Production

### 2.1 Vấn đề "Works on my machine"

Đây là vấn đề kinh điển trong phát triển phần mềm: code chạy tốt trên máy developer nhưng fail khi deploy lên server. Nguyên nhân thường đến từ:

- **Hardcoded secrets** — API key, database password viết thẳng trong code
- **Environment dependency** — Python version khác, OS khác, thư viện khác
- **Missing health checks** — Platform không biết khi nào container cần restart
- **Inflexible config** — Port, host, debug mode cố định trong code

### 2.2 Anti-patterns trong `develop/app.py`

Phân tích file `01-localhost-vs-production/develop/app.py`:

```python
# ❌ VẤN ĐỀ 1: Secret hardcode
OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"
DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"
```

**Tại sao nguy hiểm?** Khi push lên GitHub (dù private), key bị lộ. Nếu attacker lấy được key, họ dùng API quota của bạn → bill khổng lồ. Không có cách "unsee" key sau khi push — phải rotate (đổi key mới) ngay.

```python
# ❌ VẤN ĐỀ 2: Debug mode cứng
DEBUG = True  # Luôn bật, kể cả production

# ❌ VẤN ĐỀ 3: Logging bằng print() và log ra secret
print(f"[DEBUG] Using key: {OPENAI_API_KEY}")
```

**Tại sao nguy hiểm?** `print()` không có log level (INFO/WARNING/ERROR), không có timestamp, không có format chuẩn — không thể parse bởi Datadog/CloudWatch. Và nghiêm trọng hơn: log ra secret key → secret bị lưu vào log files và log aggregators!

```python
# ❌ VẤN ĐỀ 4: Không có health check
# Platform không biết khi nào restart container

# ❌ VẤN ĐỀ 5: Host binding sai
uvicorn.run("app:app", host="localhost", port=8000, reload=True)
#                        ^^^^^^^^^^^^ chỉ nhận localhost
#                                            ^^^^  cứng port
#                                                        ^^^^^^ reload trong production
```

`host="localhost"` → container chỉ nhận kết nối từ chính nó. Nginx hoặc Railway cần kết nối từ ngoài → fail. Phải dùng `host="0.0.0.0"`.

### 2.3 Giải pháp: 12-Factor App

File `production/app.py` và `production/config.py` implement 12-factor principles:

```python
# ✅ GIẢI PHÁP: Config từ environment variables
@dataclass
class Settings:
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
```

**Nguyên lý:** Tách config khỏi code. Cùng 1 binary, deploy lên dev/staging/production chỉ khác environment variables.

```python
# ✅ Structured JSON logging — không log secret
logger.info(json.dumps({
    "event": "agent_request",
    "question_length": len(question),  # chỉ log length, không log content
    "client_ip": request.client.host,  # không log API key!
}))
```

**Nguyên lý:** Log phải có structure (JSON) để dễ parse. Không bao giờ log secret.

```python
# ✅ Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok", "uptime_seconds": uptime, ...}

@app.get("/ready")  
def readiness_check():
    if not is_ready:
        raise HTTPException(503, "Not ready")
    return {"ready": True}
```

**Nguyên lý:** Platform cần 2 loại health check:
- **Liveness** (`/health`): "Process còn sống không?" → fail → restart
- **Readiness** (`/ready`): "Sẵn sàng nhận traffic không?" → fail → stop routing, không restart

```python
# ✅ Graceful shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init connections, load model
    is_ready = True
    yield  # App running
    # Shutdown: finish in-flight requests, close connections
    is_ready = False
    logger.info("Finishing in-flight requests...")
    time.sleep(0.1)
```

**Nguyên lý:** Khi platform muốn tắt container (rolling deploy, scale down), nó gửi SIGTERM. App phải hoàn thành request đang xử lý trước khi tắt → không mất data, không trả lỗi về client.

### 2.4 Bảng So Sánh Tổng Hợp

| Feature | Develop (❌) | Production (✅) | Tại Sao Quan Trọng |
|---------|-------------|----------------|-------------------|
| Secrets | Hardcode trong code | `os.getenv()` | Tránh lộ key trên Git |
| Logging | `print()` + log secret | JSON structured, no secrets | Searchable logs, bảo mật |
| Host | `localhost` | `0.0.0.0` | Container nhận external traffic |
| Port | Cứng `8000` | `int(os.getenv("PORT", 8000))` | Railway/Render inject PORT |
| Debug | Luôn `True` | Từ env var `DEBUG` | Performance & security |
| Health check | Không có | `/health` + `/ready` | Platform biết khi nào restart |
| Shutdown | Đột ngột | Graceful (finish in-flight) | Không mất request |
| CORS | Không có | `CORSMiddleware` từ config | Kiểm soát origins |

---

## 3. Part 2 — Docker Containerization

### 3.1 Tại Sao Cần Docker?

Vấn đề tiếp theo sau "works on my machine": Python version khác nhau, package version conflict, OS-specific dependencies. Docker giải quyết bằng cách đóng gói **app + runtime + dependencies** vào 1 container image.

**Lợi ích:**
- **Consistent environment**: Image chạy giống nhau trên laptop, CI/CD, production
- **Isolation**: Container A không ảnh hưởng Container B
- **Reproducible builds**: `docker build` cho cùng kết quả trên mọi máy
- **Easy rollback**: `docker run old-image` để quay về version cũ

### 3.2 Dockerfile Cơ Bản (`02-docker/develop/Dockerfile`)

```dockerfile
FROM python:3.11          # Base image: Python 3.11 full (~1 GB)
WORKDIR /app              # Working directory trong container
COPY requirements.txt .   # Copy requirements TRƯỚC (Docker layer cache)
RUN pip install -r ...    # Install dependencies (cached nếu req.txt không đổi)
COPY app.py .             # Copy code SAU (thay đổi thường xuyên)
EXPOSE 8000               # Documentation (không thực sự mở port)
CMD ["python", "app.py"]  # Default command
```

**Tại sao COPY requirements.txt trước?**

Docker build = chuỗi layers. Mỗi layer được cache. Nếu 1 layer thay đổi → tất cả layers sau phải rebuild.

```
Layer 1: FROM python:3.11          → cached (không đổi)
Layer 2: WORKDIR /app              → cached
Layer 3: COPY requirements.txt .  → cached NẾU req.txt không đổi
Layer 4: RUN pip install           → cached NẾU layer 3 cached
Layer 5: COPY app.py .             → ALWAYS rebuild (code thay đổi thường)
```

Nếu copy code trước: mỗi lần sửa code → Layer 3 thay đổi → phải rebuild pip install (tốn 2–5 phút mỗi build!). Copy requirements.txt trước → pip install chỉ rebuild khi thêm/bỏ package.

**CMD vs ENTRYPOINT:**

```dockerfile
# CMD — default command, có thể override
CMD ["python", "app.py"]
# docker run my-image              → chạy "python app.py"
# docker run my-image /bin/sh      → chạy "/bin/sh" (override!)

# ENTRYPOINT — fixed executable
ENTRYPOINT ["uvicorn"]
CMD ["app:app", "--port", "8000"]
# docker run my-image              → chạy "uvicorn app:app --port 8000"
# docker run my-image --port 9000  → chạy "uvicorn --port 9000" (thêm arg)
```

### 3.3 Multi-Stage Build (`02-docker/production/Dockerfile`)

**Vấn đề với single-stage:** Để compile Python packages (numpy, psycopg2...), cần `gcc`, `libpq-dev`. Nhưng production chỉ cần packages đã compile, không cần build tools. Single-stage → final image chứa cả build tools → nặng + attack surface lớn hơn.

**Giải pháp: Multi-stage build:**

```dockerfile
# ── Stage 1: Builder ──────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /app

# Cài build tools (chỉ dùng trong stage này)
RUN apt-get update && apt-get install -y gcc libpq-dev

# Install packages với --user (vào /root/.local)
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user — security best practice
RUN groupadd -r appuser && useradd -r -g appuser appuser
WORKDIR /app

# Chỉ copy packages đã compiled từ Stage 1 (không copy gcc, build tools)
COPY --from=builder /root/.local /home/appuser/.local
COPY main.py .

RUN chown -R appuser:appuser /app
USER appuser  # Chạy với non-root user

ENV PATH=/home/appuser/.local/bin:$PATH

# HEALTHCHECK — Docker tự restart nếu fail
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

**Kết quả:**
- `python:3.11` full: ~1.1 GB
- `python:3.11-slim` single-stage: ~250 MB
- Multi-stage với slim: ~150–200 MB
- **Image nhỏ hơn 5x** → push/pull nhanh hơn, deploy nhanh hơn, ít attack surface

**Tại sao non-root user?**

Nếu có lỗ hổng bảo mật và attacker vào được container, chạy với root = attacker có quyền root trong container. Với non-root user `appuser`, damage bị giới hạn. Best practice cho mọi production container.

### 3.4 Docker Compose Stack (`02-docker/production/docker-compose.yml`)

```yaml
services:
  agent:      # FastAPI app — 2 replicas
  redis:      # Session cache, rate limiting
  qdrant:     # Vector database (RAG)
  nginx:      # Reverse proxy, load balancer
```

**Architecture:**
```
Internet → Nginx (port 80/443) → Agent instances → Redis/Qdrant
```

**Điểm quan trọng:**
- Agent **không expose port ra ngoài** — chỉ Nginx tiếp xúc Internet
- Tất cả services trong network `internal` — isolate internal traffic
- `depends_on` với health check condition → Redis phải healthy trước khi Agent start
- `restart: unless-stopped` → tự restart nếu crash

**Debug container:**
```bash
docker logs <container_id>          # Xem logs
docker exec -it <container_id> sh   # Vào container
docker stats                        # CPU/Memory usage
docker inspect <container_id>       # Chi tiết config
```

---

## 4. Part 3 — Cloud Deployment

### 4.1 So Sánh Các Platform

| Platform | Độ Khó | Free Tier | Phù Hợp | Tự Động Scale |
|----------|--------|-----------|----------|---------------|
| **Railway** | ⭐ (dễ nhất) | $5 credit | Prototypes, học | Không |
| **Render** | ⭐⭐ | 750h/tháng | Side projects | Có (paid) |
| **GCP Cloud Run** | ⭐⭐⭐ | 2M requests/tháng | Production | Có (built-in) |

**Railway** được chọn vì: deploy nhanh nhất (< 5 phút), không cần setup infrastructure, phù hợp cho học tập.

### 4.2 Deploy Lên Railway

**Cách hoạt động:**
1. Railway CLI đọc `railway.toml` để biết cách build
2. Nó build Docker image từ `Dockerfile`
3. Push image lên Railway's container registry
4. Deploy container với environment variables đã set
5. Cấp public URL với HTTPS tự động

```toml
# railway.toml
[build]
builder = "DOCKERFILE"     # Dùng Dockerfile để build

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2"
healthcheckPath = "/health" # Railway check endpoint này
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

**Tại sao `$PORT` (không phải port cố định)?**

Railway không guarantee port 8000 available. Railway inject `PORT` env var với port mà nó muốn app lắng nghe. App phải đọc `$PORT`. Đây là lý do tại sao production app luôn dùng `int(os.getenv("PORT", 8000))`.

### 4.3 Deploy Lên Render

```yaml
# render.yaml — infrastructure as code
services:
  - type: web
    name: ai-agent-production
    runtime: docker
    region: singapore        # Gần Việt Nam
    plan: starter
    healthCheckPath: /health
    autoDeploy: true         # Auto deploy khi push GitHub
    envVars:
      - key: AGENT_API_KEY
        generateValue: true  # Render tự tạo random key!
      - key: JWT_SECRET
        generateValue: true
```

**Điểm hay của Render:** `generateValue: true` tự tạo secure random key, không cần developer tạo thủ công. Giảm rủi ro dùng key yếu.

### 4.4 GCP Cloud Run (Advanced)

Cloud Run là **serverless containers** — chỉ chạy khi có request, scale về 0 khi không có traffic.

```yaml
# cloudbuild.yaml — CI/CD pipeline
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/agent:$COMMIT_SHA', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/agent:$COMMIT_SHA']
  - name: 'gcr.io/cloud-builders/gcloud'
    args: ['run', 'deploy', 'agent', '--image', 'gcr.io/$PROJECT_ID/agent:$COMMIT_SHA']
```

**Lợi thế Cloud Run:**
- Scale to zero → $0 khi không có traffic
- Scale to N → handle traffic burst tự động
- HTTPS, custom domain miễn phí
- 2 million requests/month free tier

---

## 5. Part 4 — API Security

### 5.1 Tại Sao Cần Bảo Mật API?

Public URL = bất kỳ ai cũng gọi được → 3 rủi ro:

1. **Bill bất ngờ**: Attacker gọi LLM API bằng key của bạn → hàng nghìn USD bill
2. **Abuse**: Spam requests làm chậm service cho users thật
3. **Data leak**: Trả lời câu hỏi nhạy cảm cho người không có quyền

**Giải pháp 3 lớp:**
```
Request → Authentication → Rate Limiting → Cost Guard → LLM
         (ai được gọi?)  (bao nhiêu lần?) (tốn bao nhiêu $?)
```

### 5.2 Layer 1: API Key Authentication

**Simple nhất — phù hợp cho MVP và internal APIs:**

```python
API_KEY = os.getenv("AGENT_API_KEY", "demo-key")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key:
        raise HTTPException(401, "Missing API key")
    if api_key != API_KEY:
        raise HTTPException(403, "Invalid API key")
    return api_key

@app.post("/ask")
async def ask_agent(
    question: str,
    _key: str = Depends(verify_api_key),  # Inject auth dependency
):
    ...
```

**Cách rotate key:** Đổi `AGENT_API_KEY` env var → restart → key cũ invalid ngay. Không cần sửa code.

### 5.3 Layer 2: JWT Authentication (Advanced)

**JWT (JSON Web Token)** = stateless auth. Token chứa thông tin user và được sign bằng secret key.

**Cấu trúc JWT:**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9    ← Header (algorithm)
.
eyJzdWIiOiJzdHVkZW50Iiwicm9sZSI6InVzZXIiLCJleHAiOjE3NDUwNTQ0MDB9  ← Payload
.
SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c  ← Signature
```

**Decode payload:**
```json
{
  "sub": "student",
  "role": "user",
  "iat": 1745050800,
  "exp": 1745054400
}
```

**JWT Flow:**
```
1. POST /auth/token {username, password}
   → Server verify credentials
   → Create payload: {sub, role, exp}
   → Sign với SECRET_KEY → JWT string
   → Return JWT to client

2. POST /ask (Authorization: Bearer <JWT>)
   → Server decode JWT
   → Verify signature (không cần DB!)
   → Check expiry
   → Extract user info
   → Process request
```

**Tại sao JWT tốt hơn session?**
- Session = server lưu state → không scale (instance A không biết session của instance B)
- JWT = stateless → bất kỳ instance nào cũng verify được → scale tốt

**Tại sao cần expiry?**
JWT không thể revoke → nếu bị lộ, attacker dùng được cho đến khi expire. Expiry ngắn (60 phút) giới hạn damage window. Dùng refresh token để không cần login lại.

### 5.4 Layer 2.5: Role-Based Access

```python
DEMO_USERS = {
    "student": {"password": "demo123", "role": "user",  "daily_limit": 50},
    "teacher": {"password": "teach456", "role": "admin", "daily_limit": 1000},
}

# Trong endpoint /ask:
role = user["role"]
limiter = rate_limiter_admin if role == "admin" else rate_limiter_user
```

Admin có rate limit cao hơn (100 req/min vs 10 req/min). Còn endpoint `/admin/stats` chỉ admin mới truy cập được.

### 5.5 Layer 3: Rate Limiting

**Algorithm: Sliding Window Counter**

```python
class RateLimiter:
    def __init__(self, max_requests=10, window_seconds=60):
        self._windows: dict[str, deque] = defaultdict(deque)

    def check(self, user_id: str):
        now = time.time()
        window = self._windows[user_id]

        # Xóa timestamps cũ (ngoài window 60s)
        while window and window[0] < now - self.window_seconds:
            window.popleft()

        if len(window) >= self.max_requests:
            raise HTTPException(429, "Rate limit exceeded")

        window.append(now)  # Ghi nhận request mới
```

**Ví dụ hoạt động (10 req/min limit):**
```
t=0s:   [0]           → 1 request, OK
t=10s:  [0, 10]       → 2 requests, OK
...
t=55s:  [0,10,20,30,40,50,55] → 7 requests, OK
t=65s:  [10,20,30,40,50,55,65] → 7 requests, xóa t=0, OK
t=70s:  [10,20,...,70] → 8, OK
t=75s, t=80s, t=85s: 10, 11 → BLOCK! 429
```

**Sliding window vs Fixed window:**
- Fixed: Reset mỗi 60s đúng (00:00, 01:00, ...) → có thể send 20 requests ở giây 59 và 20 requests ở giây 61 = 40 trong 2 giây!
- Sliding: Cửa sổ 60s trượt theo thời gian → không có burst này

### 5.6 Layer 4: Cost Guard

```python
PRICE_PER_1K_INPUT_TOKENS = 0.00015   # GPT-4o-mini: $0.15/1M tokens
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006

class CostGuard:
    def check_budget(self, user_id: str):
        record = self._get_record(user_id)

        # Global budget: $10/ngày cho toàn service
        if self._global_cost >= 10.0:
            raise HTTPException(503, "Service temporarily unavailable")

        # Per-user budget: $1/ngày
        if record.total_cost_usd >= 1.0:
            raise HTTPException(402, "Daily budget exceeded")

    def record_usage(self, user_id, input_tokens, output_tokens):
        cost = (input_tokens/1000 * 0.00015 + output_tokens/1000 * 0.0006)
        self._global_cost += cost
        record.input_tokens += input_tokens
        record.output_tokens += output_tokens
```

**Tại sao check TRƯỚC khi gọi LLM?**
Nếu check sau, bạn đã tốn tiền rồi mới biết vượt budget. Check trước → không gọi LLM nếu budget hết.

**HTTP 402 Payment Required:**
Đây là status code chuẩn cho "budget exceeded". Client hiểu phải upgrade hoặc đợi reset.

### 5.7 Security Headers

```python
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"    # Chặn MIME sniffing
    response.headers["X-Frame-Options"] = "DENY"              # Chặn iframe embedding
    response.headers["X-XSS-Protection"] = "1; mode=block"    # XSS protection
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers.pop("server", None)                       # Ẩn server info
    return response
```

Ẩn "server" header để attacker không biết đang dùng uvicorn version nào → không khai thác CVE cụ thể.

---

## 6. Part 5 — Scaling & Reliability

### 6.1 Tại Sao Cần Scale?

1 instance FastAPI với 1 CPU: xử lý ~100 requests/giây (tùy app).  
LLM call = ~1–3 giây per request → throughput thực tế ~1–3 requests/giây per instance.  
→ Cần nhiều instances chạy song song.

**Nhưng scale out sinh ra vấn đề mới:** Nếu state (conversation history, user session) lưu trong memory của instance → instance A không biết state của instance B → bug khi scale.

### 6.2 Health Checks

**Liveness Probe (`/health`):**
```python
@app.get("/health")
def health():
    uptime = round(time.time() - START_TIME, 1)
    checks = {}

    try:
        import psutil
        mem = psutil.virtual_memory()
        checks["memory"] = {
            "status": "ok" if mem.percent < 90 else "degraded",
            "used_percent": mem.percent,
        }
    except ImportError:
        checks["memory"] = {"status": "ok"}

    overall_status = "ok" if all(
        v.get("status") == "ok" for v in checks.values()
    ) else "degraded"

    return {
        "status": overall_status,
        "uptime_seconds": uptime,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
```

**Readiness Probe (`/ready`):**
```python
@app.get("/ready")
def ready():
    if not _is_ready:  # False khi đang startup hoặc shutdown
        raise HTTPException(503, "Not ready")
    return {"ready": True, "in_flight_requests": _in_flight_requests}
```

**Vì sao cần 2 endpoints?**

| Scenario | `/health` | `/ready` |
|----------|-----------|---------|
| App vừa start, model đang load | ✅ 200 | ❌ 503 |
| App đang chạy bình thường | ✅ 200 | ✅ 200 |
| App đang shutdown (finishing requests) | ✅ 200 | ❌ 503 |
| App crash / memory > 90% | ❌ non-200 | ❌ non-200 |

Liveness fail → **restart container**  
Readiness fail → **stop routing traffic** (nhưng không restart)

Container vừa start cần ~2 giây để warm up. Readiness 503 trong giai đoạn này → load balancer không route traffic vào → không có request lỗi. Liveness vẫn 200 → không bị restart oan.

### 6.3 Graceful Shutdown

**Vấn đề:** Platform muốn tắt container (rolling deploy, scale down) → gửi SIGTERM. App tắt ngay → requests đang xử lý bị kill → client nhận lỗi.

**Giải pháp:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    # Startup
    logger.info("Starting up...")
    time.sleep(0.2)
    _is_ready = True

    yield  # App chạy bình thường

    # Shutdown (triggered by SIGTERM)
    _is_ready = False  # Stop readiness probe → LB stops routing new requests
    logger.info("Graceful shutdown initiated...")

    # Wait for in-flight requests
    timeout, elapsed = 30, 0
    while _in_flight_requests > 0 and elapsed < timeout:
        logger.info(f"Waiting for {_in_flight_requests} in-flight requests...")
        time.sleep(1)
        elapsed += 1

    logger.info("All requests done. Shutdown complete.")
```

**Timeline graceful shutdown:**
```
t=0s:  SIGTERM nhận
t=0s:  _is_ready = False → /ready trả 503 → LB stop routing new requests
t=0s:  Đợi in-flight requests (tối đa 30s)
t=2s:  In-flight request cuối hoàn thành
t=2s:  Process exit clean
```

### 6.4 Stateless Design

**Anti-pattern (stateful):**
```python
# ❌ State trong memory instance
conversation_history = {}  # Instance-local!

@app.post("/ask")
def ask(user_id: str, question: str):
    history = conversation_history.get(user_id, [])
    # ... process với history
    conversation_history[user_id] = updated_history
```

Khi scale lên 3 instances:
```
Request 1 → Instance A → lưu history trong memory A
Request 2 → Instance B → KHÔNG CÓ history → broken conversation!
```

**Correct (stateless):**
```python
# ✅ State trong Redis (shared storage)
def save_session(session_id: str, data: dict, ttl=3600):
    _redis.setex(f"session:{session_id}", ttl, json.dumps(data))

def load_session(session_id: str) -> dict:
    data = _redis.get(f"session:{session_id}")
    return json.loads(data) if data else {}

@app.post("/chat")
async def chat(body: ChatRequest):
    session_id = body.session_id or str(uuid.uuid4())
    session = load_session(session_id)  # Từ Redis
    history = session.get("history", [])

    answer = ask(body.question)
    append_to_history(session_id, "assistant", answer)  # Vào Redis

    return {"session_id": session_id, "answer": answer, "served_by": INSTANCE_ID}
```

Khi scale 3 instances:
```
Request 1 → Instance A → đọc/ghi Redis
Request 2 → Instance B → đọc Redis (có history từ request 1!) → ✅
Request 3 → Instance C → đọc Redis (có history đầy đủ!) → ✅
```

**`INSTANCE_ID` trong response:**
```python
INSTANCE_ID = os.getenv("INSTANCE_ID", f"instance-{uuid.uuid4().hex[:6]}")
```

Client thấy `"served_by": "instance-abc123"` → chứng minh các request đến các instances khác nhau nhưng session vẫn liên tục.

### 6.5 Load Balancing với Nginx

```nginx
upstream agent_cluster {
    server agent:8000;  # Docker DNS resolve "agent" → round-robin IPs
    keepalive 16;       # Giữ 16 kết nối persistent → ít overhead
}

server {
    listen 80;
    add_header X-Served-By $upstream_addr always;  # Debug: biết request đến instance nào

    location / {
        proxy_pass http://agent_cluster;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_next_upstream error timeout http_503;  # Failover nếu instance die
        proxy_next_upstream_tries 3;                 # Thử tối đa 3 instances
    }
}
```

**`proxy_next_upstream`:** Nếu instance 1 trả 503 hoặc timeout → Nginx tự retry sang instance 2. Client không thấy lỗi!

---

## 7. Part 6 — Final Project (XanhSM Bot)

### 7.1 Kiến Trúc Tổng Thể

```
┌────────────────────────────────────────────────────────────┐
│                         BROWSER                             │
│   Người dùng / Giáo viên chấm điểm                         │
└───────────────────────┬────────────────────────────────────┘
                        │ HTTPS (Railway domain)
                        ▼
┌────────────────────────────────────────────────────────────┐
│              XanhSM Bot — Chainlit Application              │
│          (day12_HanQuangHieu_2A202600056/app.py)            │
│                                                             │
│  Middleware (trên Chainlit's FastAPI server):               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. CORSMiddleware                                    │   │
│  │ 2. HTTP middleware — security headers + JSON logging │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Operations:                                                │
│  ┌──────────────────────────────────────────────────┐      │
│  │  GET /health  → {"status":"ok"}  (Railway probe)  │      │
│  └──────────────────────────────────────────────────┘      │
│                                                             │
│  Chainlit UI (tất cả các routes khác):                     │
│  /   → Giao diện chat XanhSM                               │
│                                                             │
│  Per-message middleware chain:                              │
│  Rate Limiter (10/min) → Cost Guard ($5/day) → Router      │
│                                                             │
│  Bot Handlers:                                              │
│  ┌──────────────────────────────────────────────────┐      │
│  │ Intent Detector → FAQ (RAG) / Giá xe / Đăng ký tài│     │
│  └──────────────────────────────────────────────────┘      │
└───────────────────────┬────────────────────────────────────┘
                        │
              ┌─────────┴──────────┐
              ▼                    ▼
   ┌─────────────────┐   ┌──────────────────────┐
   │  OpenAI API     │   │  ChromaDB            │
   │  gpt-4o-mini    │   │  Vietnamese SBERT    │
   │  (real LLM)     │   │  (FAQ retrieval RAG) │
   └─────────────────┘   └──────────────────────┘
```

### 7.2 Giải Thích Từng File

#### `config.py` — Centralized Configuration

```python
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    openai_model_mini: str = os.getenv("OPENAI_MODEL_MINI", "gpt-4o-mini")
    port: int = int(os.getenv("PORT", "8000"))
    host: str = os.getenv("HOST", "0.0.0.0")
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    bot_username: str = os.getenv("BOT_USERNAME", "admin")
    bot_password: str = os.getenv("BOT_PASSWORD", "changeme")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    daily_budget_usd: float = float(os.getenv("DAILY_BUDGET_USD", "5.0"))
    chroma_path: str = os.getenv("CHROMA_PATH", ".chromadb")
    collection_name: str = os.getenv("COLLECTION_NAME", "xanhsm_qa")
    app_name: str = os.getenv("APP_NAME", "XanhSM Bot")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")

settings = Settings()
```

**12-factor compliant:** Tất cả config đọc từ environment variables. Không hardcode secret.

#### `app.py` — Entry Point

```python
# 1. Structured JSON logging (custom formatter)
class _JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"ts": ..., "lvl": record.levelname, "msg": record.getMessage()})

# 2. Security headers + request logging trên Chainlit's FastAPI server
@_server.middleware("http")
async def _http_middleware(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    ...

# 3. Health probe
@_server.get("/health")
def health():
    return {"status": "ok", "version": ..., "uptime_seconds": ..., ...}

# 4. SIGTERM handler
signal.signal(signal.SIGTERM, _handle_sigterm)

# 5. Password auth (optional, controlled by AUTH_ENABLED env var)
if settings.auth_enabled:
    @cl.password_auth_callback
    def auth_callback(username, password):
        ...

# 6. Per-message: rate limit → cost guard → route
@cl.on_message
async def on_message(message):
    check_rate_limit()   # 10 msg/min sliding window
    check_budget()       # $5/day cost guard
    await route(message) # intent detection → handler
```

#### `Dockerfile` — Multi-stage Production Build

```dockerfile
# Stage 1: Builder — install deps
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime — slim final image
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
RUN chmod +x start.sh

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8000 HOST=0.0.0.0

# Non-root user
RUN useradd --system --create-home --uid 1001 appuser \
    && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

CMD ["./start.sh"]
```

#### `start.sh` — Chainlit entrypoint

```bash
PORT=${PORT:-8000}
export CHAINLIT_PORT=${PORT}
exec chainlit run app.py --host "${HOST}" --port "${PORT}" --headless
```

Railway inject `PORT` tự động. `start.sh` đảm bảo Chainlit lắng nghe đúng port đó.

### 7.3 Kết Quả Production Readiness

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
  ✅ railway.toml + render.yaml

🔒 Security
  ✅ .env in .gitignore
  ✅ No hardcoded secrets
  ✅ Non-root user (appuser)
  ✅ Security headers middleware

🌐 Operations
  ✅ /health liveness probe (Railway dùng endpoint này)
  ✅ Graceful shutdown (SIGTERM handler)
  ✅ Structured JSON logging

🛡️ Rate Limiting & Cost
  ✅ Sliding-window rate limiter (10 msg/user/min)
  ✅ Daily budget guard ($5 USD/ngày)

=======================================================
```

### 7.4 Chạy và Test Local

```bash
# 1. Setup
cd day12_HanQuangHieu_2A202600056
cp .env.example .env
# Edit .env: đặt OPENAI_API_KEY=sk-your-key

# 2. Start
docker compose up

# 3. Open browser
# http://localhost:8000

# 4. Health check
curl http://localhost:8000/health
# {"status":"ok"}

# 5. Dùng chat UI — nhắn tin thử:
# "Giá đặt xe từ Hà Nội đi Hội An?"
# "Tôi muốn đăng ký làm tài xế"
```

---

## 8. Kết Luận

### 8.1 Tổng Kết Những Gì Đã Học

| Concept | Hiểu | Implement |
|---------|------|-----------|
| Dev/Prod gap & 12-Factor | ✅ | ✅ |
| Environment variables & Config | ✅ | ✅ |
| Structured JSON logging | ✅ | ✅ |
| Health check & Readiness probe | ✅ | ✅ |
| Graceful shutdown | ✅ | ✅ |
| Docker multi-stage build | ✅ | ✅ |
| Docker Compose orchestration | ✅ | ✅ |
| Cloud deployment (Railway/Render) | ✅ | ✅ (live at Railway URL) |
| API Key authentication | ✅ | ✅ |
| JWT authentication | ✅ | ✅ |
| Rate limiting (Sliding Window) | ✅ | ✅ |
| Cost guard | ✅ | ✅ |
| Stateless design với Redis | ✅ | ✅ |
| Load balancing với Nginx | ✅ | ✅ |

### 8.2 Key Takeaways

1. **Security is layered** — Không có silver bullet. API key + rate limit + cost guard cùng nhau tạo phòng thủ nhiều lớp.

2. **Stateless is key to scaling** — Bất kỳ state nào trong memory instance đều là bottleneck khi scale. Redis là giải pháp phổ biến nhất cho web apps.

3. **Health checks are not optional** — Không có health checks = platform không biết khi nào restart. Luôn có `/health` và `/ready`.

4. **Config từ environment** — Không bao giờ hardcode secret. Không bao giờ. `os.getenv()` là cách duy nhất trong production.

5. **Small Docker images matter** — Image nhỏ = deploy nhanh hơn, pull nhanh hơn, ít attack surface hơn. Multi-stage build là best practice.

6. **Graceful shutdown prevents data loss** — SIGTERM không phải SIGKILL. Handle SIGTERM để hoàn thành request đang xử lý.

### 8.3 Next Steps

Sau lab này, các bước tiếp theo có thể tìm hiểu:

1. **Monitoring**: Thêm Prometheus metrics + Grafana dashboard
2. **Distributed tracing**: OpenTelemetry để trace request xuyên services
3. **CI/CD**: GitHub Actions → auto test + build + deploy khi push
4. **Kubernetes**: Container orchestration cho large-scale deployments
5. **Secret management**: HashiCorp Vault hoặc AWS Secrets Manager
6. **Database migrations**: Alembic cho PostgreSQL với zero-downtime deploy

---

*Báo cáo được tạo bởi Hàn Quang Hiếu — Mã học viên 2A202600056 — 17/04/2026*
