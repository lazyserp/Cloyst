"""Cryptographic immutable hash-chained audit logging for Cloyst."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from core.db.models import AuditLogRecord

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def compute_audit_hash(
    record_id: str,
    api_key_id: Optional[str],
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    status_code: int,
    created_at_iso: str,
    prev_hash: str,
) -> str:
    """Compute deterministic SHA-256 hash chaining this record with the preceding record."""
    canonical_payload = (
        f"{prev_hash}|{record_id}|{api_key_id or 'none'}|{model_id}|"
        f"{prompt_tokens}|{completion_tokens}|{status_code}|{created_at_iso}"
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def record_audit_entry(
    db: Session,
    model_id: str,
    api_key_id: Optional[str] = None,
    project_id: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: float = 0.0,
    status_code: int = 200,
    error_message: Optional[str] = None,
    request_id: Optional[str] = None,
) -> AuditLogRecord:
    """Create and append an immutable hash-chained audit record."""
    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Retrieve preceding record hash to maintain the chain
    stmt = (
        select(AuditLogRecord.record_hash)
        .where(AuditLogRecord.record_hash.isnot(None))
        .order_by(desc(AuditLogRecord.created_at))
        .limit(1)
    )
    prev_hash = db.scalar(stmt) or GENESIS_HASH

    curr_hash = compute_audit_hash(
        record_id=record_id,
        api_key_id=api_key_id,
        model_id=model_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        status_code=status_code,
        created_at_iso=now_iso,
        prev_hash=prev_hash,
    )

    log_record = AuditLogRecord(
        id=record_id,
        api_key_id=api_key_id,
        model_id=model_id,
        project_id=project_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens or (prompt_tokens + completion_tokens),
        latency_ms=round(latency_ms, 2),
        status_code=status_code,
        error_message=error_message,
        request_id=request_id,
        created_at=now,
        prev_record_hash=prev_hash,
        record_hash=curr_hash,
    )

    db.add(log_record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return log_record


def verify_audit_chain(db: Session) -> Tuple[bool, int, Optional[str]]:
    """Traverse and cryptographically verify the integrity of the audit hash chain.

    Returns:
        (is_valid, record_count, error_detail)
    """
    stmt = select(AuditLogRecord).order_by(AuditLogRecord.created_at.asc(), AuditLogRecord.id.asc())
    records = db.scalars(stmt).all()

    if not records:
        return True, 0, None

    expected_prev = GENESIS_HASH
    for idx, rec in enumerate(records):
        # Skip legacy unchained records if created prior to chaining
        if rec.record_hash is None:
            continue

        if rec.prev_record_hash != expected_prev:
            return (
                False,
                idx,
                f"Broken chain linkage at record {rec.id} (index {idx}): expected prev {expected_prev}, found {rec.prev_record_hash}",
            )

        calc_hash = compute_audit_hash(
            record_id=rec.id,
            api_key_id=rec.api_key_id,
            model_id=rec.model_id,
            prompt_tokens=rec.prompt_tokens,
            completion_tokens=rec.completion_tokens,
            status_code=rec.status_code,
            created_at_iso=rec.created_at.isoformat(),
            prev_hash=rec.prev_record_hash,
        )

        if calc_hash != rec.record_hash:
            return (
                False,
                idx,
                f"Tampered record content detected at record {rec.id} (index {idx}): computed hash {calc_hash} != stored {rec.record_hash}",
            )

        expected_prev = rec.record_hash

    return True, len(records), None
