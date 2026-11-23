"""Cloyst Structured JSON Logging with Secret Redaction."""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict

# Regex patterns for redacting sensitive secrets
SECRET_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"cloyst_sk_[A-Za-z0-9_\-]{8,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{14,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
    (re.compile(r"(api[_\-]?key[\"\']?\s*[:=]\s*[\"\'])[A-Za-z0-9_\-]{8,}([\"\'])", re.IGNORECASE), r"\1[REDACTED]\2"),
    (re.compile(r"(password[\"\']?\s*[:=]\s*[\"\'])[^\"\']{4,}([\"\'])", re.IGNORECASE), r"\1[REDACTED]\2"),
    (re.compile(r"(secret[\"\']?\s*[:=]\s*[\"\'])[^\"\']{4,}([\"\'])", re.IGNORECASE), r"\1[REDACTED]\2"),
]


def redact_secrets(text: str) -> str:
    """Scan and redact known secret patterns from log messages."""
    if not isinstance(text, str):
        text = str(text)

    for pattern, repl in SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


class JsonFormatter(logging.Formatter):
    """Format log records as single-line structured JSON with redacting filter."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        redacted_msg = redact_secrets(message)

        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redacted_msg,
        }

        # Include request ID or trace ID if present on the record
        if hasattr(record, "request_id"):
            log_data["request_id"] = getattr(record, "request_id")
        if hasattr(record, "model_id"):
            log_data["model_id"] = getattr(record, "model_id")

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO", format_type: str = "json") -> logging.Logger:
    """Configure Cloyst root logger."""
    root_logger = logging.getLogger("cloyst")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if format_type.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
        )

    root_logger.addHandler(handler)
    return root_logger


logger = setup_logging()
