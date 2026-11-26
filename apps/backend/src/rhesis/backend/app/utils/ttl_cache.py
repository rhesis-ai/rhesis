"""A small per-process cache with a time-to-live, for lookups that rarely change.

Used where a hot path reloaded the same rows for every item it processed, such as
trace evaluation reading a project's metrics and judge model once per trace. A value
is at most ``ttl`` seconds stale; callers state what that staleness means for them.

Keys must carry the tenant (organization, project), so a value never serves another
tenant. Values are shared between the threads of a process: store immutable data or
objects already shared that way (models, plain configs), never ORM rows or sessions.
"""

import threading
import time
from typing import Any, Callable, Dict, Hashable, Tuple

_registry: list["TTLCache"] = []


class TTLCache:
    def __init__(self, ttl: Callable[[], float]):
        """*ttl* is read on every store, so tests and settings can change it."""
        self._ttl = ttl
        self._lock = threading.Lock()
        self._values: Dict[Hashable, Tuple[float, Any]] = {}
        self._loading: Dict[Hashable, threading.Lock] = {}
        _registry.append(self)

    def _fresh(self, key: Hashable) -> Tuple[bool, Any]:
        with self._lock:
            hit = self._values.get(key)
        if hit is not None and hit[0] > time.monotonic():
            return True, hit[1]
        return False, None

    def get_or_load(self, key: Hashable, load: Callable[[], Any]) -> Any:
        """The cached value for *key*, or ``load()`` stored for the TTL.

        One thread loads a key while the others asking for it wait and take its
        result: when an entry expires, every worker thread misses at once, and each
        loading it would repeat the same queries, each inside its own transaction.
        An exception from ``load`` is not cached; the next caller loads again.
        """
        found, value = self._fresh(key)
        if found:
            return value
        with self._lock:
            key_lock = self._loading.setdefault(key, threading.Lock())
        with key_lock:
            found, value = self._fresh(key)
            if found:
                return value
            try:
                value = load()
                self._store(key, value)
                return value
            finally:
                # Dropped once loaded: a thread already waiting holds this lock object
                # and finds the stored value; a later one finds it without locking.
                with self._lock:
                    self._loading.pop(key, None)

    def _store(self, key: Hashable, value: Any) -> None:
        ttl = self._ttl()
        if ttl <= 0:
            return
        now = time.monotonic()
        with self._lock:
            # Expired entries go on each store, so the cache holds only live keys.
            for stale in [k for k, (expires, _) in self._values.items() if expires <= now]:
                del self._values[stale]
            self._values[key] = (now + ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


def clear_all() -> None:
    """Empty every cache in the process (tests)."""
    for cache in _registry:
        cache.clear()
