"""Cloyst Centralized Typed Configuration.

Validates environment variables, enforces air-gap defaults, and rejects weak secrets.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WEAK_SECRETS = {
    "devkey",
    "cloyst-master-secret-2026",
    "secret",
    "admin",
    "password",
    "123456",
    "changeme",
    "test",
    "default",
}


class Settings(BaseSettings):
    """Cloyst unified system settings."""

    # Environment & Identity
    cloyst_env: str = Field(default="development", alias="CLOYST_ENV")
    cloyst_admin_token: str = Field(
        default_factory=lambda: os.getenv("CLOYST_ADMIN_TOKEN") or "",
        alias="CLOYST_ADMIN_TOKEN",
    )
    cloyst_key_pepper: str = Field(
        default_factory=lambda: os.getenv("CLOYST_KEY_PEPPER") or "",
        alias="CLOYST_KEY_PEPPER",
    )

    # Networking & Air-Gap Mode
    air_gap_mode: bool = Field(default=True, alias="CLOYST_AIR_GAP_MODE")
    egress_allowlist: List[str] = Field(
        default_factory=lambda: ["127.0.0.1", "localhost", "host.docker.internal"],
        alias="CLOYST_EGRESS_ALLOWLIST",
    )

    # Database & Cache
    database_url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL") or "sqlite:///./cloyst.db",
        alias="DATABASE_URL",
    )
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    # Gateway Ports & Limits
    gateway_host: str = Field(default="0.0.0.0", alias="CLOYST_GATEWAY_HOST")
    gateway_port: int = Field(default=8000, alias="CLOYST_GATEWAY_PORT")
    control_plane_host: str = Field(default="0.0.0.0", alias="CLOYST_CONTROL_PLANE_HOST")
    control_plane_port: int = Field(default=8001, alias="CLOYST_CONTROL_PLANE_PORT")

    # Logging & Redaction
    log_level: str = Field(default="INFO", alias="CLOYST_LOG_LEVEL")
    log_format: str = Field(default="json", alias="CLOYST_LOG_FORMAT")
    log_payloads: bool = Field(default=False, alias="CLOYST_LOG_PAYLOADS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cloyst_admin_token", mode="after")
    @classmethod
    def validate_admin_token(cls, v: str, info) -> str:
        env = os.getenv("CLOYST_ENV", "development").lower()
        if not v or v.lower() in WEAK_SECRETS:
            if env == "production":
                raise ValueError(
                    f"Refusing to start in production: CLOYST_ADMIN_TOKEN is missing or uses an insecure/default value ('{v}'). "
                    "Generate a secure token with `openssl rand -hex 32`."
                )
            # In development/test mode, auto-generate a secure ephemeral token if weak
            generated = secrets.token_urlsafe(32)
            return generated
        if len(v) < 12 and env == "production":
            raise ValueError("CLOYST_ADMIN_TOKEN must be at least 12 characters long in production.")
        return v

    @field_validator("cloyst_key_pepper", mode="after")
    @classmethod
    def validate_key_pepper(cls, v: str, info) -> str:
        if not v:
            # Deterministic local fallback pepper for test/dev if not set
            return os.getenv("CLOYST_PEPPER_FALLBACK", "cloyst_secure_pepper_default_entropy_2026")
        return v


# Global singleton instance
settings = Settings()

