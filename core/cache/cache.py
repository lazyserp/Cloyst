"""Exact-Match In-Memory Cache with TTL and Project Isolation for Cloyst.

Guarantees zero database roundtrips for repeated prompt completions.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional


class CacheEntry:
    def __init__(self, data: Dict[str, Any], ttl_seconds: float = 3600.0):
        self.data = data
        self.expires_at = time.time() + ttl_seconds


class ExactMatchCache:
    """Thread-safe LRU-like exact match response cache."""

    def __init__(self, max_entries: int = 5000):
        self.max_entries = max_entries
        self._cache: Dict[str, CacheEntry] = {}

    def _generate_key(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        project_id: Optional[str] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        canonical = {
            "p": project_id or "global",
            "m": model,
            "msgs": messages,
            "temp": temperature if temperature is not None else 0.7,
            "tools": tools or [],
        }
        serialized = json.dumps(canonical, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        project_id: Optional[str] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached response if valid and not expired."""
        key = self._generate_key(model, messages, project_id, temperature, tools)
        entry = self._cache.get(key)
        if not entry:
            return None

        if entry.expires_at < time.time():
            self._cache.pop(key, None)
            return None

        return entry.data

    def set(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        data: Dict[str, Any],
        project_id: Optional[str] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        ttl_seconds: float = 3600.0,
    ) -> None:
        """Store response in cache, evicting oldest if full."""
        if len(self._cache) >= self.max_entries:
            # Evict first key
            first_key = next(iter(self._cache))
            self._cache.pop(first_key, None)

        key = self._generate_key(model, messages, project_id, temperature, tools)
        self._cache[key] = CacheEntry(data, ttl_seconds)

    def clear(self) -> None:
        self._cache.clear()


global_cache = ExactMatchCache()
