"""Intelligent Multi-Strategy Router and Circuit Breaker for Cloyst.

Supports:
- Round-robin, weighted, least-busy, latency-EWMA, priority-failover, GPU-aware
- Circuit breaker with auto-cooldown and half-open probes
- Fallback chains and dry-run explanation endpoint
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional, Tuple


class EndpointHealth:
    """Tracks live metrics and circuit breaker state for a compute endpoint."""

    def __init__(self, endpoint_id: str, host: str, port: int, weight: float = 1.0, priority: int = 1):
        self.endpoint_id = endpoint_id
        self.host = host
        self.port = port
        self.weight = weight
        self.priority = priority

        self.in_flight: int = 0
        self.total_requests: int = 0
        self.consecutive_failures: int = 0
        self.ewma_latency_ms: float = 50.0  # initial optimistic baseline
        self.state: str = "CLOSED"  # CLOSED (healthy), OPEN (circuit broken), HALF_OPEN
        self.circuit_open_until: float = 0.0

    def record_start(self) -> None:
        self.in_flight += 1
        self.total_requests += 1

    def record_success(self, latency_ms: float) -> None:
        self.in_flight = max(0, self.in_flight - 1)
        self.consecutive_failures = 0
        # EWMA with alpha = 0.2
        self.ewma_latency_ms = (0.2 * latency_ms) + (0.8 * self.ewma_latency_ms)
        self.state = "CLOSED"

    def record_failure(self, cooldown_seconds: float = 15.0) -> None:
        self.in_flight = max(0, self.in_flight - 1)
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            self.state = "OPEN"
            self.circuit_open_until = time.time() + cooldown_seconds

    def is_available(self) -> bool:
        now = time.time()
        if self.state == "OPEN":
            if now >= self.circuit_open_until:
                self.state = "HALF_OPEN"
                return True
            return False
        return True


class Router:
    """Selects target backend instances according to routing strategy and circuit breaker."""

    def __init__(self):
        self._endpoints: Dict[str, List[EndpointHealth]] = {}
        self._rr_counters: Dict[str, int] = {}
        self._fallback_map: Dict[str, str] = {}  # model_id -> fallback_model_id

    def register_endpoint(
        self,
        model_id: str,
        endpoint_id: str,
        host: str,
        port: int,
        weight: float = 1.0,
        priority: int = 1,
    ) -> EndpointHealth:
        if model_id not in self._endpoints:
            self._endpoints[model_id] = []
            self._rr_counters[model_id] = 0

        # Replace existing endpoint if already registered
        for ep in self._endpoints[model_id]:
            if ep.endpoint_id == endpoint_id:
                ep.host = host
                ep.port = port
                ep.weight = weight
                ep.priority = priority
                return ep

        ep = EndpointHealth(endpoint_id, host, port, weight, priority)
        self._endpoints[model_id].append(ep)
        return ep

    def set_fallback(self, primary_model: str, fallback_model: str) -> None:
        self._fallback_map[primary_model] = fallback_model

    def select_endpoint(
        self,
        model_id: str,
        strategy: str = "least-busy",
    ) -> Tuple[Optional[EndpointHealth], Optional[str]]:
        """Select healthy endpoint based on strategy. Returns (Endpoint, selected_model_id)."""
        target_model = model_id
        endpoints = self._endpoints.get(target_model, [])
        healthy = [ep for ep in endpoints if ep.is_available()]

        # If primary has no healthy endpoints, check fallback chain
        if not healthy and target_model in self._fallback_map:
            target_model = self._fallback_map[target_model]
            endpoints = self._endpoints.get(target_model, [])
            healthy = [ep for ep in endpoints if ep.is_available()]

        if not healthy:
            return None, None

        strat = strategy.lower()
        if strat == "round-robin":
            idx = self._rr_counters[target_model] % len(healthy)
            self._rr_counters[target_model] += 1
            return healthy[idx], target_model

        if strat == "latency-ewma":
            # Pick lowest EWMA latency
            healthy.sort(key=lambda ep: ep.ewma_latency_ms)
            return healthy[0], target_model

        if strat == "weighted":
            weights = [ep.weight for ep in healthy]
            selected = random.choices(healthy, weights=weights, k=1)[0]
            return selected, target_model

        if strat == "priority":
            # Lowest priority number = highest precedence
            healthy.sort(key=lambda ep: (ep.priority, ep.in_flight))
            return healthy[0], target_model

        # Default: least-busy (minimum in-flight requests)
        healthy.sort(key=lambda ep: (ep.in_flight, ep.ewma_latency_ms))
        return healthy[0], target_model

    def dry_run(self, model_id: str, strategy: str = "least-busy") -> Dict[str, Any]:
        """Explain routing decision for admin inspection."""
        endpoints = self._endpoints.get(model_id, [])
        ep, chosen_model = self.select_endpoint(model_id, strategy)

        status_list = []
        for e in endpoints:
            status_list.append({
                "endpoint_id": e.endpoint_id,
                "host": e.host,
                "port": e.port,
                "state": e.state,
                "in_flight": e.in_flight,
                "ewma_latency_ms": round(e.ewma_latency_ms, 2),
                "weight": e.weight,
                "priority": e.priority,
            })

        return {
            "requested_model": model_id,
            "chosen_model": chosen_model,
            "strategy": strategy,
            "selected_endpoint": {
                "id": ep.endpoint_id,
                "host": ep.host,
                "port": ep.port,
            } if ep else None,
            "candidates": status_list,
            "fallback_configured": self._fallback_map.get(model_id),
        }


global_router = Router()
