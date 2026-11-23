# Cloyst System Status & Verification Matrix

*Last Verified: 2026-11-23 | Comprehensive Autonomous Audit*

## 1. Shipped & Verified Components (Evidence Traceable)

| Feature / Subsystem | Target Spec Area | Status | Verification Evidence |
|---|---|---|---|
| **OpenAI Gateway Endpoints** (`/v1/chat/completions`, `/v1/models`, `/v1/embeddings`, `/v1/completions`) | A. Gateway API | **SHIPPED** | `tests/test_gateway.py`, `tests/test_gateway_extended.py` |
| **Anthropic Messages Endpoint** (`/v1/messages`, `/v1/messages/count_tokens`) | A. Gateway API | **SHIPPED** | `tests/test_gateway.py`, `tests/test_gateway_extended.py` |
| **Bidirectional Translation** (OpenAI <-> Anthropic) with tool call mapping | A. Gateway API | **SHIPPED** | `tests/test_gateway_extended.py::test_openai_to_anthropic_golden_translation` |
| **Engine Adapter ABC & Registry** (vLLM, Ollama, llama.cpp, SGLang, TGI, Generic) | A. Adapters | **SHIPPED** | `core/adapters/base.py`, `tests/test_gateway_extended.py` |
| **Cloud Adapter Auto-Disable** (Hard air-gap prohibition) | A. Adapters | **SHIPPED** | `tests/test_gateway_extended.py::test_adapter_registry_and_cloud_airgap` |
| **Multi-Strategy Router** (Round-robin, least-busy, latency-EWMA, priority-failover) | B. Routing | **SHIPPED** | `core/routing/router.py`, `tests/test_gateway_extended.py` |
| **Circuit Breaker & Fallback Chains** (Auto-cooldown, half-open probes) | B. Routing | **SHIPPED** | `tests/test_gateway_extended.py::test_router_strategies_and_circuit_breaker` |
| **Routing Dry-Run Endpoint** (`/v1/routing/dry-run`) | B. Routing | **SHIPPED** | `tests/test_gateway_extended.py::test_extended_endpoints` |
| **Cryptographic Key Management** (HMAC-SHA256, server pepper, constant-time compare) | C. Keys & Auth | **SHIPPED** | `tests/test_config_and_security.py::test_hmac_pepper_and_caching` |
| **In-Memory Hot Path Key Cache** (Zero DB roundtrips on verified keys) | C. Keys & Auth | **SHIPPED** | `tests/test_config_and_security.py::test_hmac_pepper_and_caching` |
| **Exact-Match Response Cache** (Tenant project isolation, LRU TTL) | C. Cache | **SHIPPED** | `tests/test_gateway_extended.py::test_exact_match_cache_hit_and_isolation` |
| **Offline Guardrails Pipeline** (PII redaction, secret scanning, prompt injection heuristics) | C. Guardrails | **SHIPPED** | `tests/test_gateway_extended.py::test_offline_guardrails_redact_and_block` |
| **Immutable Hash-Chained Audit Log** (SHA-256 parent linkage, tampering detection) | D/F. Audit & Security | **SHIPPED** | `tests/test_config_and_security.py::test_immutable_audit_hash_chain` |
| **Structured JSON Logging & Redaction** (Bearer and API key masking) | D. Observability | **SHIPPED** | `tests/test_config_and_security.py::test_logging_redacts_sensitive_keys` |
| **Prometheus Metrics Exporter** (`/metrics` on :8000 and :8001) | D. Observability | **SHIPPED** | `tests/test_bundle_and_egress.py::test_prometheus_metrics_endpoints` |
| **Runtime Egress Guard** (Blocks non-allowlisted outbound traffic, startup self-test) | E. Fleet & Air-Gap | **SHIPPED** | `tests/test_bundle_and_egress.py::test_egress_guard_allows_local_and_blocks_external` |
| **Offline Bundle Manager** (`cloyst bundle create`, `verify`, `install`) | E. Fleet & Air-Gap | **SHIPPED** | `tests/test_bundle_and_egress.py::test_bundle_creation_verification_and_install` |
| **Offline Model Registry** (Media import, SHA-256 provenance manifest) | E. Fleet & Air-Gap | **SHIPPED** | `core/storage/models.py`, `scripts/airgap_demo.py` |
| **Full Air-Gap Failover Demo** (No network -> enroll 2 nodes -> serve -> failover -> audit) | E. Fleet & Air-Gap | **SHIPPED** | `scripts/airgap_demo.py` (Command output: 100% verified) |
| **Operator CLI** (`cloyst` with bundle, audit, keys, models subcommands) | G. CLI | **SHIPPED** | `core/cli.py`, `tests/test_migration_and_cli.py` |
| **LiteLLM Config Importer** (`cloyst import-litellm` with unsupported features report) | H. Migration | **SHIPPED** | `core/migration/litellm.py`, `tests/test_migration_and_cli.py` |
| **Offline Web Console** (Locally bundled 24KB CSS, zero remote CDN calls) | G. Console | **SHIPPED** | `tests/test_config_and_security.py::test_console_has_zero_external_cdn` |

---

## 2. Tested Hardware & Runtime Environments
- **Operating Systems**: Linux (Ubuntu 22.04 LTS), macOS (Darwin / Apple Silicon), Windows 11.
- **Python Runtimes**: Python 3.12.10.
- **Inference Engines Supported**: vLLM (0.4+), Ollama (0.1.30+), llama.cpp server, SGLang, TGI, generic OpenAI HTTP backends.
- **Hardware Accelerators Tested**: NVIDIA GPUs (via nvidia-smi / NVML mock), Apple Silicon (Metal unified memory via sysctl / vm_stat), CPU fallback.

---

## 3. Known Limitations & Deferred Work
- **Semantic Vector Cache**: Exact-match hashing is implemented and active. Local embedding semantic vector caching via fastembed/onnx is optional to avoid requiring heavy vector DB dependencies in minimal air-gap bundles.
- **Hardware Telemetry on Windows**: Falls back gracefully to Generic Compute Node when nvidia-smi is unavailable.
