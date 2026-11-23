# Cloyst Hardening & Air-Gap Deployment Guide

## 1. Air-Gap Isolation
Cloyst is engineered to operate in environments with zero external network connectivity.
- **Egress Guard**: Set `CLOYST_AIR_GAP_MODE=true` to block any outbound socket connections outside the operator-defined `CLOYST_EGRESS_ALLOWLIST`.
- **Zero Remote Dependencies**: The Web Console UI embeds minified CSS assets locally with no CDN script tags or remote Google Fonts.
- **Model Distribution**: Use `cloyst bundle create` and `cloyst bundle install` to transport verified models across security perimeters via removable media.

## 2. Secrets Management
- In production (`CLOYST_ENV=production`), Cloyst will refuse to start if `CLOYST_ADMIN_TOKEN` is unset or matches known weak defaults.
- Always provide an external high-entropy token:
  ```bash
  export CLOYST_ADMIN_TOKEN=$(openssl rand -hex 32)
  export CLOYST_KEY_PEPPER=$(openssl rand -hex 32)
  ```
- All API keys are stored as HMAC-SHA256 digests. Raw keys are displayed only once upon generation.

## 3. Container Hardening
- Rootless container execution: run as non-root user `uid=1000`.
- Read-only root filesystem with ephemeral `/tmp` volume.
- Network policy: block outbound traffic to public IP ranges at the Kubernetes / Docker bridge layer.
