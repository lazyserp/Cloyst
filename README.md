# Cloyst

**Self-Hosted AI Inference Control Plane & Intelligent API Gateway**

Cloyst is a lightweight, production-grade private inference platform that turns fragmented GPU hardware (NVIDIA servers, Linux workstations, Apple Silicon Macs) into a resilient, observable, multi-tenant enterprise inference cloud.

---

## ⚡ Key Capabilities

* **Unified AI Gateway (`:8000`)**:
  * Drop-in OpenAI-compatible (`/v1/chat/completions`) and Anthropic-compatible (`/v1/messages`) routing.
  * Real-time SSE streaming telemetry parsing without response buffering or latency penalty.
  * Native tool calling support with automatic argument parsing and local engine fallbacks.
  * Token-bucket rate limiting (per-key token isolation).
* **Control Plane & Fleet Management (`:8001`)**:
  * Node discovery & continuous hardware heartbeat telemetry.
  * Native hardware inspection: NVIDIA GPUs (`nvidia-smi`), Apple Silicon unified memory (macOS `sysctl`/Metal), and Linux memory fallbacks.
  * Automated preflight checks: Docker daemon, CUDA drivers, available VRAM, and storage paths.
* **Engine Orchestration**:
  * Containerized vLLM runner with deterministic memory utilization and quantization flags.
  * Automated local Ollama runtime discovery and dynamic model registration.
* **Enterprise Security & Observability**:
  * Cryptographically hashed API keys (SHA-256) with role-based access control (RBAC) and instant revocation.
  * Multi-tenant project boundaries for team and departmental isolation.
  * Metadata-only audit logging: tracks latency, token counts (prompt & completion), and model IDs without storing or leaking sensitive prompt text.
  * Built-in dark-mode Web Console and interactive AI Playground.

---

## 🏗 Architecture

```text
               +-----------------------------------------+
               |  Clients (SDKs / Web UI / Internal App) |
               +-----------------------------------------+
                                    |
                    API Key Auth & Rate Limiting
                                    v
+-----------------------------------------------------------------------+
|                         Cloyst AI Gateway                             |
|  - OpenAI & Anthropic Compatible Proxy                                |
|  - Dynamic Model Routing & Fallback                                   |
|  - Streaming SSE Token Usage Telemetry & Metadata Audit Logs          |
+-----------------------------------------------------------------------+
                                    |
          +-------------------------+-------------------------+
          |                                                   |
          v                                                   v
+--------------------+                             +--------------------+
|  vLLM Containers   |                             |   Ollama Runtime   |
|  (NVIDIA / CUDA)   |                             |   (Apple / Linux)  |
+--------------------+                             +--------------------+
          ^                                                   ^
          |             Hardware Telemetry & Heartbeat        |
          +-------------------------+-------------------------+
                                    |
+-----------------------------------------------------------------------+
|                      Cloyst Control Plane & Daemon                    |
|  - Fleet Hardware Detection (VRAM, CUDA, Metal Unified Memory)        |
|  - Preflight Health Checks & Lifecycle Management                     |
|  - Multi-Tenant Projects, RBAC Keys & Web Console                     |
+-----------------------------------------------------------------------+
                                    |
                         PostgreSQL 16 Storage
```

---

## 🚀 Quickstart (Under 60 Seconds)

### 1. Launch with Docker Compose

```bash
git clone https://github.com/lazyserp/Cloyst.git
cd Cloyst
docker compose up -d
```

Services will be running at:
* **AI Gateway:** `http://localhost:8000`
* **Control Plane & Web Console:** `http://localhost:8001/console`
* **PostgreSQL:** `localhost:5432`

### 2. Verify Cluster Health

```bash
python scripts/verify_cluster.py
```

### 3. Send an Inference Request

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cloyst-master-secret-2026" \
  -d '{
    "model": "qwen-2.5-7b-instruct",
    "messages": [
      {"role": "user", "content": "Explain unified memory in Apple Silicon."}
    ]
  }'
```

Or using the standard OpenAI Python SDK:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-cloyst-api-key"
)

response = client.chat.completions.create(
    model="qwen-2.5-7b-instruct",
    messages=[{"role": "user", "content": "Hello Cloyst!"}]
)
print(response.choices[0].message.content)
```

---

## 🛠 Running the Node Agent Daemon

On remote GPU nodes (NVIDIA or Mac):

```bash
python scripts/run_agent.py \
  --control-plane-url http://<control-plane-ip>:8001 \
  --interval 5
```

---

## 🧪 Testing

Run unit and integration test suites:

```bash
pytest tests/
```

---

## 📄 License

Apache 2.0 / MIT
