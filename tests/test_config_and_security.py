import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.config import Settings
from core.db.models import ApiKeyRecord, Base
from core.db.session import init_db
from core.logging import redact_secrets
from core.security.audit import record_audit_entry, verify_audit_chain, GENESIS_HASH
from core.security.keys import generate_api_key, invalidate_key_cache, verify_api_key
from core.gateway.app import app


@pytest.fixture
def isolated_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine=engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(bind=engine)


def test_config_rejects_weak_secrets_in_production(monkeypatch):
    """Verify that Cloyst refuses to start in production with default/weak admin secrets."""
    monkeypatch.setenv("CLOYST_ENV", "production")
    for weak in ["devkey", "cloyst-master-secret-2026", "admin", "password", "123456"]:
        monkeypatch.setenv("CLOYST_ADMIN_TOKEN", weak)
        with pytest.raises(ValueError, match="Refusing to start in production"):
            Settings()


def test_config_generates_strong_secret_in_development(monkeypatch):
    """Verify that missing/weak admin secret auto-generates a strong token in dev."""
    monkeypatch.setenv("CLOYST_ENV", "development")
    monkeypatch.setenv("CLOYST_ADMIN_TOKEN", "devkey")
    s = Settings()
    assert s.cloyst_admin_token != "devkey"
    assert len(s.cloyst_admin_token) >= 32


def test_logging_redacts_sensitive_keys():
    """Verify structured logger strips Bearer tokens, raw API keys, and passwords."""
    raw = (
        "User authenticated with Bearer cloyst_sk_live_supersecret123456789. "
        "Also found sk-ant-api03-abcdefghijklmnop and password='mysecretpassword'."
    )
    redacted = redact_secrets(raw)
    assert "cloyst_sk_live_supersecret123456789" not in redacted
    assert "sk-ant-api03-abcdefghijklmnop" not in redacted
    assert "mysecretpassword" not in redacted
    assert "[REDACTED]" in redacted


def test_hmac_pepper_and_caching(isolated_db):
    """Verify HMAC-SHA256 with pepper, constant-time compare, and in-memory cache."""
    invalidate_key_cache()
    plain, hmac_hash, prefix = generate_api_key()
    assert len(hmac_hash) == 64

    rec = ApiKeyRecord(
        name="test-key",
        key_hash=hmac_hash,
        prefix=prefix,
        is_active=True,
    )
    isolated_db.add(rec)
    isolated_db.commit()

    # 1. First verification queries database and populates cache
    v1 = verify_api_key(plain, isolated_db)
    assert v1 is not None
    assert v1.id == rec.id

    # 2. Second verification succeeds even if db is None (served from in-memory cache)
    v2 = verify_api_key(plain, None)
    assert v2 is not None
    assert v2.id == rec.id

    # 3. Invalidation clears memory cache
    invalidate_key_cache()
    v3 = verify_api_key(plain, None)
    assert v3 is None


def test_immutable_audit_hash_chain(isolated_db):
    """Verify cryptographic hash chaining and tampering detection across audit logs."""
    r1 = record_audit_entry(
        db=isolated_db,
        model_id="model-alpha",
        prompt_tokens=10,
        completion_tokens=20,
        status_code=200,
    )
    assert r1.prev_record_hash == GENESIS_HASH
    assert r1.record_hash is not None

    r2 = record_audit_entry(
        db=isolated_db,
        model_id="model-beta",
        prompt_tokens=15,
        completion_tokens=25,
        status_code=200,
    )
    assert r2.prev_record_hash == r1.record_hash

    # Verification passes on untampered log
    valid, count, err = verify_audit_chain(isolated_db)
    assert valid is True
    assert count == 2
    assert err is None

    # Simulate malicious database tampering on record 1
    r1.prompt_tokens = 9999
    isolated_db.commit()

    # Verification must catch tampering
    valid_tampered, count_t, err_t = verify_audit_chain(isolated_db)
    assert valid_tampered is False
    assert "Tampered record content detected" in err_t


def test_request_id_middleware():
    """Verify gateway attaches x-cloyst-request-id to all responses."""
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        assert "x-cloyst-request-id" in res.headers
        assert res.headers["x-cloyst-request-id"].startswith("cloyst-")


def test_console_has_zero_external_cdn():
    """Verify console HTML has zero external CDN or remote font references (air-gap rule #1)."""
    console_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core", "console", "index.html"))
    with open(console_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert "cdn.tailwindcss.com" not in html
    assert "https://" not in html
    assert "fonts.googleapis.com" not in html
