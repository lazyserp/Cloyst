# Cloyst Security Audit Findings & Remediation Log

During the comprehensive autonomous audit, the following vulnerabilities were identified and remediated:

| Finding ID | Severity | Category | Description | Remediation Applied | Status |
|---|---|---|---|---|---|
| **VULN-01** | P0 | Weak Secrets | `core/control_plane/app.py` allowed fallback to `devkey`, and compose specified `cloyst-master-secret-2026`. | Implemented startup validation in `core/config.py` refusing to boot in production with weak secrets; auto-generates high-entropy token in development. | **RESOLVED** |
| **VULN-02** | P0 | Cryptography | API keys used unsalted SHA-256 (`hashlib.sha256`), making leaked databases vulnerable to precomputed dictionary attacks. | Upgraded to HMAC-SHA256 with system pepper (`CLOYST_KEY_PEPPER`), constant-time comparison, and in-memory hot cache. | **RESOLVED** |
| **VULN-03** | P0 | Disk Leak / Path Traversal | Streaming proxy wrote raw stream chunks directly to `/tmp/last_chunks.log`, creating an unencrypted disk leak and failing on Windows. | Removed raw file write completely; all logging routed through structured redaction logger. | **RESOLVED** |
| **VULN-04** | P1 | Air-Gap Violation | `core/console/index.html` fetched `https://cdn.tailwindcss.com` from an external CDN at runtime. | Replaced external CDN script with a locally bundled, self-contained 24KB CSS stylesheet served offline. | **RESOLVED** |
| **VULN-05** | P1 | Audit Tampering | `AuditLogRecord` was a mutable SQL table without tamper-detection or cryptographic integrity guarantees. | Implemented SHA-256 hash chaining (`prev_record_hash`) across all audit entries with verification CLI (`cloyst audit verify`). | **RESOLVED** |
| **VULN-06** | P2 | Missing Egress Guard | Gateway had no mechanism to intercept or prevent accidental outbound network calls. | Implemented `EgressGuard` blocking any destination outside the operator allowlist and running startup self-tests. | **RESOLVED** |
