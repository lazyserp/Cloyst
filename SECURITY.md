# Security Policy

## Supported Versions
Cloyst releases receive critical security patches on the current major release series.

## Reporting a Vulnerability
Cloyst takes security and air-gap integrity seriously. If you discover a vulnerability:
1. Do NOT open a public GitHub issue.
2. Email `security@cloyst.local` or the repository maintainers with detailed reproduction steps.
3. Include impact assessment (confidentiality, integrity, availability).
4. Our team will acknowledge receipt within 24 hours and issue a CVE/patch within 7 business days for critical issues.

## Security Baseline & Hardening
- **Air-Gapped by Default**: No telemetry, no remote CDN assets, no external font loading.
- **Secret Management**: Weak and default secrets ("devkey", "admin", "password", "cloyst-master-secret-2026") are refused at startup in production environments.
- **Cryptographic Keys**: API keys are hashed using HMAC-SHA256 with a unique server pepper and validated using constant-time comparisons.
- **Audit Logging**: Inference events are recorded with cryptographic hash chains to ensure tamper-evidence.
