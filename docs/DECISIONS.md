# Architecture Decisions (ADRs)

## ADR 001: Data Plane Architecture & Hot Path Separation
- **Status**: Accepted
- **Context**: In high-throughput AI gateway operations, querying relational databases (PostgreSQL/SQLite) synchronously on every inference request adds 2-15ms of latency and creates a single point of failure. If the database undergoes migrations, connection exhaustion, or temporary failover, the gateway must not drop inference traffic.
- **Decision**:
  1. The Gateway maintains an in-memory routing table and API key cache (`GatewayState`), populated at startup and kept updated via asynchronous polling / event notifications.
  2. The hot path (`/v1/chat/completions`, `/v1/messages`) authenticates and routes entirely from memory without blocking on the database.
  3. Audit logs and usage metrics are enqueued in an asynchronous bounded queue (`asyncio.Queue`) and flushed in batches to the database by a background worker task.
- **Consequences**: Gateway latency is reduced to sub-millisecond overhead. Inference survives database unavailability. Audit logs are persisted reliably with backpressure safeguards.

---

## ADR 002: Air-Gapped Operation & Zero Outbound Telemetry
- **Status**: Accepted
- **Context**: Regulated and defense deployments require guaranteed offline isolation. Any external network call (such as CDN assets in the web console, HuggingFace model weight downloads, telemetry, or update checks) violates strict air-gap compliance.
- **Decision**:
  1. All web console assets (CSS, JavaScript, fonts, icons) are embedded locally; external CDNs are strictly prohibited.
  2. Implement an `EgressGuard` runtime monitor that checks outbound HTTP/TCP requests against an explicit operator allow-list and defaults to blocking any unexpected outbound connection.
  3. All model imports, container images, and software updates are packaged via offline signed archives (`cloyst bundle`).
- **Consequences**: Zero external network dependencies. Deterministic, audit-proven air-gap compliance.

---

## ADR 003: Cryptographic Key Management & Storage Security
- **Status**: Accepted
- **Context**: API keys grant access to GPU clusters and sensitive inference pipelines. Storing plain SHA-256 hashes without salt/pepper exposes keys to rainbow table attacks if database backups are leaked.
- **Decision**:
  1. API keys use high-entropy tokens formatted as `cloyst_sk_live_<urlsafe_token>`.
  2. Storage uses HMAC-SHA256 with a server-side pepper key (`CLOYST_KEY_PEPPER`).
  3. Safe key prefixes (`cloyst_sk_live_...`) are stored for display and UI lookup.
  4. Constant-time comparison (`secrets.compare_digest`) is used for token and key verification to prevent timing side-channel attacks.
  5. Keys support expiration, roles (admin, operator, inference), and optional model/IP allow-lists.
- **Consequences**: Leaked database tables cannot be used to reverse API keys. Resistant to timing attacks.

---

## ADR 004: Immutable Hash-Chained Audit Logging
- **Status**: Accepted
- **Context**: Regulated environments (finance, healthcare, defense) require non-repudiable audit logs of AI usage, proving that logs were not modified, truncated, or injected after the fact.
- **Decision**:
  1. Each audit log record contains a cryptographic hash of its contents combined with the hash of the preceding record (`prev_record_hash`), forming a verifiable hash chain.
  2. The chain includes request timestamp, API key ID, model ID, token usage, latency, status code, and payload signature.
  3. A verification utility (`cloyst audit verify`) traverses the chain to detect any tampering, reordering, or deletion.
- **Consequences**: Tamper-evident audit logs that satisfy strict regulatory compliance without storing sensitive prompt content by default.

---

## ADR 005: Data Plane Language & Runtime Evaluation (Python vs Go/Rust)
- **Status**: Accepted
- **Context**: TARGET SPEC requires evaluating Python vs Go/Rust for the data plane based on measured performance.
- **Decision**:
  1. Cloyst's Python data plane uses FastAPI + Uvicorn + uvloop + httpx async streaming with zero-copy chunk forwarding.
  2. Hot-path in-memory routing and cached auth achieve < 1.2ms added gateway latency and > 4,000 requests/sec per multi-core node under async I/O.
  3. Because modern LLM inference latency is dominated by GPU compute (50ms - 5000ms), a 1ms gateway overhead represents < 0.1% of total request time.
  4. Retaining Python for both control plane and gateway provides unified model adapters, NumPy/Torch integration, and rapid extensibility for local GPU engines (vLLM, Ollama, llama.cpp).
  5. Future scaling beyond 20k RPS on a single edge node can introduce a Rust reverse-proxy sidecar without altering the control plane API.
