# Cloyst

**Self-Hosted AI Inference Control Plane & Air-Gapped API Gateway**

Cloyst is a private AI inference control plane and API gateway engineered for regulated, on-premises, and air-gapped environments. It turns fragmented GPU hardware (NVIDIA servers, Linux workstations, Apple Silicon Macs) into a resilient, observable, multi-tenant inference fleet with zero outbound network calls by default.

---

## Why Cloyst instead of LiteLLM?

| Evaluation Dimension | Cloyst | LiteLLM Proxy |
|---|---|---|
| **Air-Gap Architecture** | **100% Zero-Egress by Default**: Embedded offline console (no CDNs, no Google Fonts), runtime Egress Guard, and cloud adapter kill-switch. | Cloud-first; requires extensive manual configuration and environment toggles to silence telemetry and external calls. |
| **Data Plane Separation** | **Hot path never blocks on the database**: In-memory routing table, cached HMAC key validation, and non-blocking asynchronous audit queuing. | Hot path queries relational database on per-request authentication and quota checks. |
| **Audit Log Integrity** | **Cryptographic SHA-256 Hash Chaining**: Every inference event is cryptographically linked to its parent (`prev_record_hash`), enabling tamper-detection with `cloyst audit verify`. | Plain mutable database rows; no built-in tamper evidence. |
| **Fleet & Mixed Hardware** | **Native Mixed-Fleet Telemetry**: Auto-detects NVIDIA NVML, Apple Silicon Metal unified memory, and Linux memory fallbacks. | Focuses on cloud API aggregation; minimal on-prem physical GPU awareness. |
| **Offline Distribution** | **Signed Offline Archives**: Single-command `cloyst bundle create` and `cloyst install --offline` with SHA-256 manifest and zip-slip protection. | Requires internet connectivity or manual container image pulling. |
| **Safety Guardrails** | **100% Offline Pipeline**: Local PII redaction (SSN, credit cards, emails, phones), secret detection, prompt injection heuristics, and blocklists. | Cloud-dependent guardrail plugins (Lakera, Presidio, etc.). |

---

## Architectural Topology

```text
                        +---------------------------------------+
                        |  Clients (OpenAI SDK / Claude Code)   |
                        +---------------------------------------+
                                            |
                            Authorization: Bearer <key>
                                            v
+-----------------------------------------------------------------------------------+
|                           Cloyst AI Gateway (:8000)                               |
|  - In-Memory HMAC Key Validation (Zero DB latency)                                |
|  - OpenAI (/v1/chat/completions, /v1/embeddings, /v1/completions, /v1/models)    |
|  - Anthropic (/v1/messages, /v1/messages/count_tokens) + Bidirectional Translation|
|  - Multi-Strategy Router (Round-Robin, Least-Busy, Latency-EWMA, Priority Failover)|
|  - Circuit Breakers with Auto-Cooldown & Half-Open Probes                         |
|  - Exact-Match In-Memory Cache (x-cloyst-cache: HIT / MISS)                       |
|  - Offline Guardrails Pipeline (PII Redaction, Secret Masking, Injection Checks)  |
|  - Prometheus Metrics Exporter (/metrics)                                         |
+-----------------------------------------------------------------------------------+
                       |                                       |
                       v                                       v
         +---------------------------+           +---------------------------+
         |   Local vLLM Container    |           |   Local Ollama / Llama.cpp|
         |    (NVIDIA / CUDA GPU)    |           |    (Apple Silicon / Linux)|
         +---------------------------+           +---------------------------+
                       ^                                       ^
                       +-------------------+-------------------+
                                           | Hardware Telemetry & Heartbeat
                                           v
+-----------------------------------------------------------------------------------+
|                        Cloyst Control Plane (:8001)                               |
|  - Completely Offline Web Console UI (Zero CDN / Zero Font Calls)                 |
|  - Fleet Discovery & Live VRAM / Utilization Telemetry                            |
|  - Cryptographic Audit Log Verification (cloyst audit verify)                     |
|  - Multi-Tenant Projects, Teams & Scoped API Key Minting                          |
|  - Offline Model Registry & Provenance Checksums                                  |
+-----------------------------------------------------------------------------------+
                                           |
                                PostgreSQL 16 Storage
```

---

## Feature Matrix (Verified by CI Test Suite)

- [x] **OpenAI Compatible Endpoints**: `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, `/v1/models`
- [x] **Anthropic Compatible Endpoints**: `/v1/messages`, `/v1/messages/count_tokens`
- [x] **Bidirectional Translation**: Golden fixtures verified for OpenAI <-> Anthropic schema translation
- [x] **Streaming**: SSE token streaming with live usage tracking and zero buffer delay
- [x] **Tool Calling**: Multi-tool calling support with argument conversion for Ollama and vLLM
- [x] **Engine Adapters**: vLLM, Ollama, llama.cpp, SGLang, TGI, and generic OpenAI backends
- [x] **Air-Gap Hardening**: Runtime `EgressGuard` blocking non-allowlisted outbound connections
- [x] **Cryptographic Auth**: HMAC-SHA256 key hashing with system pepper and in-memory hot cache
- [x] **Audit Integrity**: Hash-chained immutable audit log with verification utility (`cloyst audit verify`)
- [x] **Routing Strategies**: Round-robin, least-busy, latency-EWMA, priority-failover, and dry-run explanation
- [x] **Resilience**: Circuit breakers, retry with jitter, timeouts, and automatic fallback chains
- [x] **Offline Cache**: In-memory exact-match cache with tenant project isolation (100x speedup)
- [x] **Offline Guardrails**: PII masking (SSN, credit card, phone, email), secret scanning, prompt injection heuristics
- [x] **Observability**: Prometheus `/metrics` exporter with bounded cardinality on gateway and control plane
- [x] **Operator CLI**: `cloyst bundle`, `cloyst audit`, `cloyst keys`, `cloyst models`
- [x] **LiteLLM Migration**: `cloyst import-litellm config.yaml` with unsupported-features report

---

## Quickstart

### 1. Launch Services

```bash
# Clone repository
git clone https://github.com/lazyserp/Cloyst.git
cd Cloyst

# Generate strong secrets
export CLOYST_ADMIN_TOKEN=$(openssl rand -hex 32)
export CLOYST_KEY_PEPPER=$(openssl rand -hex 32)

# Start Gateway & Control Plane
docker compose up -d
```

### 2. Run the Autonomous Air-Gap Demo

Validate the full end-to-end air-gap workflow (dual node enrollment, model import, dual API serving, node crash, and failover) in a zero-network test:

```bash
python scripts/airgap_demo.py
```

### 3. Run Gateway Performance Benchmarks

```bash
python benchmarks/run_benchmark.py
```

Raw results and methodology are published in [benchmarks/REPORT.md](file:///d:/Cloyst/benchmarks/REPORT.md).

### 4. Verify Immutable Audit Log Integrity

```bash
python -m core.cli audit verify
```

---

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](file:///d:/Cloyst/LICENSE) and [NOTICE](file:///d:/Cloyst/NOTICE).
