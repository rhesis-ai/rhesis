"""Simple in-process cache for resolved parameters.

- Immutable version pins are cached forever (the content never changes).
- Environment and experiment_id lookups use a TTL (default 60 s).

The cache is intentionally unsophisticated — a plain dict with
timestamps. A more elaborate solution (LRU, async refresh) can replace
this later without changing the public API.
"""

from __future__ import annotations

import threading
import time
from typing import Any

_DEFAULT_TTL_SECONDS = 60.0


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float | None) -> None:
        self.value = value
        self.expires_at = None if ttl is None else time.monotonic() + ttl


class ParameterCache:
    def __init__(self, ttl: float = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._store: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def _key(
        self,
        project: str,
        *,
        environment: str | None = None,
        experiment_id: str | None = None,
        version: str | None = None,
    ) -> str:
        return f"{project}|{environment}|{experiment_id}|{version}"

    def get(
        self,
        project: str,
        *,
        environment: str | None = None,
        experiment_id: str | None = None,
        version: str | None = None,
    ) -> Any | None:
        key = self._key(
            project,
            environment=environment,
            experiment_id=experiment_id,
            version=version,
        )
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at is not None and time.monotonic() > entry.expires_at:
                del self._store[key]
                return None
            return entry.value

    def put(
        self,
        project: str,
        value: Any,
        *,
        environment: str | None = None,
        experiment_id: str | None = None,
        version: str | None = None,
    ) -> None:
        key = self._key(
            project,
            environment=environment,
            experiment_id=experiment_id,
            version=version,
        )
        # Immutable version pins never expire.
        ttl = None if version is not None else self._ttl
        with self._lock:
            self._store[key] = _CacheEntry(value, ttl)

    def invalidate(self, project: str | None = None) -> None:
        """Drop cached entries.  ``None`` clears everything."""
        with self._lock:
            if project is None:
                self._store.clear()
            else:
                prefix = f"{project}|"
                self._store = {k: v for k, v in self._store.items() if not k.startswith(prefix)}
