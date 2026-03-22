"""Redis-backed cache base class with in-memory fallback.

Encapsulates the common Redis infrastructure shared by all sync
Redis-backed caches (conversation linking, trace metrics debounce, etc.).
Async caches (e.g. GarakProbeCache) do not extend this class but should
still reference RedisDatabase for DB number allocation.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


class RedisBackedCache:
    """Sync Redis cache with automatic in-memory fallback.

    Subclasses define their own key prefixes and public API methods.
    This base handles connection lifecycle and primitive operations.
    """

    def __init__(self, redis_db: int, cache_name: str, ttl: int = 120) -> None:
        self._redis_db = redis_db
        self._cache_name = cache_name
        self._ttl = ttl
        self._redis: Optional[Any] = None
        self._initialized = False
        self._memory: Dict[str, Any] = {}
        self._memory_timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()

    @property
    def _using_redis(self) -> bool:
        return self._redis is not None

    def _build_redis_url(self) -> str:
        redis_url = os.getenv("BROKER_URL", "redis://localhost:6379/0")
        parsed = urlparse(redis_url)
        return urlunparse(parsed._replace(path=f"/{self._redis_db}"))

    def initialize(self) -> None:
        """Try to connect to Redis. Falls back to in-memory if unavailable."""
        if self._initialized:
            return

        try:
            import redis as redis_pkg

            cache_url = self._build_redis_url()
            self._redis = redis_pkg.Redis.from_url(
                cache_url,
                decode_responses=True,
                encoding="utf-8",
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self._redis.ping()
            self._initialized = True
            logger.info(
                f"{self._cache_name} cache: Redis connection established (db {self._redis_db})"
            )
        except Exception as e:
            logger.debug(
                f"{self._cache_name} cache: Redis not available "
                f"({type(e).__name__}: {e}). "
                "Operating in memory-only mode."
            )
            if self._redis is not None:
                try:
                    self._redis.close()
                except Exception:
                    pass
                self._redis = None
            self._initialized = True

    def close(self) -> None:
        """Close the Redis connection if open."""
        if self._redis is not None:
            try:
                self._redis.close()
            except Exception:
                pass
            self._redis = None

    def _evict_stale(self) -> None:
        """Remove entries older than TTL from in-memory cache (caller holds lock)."""
        cutoff = time.monotonic() - self._ttl
        stale = [k for k, ts in self._memory_timestamps.items() if ts < cutoff]
        for key in stale:
            self._memory.pop(key, None)
            self._memory_timestamps.pop(key, None)

    def _set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """Set a key-value pair in Redis or in-memory fallback."""
        ex = ttl if ttl is not None else self._ttl
        if self._using_redis:
            try:
                self._redis.set(key, value, ex=ex)
                return
            except Exception as exc:
                logger.warning(
                    f"{self._cache_name}: Redis write failed for _set, "
                    f"falling back to memory: {exc}"
                )

        with self._lock:
            self._memory[key] = value
            self._memory_timestamps[key] = time.monotonic()
            self._evict_stale()

    def _get(self, key: str) -> Optional[str]:
        """Get a value by key from Redis or in-memory fallback."""
        if self._using_redis:
            try:
                return self._redis.get(key)
            except Exception as exc:
                logger.warning(
                    f"{self._cache_name}: Redis read failed for _get, falling back to memory: {exc}"
                )

        with self._lock:
            self._evict_stale()
            return self._memory.get(key)

    def _delete(self, *keys: str) -> None:
        """Delete one or more keys from Redis or in-memory fallback."""
        if not keys:
            return

        if self._using_redis:
            try:
                self._redis.delete(*keys)
                return
            except Exception as exc:
                logger.warning(
                    f"{self._cache_name}: Redis delete failed, falling back to memory: {exc}"
                )

        with self._lock:
            for key in keys:
                self._memory.pop(key, None)
                self._memory_timestamps.pop(key, None)

    def _mget(self, keys: List[str]) -> List[Optional[str]]:
        """Get multiple values at once from Redis or in-memory fallback."""
        if not keys:
            return []

        if self._using_redis:
            try:
                return self._redis.mget(keys)
            except Exception as exc:
                logger.warning(
                    f"{self._cache_name}: Redis mget failed, falling back to memory: {exc}"
                )

        with self._lock:
            self._evict_stale()
            return [self._memory.get(k) for k in keys]

    def _pipeline_set(self, items: Dict[str, str], ttl: Optional[int] = None) -> None:
        """Set multiple key-value pairs atomically via Redis pipeline."""
        if not items:
            return

        ex = ttl if ttl is not None else self._ttl
        if self._using_redis:
            try:
                pipe = self._redis.pipeline()
                for key, value in items.items():
                    pipe.set(key, value, ex=ex)
                pipe.execute()
                return
            except Exception as exc:
                logger.warning(
                    f"{self._cache_name}: Redis pipeline_set failed, falling back to memory: {exc}"
                )

        with self._lock:
            now = time.monotonic()
            for key, value in items.items():
                self._memory[key] = value
                self._memory_timestamps[key] = now
            self._evict_stale()

    def _getdel(self, key: str) -> Optional[str]:
        """Get and delete a key atomically."""
        if self._using_redis:
            try:
                pipe = self._redis.pipeline()
                pipe.get(key)
                pipe.delete(key)
                results = pipe.execute()
                return results[0]
            except Exception as exc:
                logger.warning(
                    f"{self._cache_name}: Redis getdel failed, falling back to memory: {exc}"
                )

        with self._lock:
            val = self._memory.pop(key, None)
            self._memory_timestamps.pop(key, None)
            return val
