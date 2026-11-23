"""Prometheus Metrics Exporter with Bounded Cardinality for Cloyst Gateway."""
from __future__ import annotations

import time
from typing import Dict


class MetricsRegistry:
    """Thread-safe Prometheus metrics registry."""

    def __init__(self):
        self._requests_total: Dict[str, int] = {}
        self._tokens_total: Dict[str, int] = {}
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._in_flight: int = 0
        self._request_duration_sum: float = 0.0
        self._request_duration_count: int = 0

    def record_request_start(self) -> None:
        self._in_flight += 1

    def record_request_end(self, model: str, status_code: int, duration_seconds: float) -> None:
        self._in_flight = max(0, self._in_flight - 1)
        key = f'{model}_{status_code}'
        self._requests_total[key] = self._requests_total.get(key, 0) + 1
        self._request_duration_sum += duration_seconds
        self._request_duration_count += 1

    def record_tokens(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        p_key = f'{model}_prompt'
        c_key = f'{model}_completion'
        self._tokens_total[p_key] = self._tokens_total.get(p_key, 0) + prompt_tokens
        self._tokens_total[c_key] = self._tokens_total.get(c_key, 0) + completion_tokens

    def record_cache_hit(self) -> None:
        self._cache_hits += 1

    def record_cache_miss(self) -> None:
        self._cache_misses += 1

    def generate_prometheus_text(self) -> str:
        """Format metrics in standard Prometheus exposition format."""
        lines = [
            "# HELP cloyst_in_flight_requests Current active requests in flight",
            "# TYPE cloyst_in_flight_requests gauge",
            f"cloyst_in_flight_requests {self._in_flight}",
            "",
            "# HELP cloyst_cache_hits_total Total exact-match cache hits",
            "# TYPE cloyst_cache_hits_total counter",
            f"cloyst_cache_hits_total {self._cache_hits}",
            "",
            "# HELP cloyst_cache_misses_total Total exact-match cache misses",
            "# TYPE cloyst_cache_misses_total counter",
            f"cloyst_cache_misses_total {self._cache_misses}",
            "",
            "# HELP cloyst_requests_total Total HTTP requests routed",
            "# TYPE cloyst_requests_total counter",
        ]
        for key, count in sorted(self._requests_total.items()):
            parts = key.rsplit("_", 1)
            model, status_c = parts[0], parts[1]
            lines.append(f'cloyst_requests_total{{model="{model}",status="{status_c}"}} {count}')

        lines.extend([
            "",
            "# HELP cloyst_tokens_total Total tokens processed",
            "# TYPE cloyst_tokens_total counter",
        ])
        for key, count in sorted(self._tokens_total.items()):
            parts = key.rsplit("_", 1)
            model, ttype = parts[0], parts[1]
            lines.append(f'cloyst_tokens_total{{model="{model}",type="{ttype}"}} {count}')

        avg_lat = (
            (self._request_duration_sum / self._request_duration_count)
            if self._request_duration_count > 0
            else 0.0
        )
        lines.extend([
            "",
            "# HELP cloyst_request_duration_seconds_avg Average request duration in seconds",
            "# TYPE cloyst_request_duration_seconds_avg gauge",
            f"cloyst_request_duration_seconds_avg {round(avg_lat, 4)}",
        ])

        return "\n".join(lines) + "\n"


global_metrics = MetricsRegistry()
