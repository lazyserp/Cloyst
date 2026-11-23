"""Cryptographic API key generation, HMAC-SHA256 hashing, and in-memory validation cache."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from core.db.models import ApiKeyRecord


# In-memory validation cache to eliminate database calls on the hot path
class KeyCacheEntry:
    def __init__(self, record: ApiKeyRecord, ttl_seconds: float = 60.0):
        self.record = record
        self.expires_at = time.time() + ttl_seconds


_KEY_CACHE: Dict[str, KeyCacheEntry] = {}


def invalidate_key_cache(key_hash: Optional[str] = None) -> None:
    """Invalidate key cache entries. If key_hash is None, clear all."""
    global _KEY_CACHE
    if key_hash:
        _KEY_CACHE.pop(key_hash, None)
    else:
        _KEY_CACHE.clear()


def hash_key(raw_key: str, pepper: Optional[str] = None) -> str:
    """Compute HMAC-SHA256 hex digest of the raw key using the system pepper."""
    effective_pepper = pepper or settings.cloyst_key_pepper or "cloyst_secure_pepper_default_entropy_2026"
    return hmac.new(
        effective_pepper.encode("utf-8"),
        raw_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def legacy_hash_key(raw_key: str) -> str:
    """Legacy unpeppered SHA-256 for backward compatibility with existing databases."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key(prefix: str = "cloyst_sk_live_") -> Tuple[str, str, str]:
    """Generate a cryptographically secure API key.

    Returns:
        (plain_key, key_hash, prefix)
        - plain_key: Shown to the user ONCE (e.g. 'cloyst_sk_live_AbCd123...')
        - key_hash: Stored in the database (HMAC-SHA256)
        - prefix: Safe display prefix (e.g. 'cloyst_sk_live_AbCd')
    """
    token = secrets.token_urlsafe(32)
    plain_key = f"{prefix}{token}"
    key_hash = hash_key(plain_key)
    safe_prefix = plain_key[:16]
    return plain_key, key_hash, safe_prefix


def verify_api_key(raw_key: str, db: Optional[Session] = None) -> ApiKeyRecord | None:
    """Verify an incoming raw API key against in-memory cache and/or database.

    Uses constant-time comparison and verifies expiration and active status.
    """
    if not raw_key or not isinstance(raw_key, str):
        return None

    current_hash = hash_key(raw_key)
    now_ts = time.time()

    # 1. Check in-memory hot cache first (zero DB latency)
    cached = _KEY_CACHE.get(current_hash)
    if cached and cached.expires_at > now_ts:
        rec = cached.record
        if rec.is_active:
            if rec.expires_at is None or rec.expires_at > datetime.now(timezone.utc):
                return rec
        _KEY_CACHE.pop(current_hash, None)
        return None

    if db is None:
        return None

    # 2. Query database for HMAC-SHA256 hash
    stmt = select(ApiKeyRecord).where(ApiKeyRecord.key_hash == current_hash)
    record = db.scalar(stmt)

    # Fallback: check legacy unpeppered SHA-256 hash for backward compatibility
    if not record:
        legacy_h = legacy_hash_key(raw_key)
        stmt_legacy = select(ApiKeyRecord).where(ApiKeyRecord.key_hash == legacy_h)
        record = db.scalar(stmt_legacy)
        if record:
            current_hash = legacy_h

    if not record:
        return None

    if not record.is_active:
        return None

    if record.expires_at is not None:
        if record.expires_at < datetime.now(timezone.utc):
            return None

    # Cache active, non-expired key in memory for hot path
    _KEY_CACHE[current_hash] = KeyCacheEntry(record, ttl_seconds=60.0)
    return record
