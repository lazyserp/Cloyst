# Cloyst Regulatory & Compliance Mapping

*Honest assessment of Cloyst technical controls against regulatory frameworks. Cloyst is self-hosted software; certifications apply to the overall operator deployment.*

| Control ID | Framework | Regulatory Requirement | Cloyst Implementation Status | Evidence / Verification |
|---|---|---|---|---|
| **AC-2 / AC-3** | NIST SP 800-53 | Account & Access Enforcement | **Implemented**: Role-based access control, tenant project isolation, cryptographic API key validation with rotation grace and instant revocation | `tests/test_security_keys.py`, `tests/test_control_plane.py` |
| **AU-2 / AU-9** | NIST SP 800-53 | Audit Events & Protection of Audit Information | **Implemented**: Metadata-only immutable hash-chained audit logging (`prev_record_hash`) preventing undetected modification or log deletion | `core/security/audit.py`, `test_immutable_audit_hash_chain` |
| **SC-7** | NIST SP 800-53 | Boundary Protection | **Implemented**: Runtime Egress Guard blocking non-allowlisted outbound connections; air-gap startup self-test | `core/security/egress.py`, `test_egress_guard_allows_local_and_blocks_external` |
| **CC6.1** | SOC 2 Type II | Logical Access Security | **Implemented**: Constant-time token verification, HMAC-SHA256 key hashing with secret pepper | `core/security/keys.py`, `test_hmac_pepper_and_caching` |
| **CC7.2** | SOC 2 Type II | Monitoring & Anomaly Detection | **Implemented**: Prometheus metrics with bounded cardinality; health and circuit breaker tracking | `core/observability/metrics.py`, `test_prometheus_metrics_endpoints` |
| **164.312(a)** | HIPAA Security Rule | Access Control & Integrity | **Implemented**: Offline PII redaction pipeline (SSN, credit card, phone, email); prompt injection heuristics | `core/policies/guardrails.py`, `test_offline_guardrails_redact_and_block` |
| **A.12.4** | ISO/IEC 27001 | Logging and Monitoring | **Implemented**: Structured JSON logging with automated secret and credential redaction | `core/logging.py`, `test_logging_redacts_sensitive_keys` |
