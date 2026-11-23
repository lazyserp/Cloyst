"""Cloyst Runtime Egress Guard.

Enforces air-gap boundaries by intercepting outbound destination requests,
blocking unauthorized external connections, and logging security alerts.
"""
from __future__ import annotations

import logging
import socket
from typing import List, Optional
from urllib.parse import urlparse

from core.config import settings

logger = logging.getLogger("cloyst.egress")


class EgressBlockedError(PermissionError):
    """Raised when an outbound connection to an unauthorized destination is attempted."""
    pass


class EgressGuard:
    """Monitors and enforces outbound network boundaries."""

    def __init__(self, allowlist: Optional[List[str]] = None):
        self.allowlist = set(allowlist or settings.egress_allowlist)
        # Always allow standard local loopback addresses
        self.allowlist.update({"127.0.0.1", "localhost", "0.0.0.0", "host.docker.internal"})

    def is_destination_allowed(self, target: str) -> bool:
        """Check if target host or URL is authorized for egress."""
        if not settings.air_gap_mode:
            return True

        if target.startswith("http://") or target.startswith("https://"):
            parsed = urlparse(target)
            host = parsed.hostname or ""
        elif ":" in target and not target.count(":") > 1:
            host = target.split(":")[0]
        else:
            host = target

        host_lower = host.lower().strip()
        if host_lower in self.allowlist:
            return True

        # Check local hostname resolution
        try:
            if host_lower == socket.gethostname().lower():
                return True
        except Exception:
            pass

        return False

    def assert_destination_allowed(self, target: str) -> None:
        """Raise EgressBlockedError if the target destination violates air-gap policy."""
        if not self.is_destination_allowed(target):
            logger.warning(
                "EGRESS_VIOLATION_BLOCKED: Outbound request to '%s' denied by Air-Gap Egress Guard",
                target,
            )
            raise EgressBlockedError(
                f"Air-Gap Policy Violation: Outbound connection to '{target}' is not in the operator allowlist."
            )

    def run_startup_self_test(self) -> bool:
        """Verify that air-gap mode is active and unauthorized egress is properly blocked."""
        if not settings.air_gap_mode:
            return True

        unauthorized_sample = "https://external-telemetry.example.com/api"
        assert not self.is_destination_allowed(unauthorized_sample), "EgressGuard failed self-test"
        return True


global_egress_guard = EgressGuard()
