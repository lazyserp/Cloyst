# Cloyst Security Threat Model (STRIDE)

This document provides a systematic STRIDE threat analysis for Cloyst in air-gapped and regulated deployments.

## System Overview
- **Data Plane**: FastAPI + Uvicorn + in-memory routing/cache. Listens on `:8000`. Authenticates via Bearer token or `x-api-key`.
- **Control Plane**: FastAPI + Uvicorn + admin console. Listens on `:8001`. Authenticates via Bearer admin token.
- **Node Agents**: Telemetry daemon reporting GPU and hardware specs to control plane.
- **Storage Layer**: PostgreSQL/SQLite + local model weight directory.

---

## STRIDE Threat Matrix

| Threat Category | Potential Attack Vector | Cloyst Architectural Mitigation | Verification Test |
|---|---|---|---|
| **Spoofing** | Adversary presents forged API key or spoofed node registration | HMAC-SHA256 key hashing with system pepper (`CLOYST_KEY_PEPPER`), constant-time token comparison (`secrets.compare_digest`), high-entropy tokens | `test_hmac_pepper_and_caching`, `test_verify_admin_token` |
| **Tampering** | Malicious actor modifies database audit records or model files | Cryptographic hash-chained audit logs (`prev_record_hash`), SHA-256 model directory provenance hashes, signed bundle archives | `test_immutable_audit_hash_chain`, `test_bundle_detects_file_tampering` |
| **Repudiation** | Client denies issuing inference request or prompts | Immutable audit trail recording timestamps, token counts, model IDs, latency, and cryptographic parent linkages | `test_immutable_audit_hash_chain` |
| **Information Disclosure** | Leakage of API keys, Bearer tokens, or PII in logs or responses | Structured JSON logger with regex-based automatic secret redaction, offline PII scanner/redactor, metadata-only logging by default | `test_logging_redacts_sensitive_keys`, `test_offline_guardrails_redact_and_block` |
| **Denial of Service** | Upstream node outage, 429 flood, or memory exhaustion | Token-bucket rate limiting per key, circuit breakers with auto-cooldown, priority failover routing, bounded memory caches | `test_router_strategies_and_circuit_breaker`, `test_rate_limiter_isolated_keys` |
| **Elevation of Privilege** | Tenant IDOR or developer escalating to cluster administrator | Role-based access control (admin, operator, inference), project tenant scoping on keys and cached responses | `test_exact_match_cache_hit_and_isolation` |
