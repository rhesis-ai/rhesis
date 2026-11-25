"""Admission control for trace ingest: what may enter before any work is done.

Three caps, each answered with a retryable status:

- per API process, requests being read or decoded at once and their bytes in
  memory, compressed and decompressed (503), so a burst cannot exhaust a pod's
  memory or threads; the role the OpenTelemetry Collector's memory limiter plays;
- per organization, bytes per minute across all processes (429), so one tenant
  cannot crowd out the rest;
- the ingest queue's depth (503), so workers that have fallen behind push back
  on exporters instead of letting Redis grow without bound.

The shared checks use Redis and fail open: an outage there should not stop
ingest, and the per-process cap still bounds each pod.
"""

import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Optional
from urllib.parse import urlparse, urlunparse

from rhesis.backend.app.config.settings import TraceIngestSettings, get_redis_settings
from rhesis.backend.app.services.redis_constants import RedisDatabase

logger = logging.getLogger(__name__)

# Routed in celery/config.py; only ingest jobs, so its depth is the ingest backlog.
INGEST_QUEUE = "trace-ingest"

# Kombu's Redis transport keeps a queue as a list under its name, and messages
# sent with a priority in lists named "<queue>\x06\x16<step>" (PRIORITY_STEPS).
_QUEUE_KEYS = (INGEST_QUEUE, *(f"{INGEST_QUEUE}\x06\x16{step}" for step in (3, 6, 9)))

_ORG_KEY = "trace-ingest:v1:bytes:"
_QUEUE_DEPTH_CACHE_SECONDS = 1.0
_REDIS_TIMEOUT_SECONDS = 0.5


@dataclass(frozen=True)
class Rejection:
    status_code: int
    message: str
    retry_after: int


class IngestRejected(Exception):
    def __init__(self, rejection: Rejection) -> None:
        super().__init__(rejection.message)
        self.rejection = rejection


# ---------------------------------------------------------------------------
# Per process
# ---------------------------------------------------------------------------


class InflightSlot:
    """One admitted request's share of the process's in-flight bytes."""

    def __init__(self, limiter: "InflightLimiter", settings: TraceIngestSettings) -> None:
        self._limiter = limiter
        self._settings = settings
        self.bytes = 0

    def add(self, size: int) -> None:
        """Count ``size`` more bytes held by this request (negative to give some back).

        Raises :class:`IngestRejected` (503) when growing past the process's cap.
        """
        if size > 0 and self._limiter.bytes + size > self._settings.max_inflight_bytes:
            raise IngestRejected(
                Rejection(
                    503, "Trace ingest is busy; retry later", self._settings.retry_after_seconds
                )
            )
        self._limiter.bytes += size
        self.bytes += size


class InflightLimiter:
    """Bounds concurrent requests and the bytes they hold in one process.

    A slot is taken before the request is authenticated or its body read, and
    bytes are counted as they arrive and again once decompressed. Only touched
    from the event loop, between awaits, so it needs no lock.
    """

    def __init__(self) -> None:
        self.requests = 0
        self.bytes = 0

    def acquire(self, settings: TraceIngestSettings) -> InflightSlot:
        """Take a slot. Raises :class:`IngestRejected` (503) when all are taken."""
        if self.requests >= settings.max_concurrent_requests:
            raise IngestRejected(
                Rejection(503, "Trace ingest is busy; retry later", settings.retry_after_seconds)
            )
        self.requests += 1
        return InflightSlot(self, settings)

    def release(self, slot: InflightSlot) -> None:
        self.requests -= 1
        self.bytes -= slot.bytes

    @asynccontextmanager
    async def admit(self, settings: TraceIngestSettings) -> AsyncIterator[InflightSlot]:
        slot = self.acquire(settings)
        try:
            yield slot
        finally:
            self.release(slot)


inflight = InflightLimiter()


# ---------------------------------------------------------------------------
# Shared (Redis)
# ---------------------------------------------------------------------------


def _redis_url(db: int) -> str:
    return urlunparse(urlparse(get_redis_settings().broker_url)._replace(path=f"/{db}"))


class _Redis:
    """Lazily built clients with short timeouts; ``None`` while Redis is unreachable."""

    def __init__(self) -> None:
        self._clients: dict[int, object] = {}
        self._retry_at = 0.0

    def get(self, db: int):
        if db in self._clients:
            return self._clients[db]
        if time.monotonic() < self._retry_at:
            return None
        try:
            import redis

            client = redis.Redis.from_url(
                _redis_url(db),
                socket_timeout=_REDIS_TIMEOUT_SECONDS,
                socket_connect_timeout=_REDIS_TIMEOUT_SECONDS,
            )
            client.ping()
        except Exception as exc:
            logger.warning(f"Trace ingest admission: Redis unavailable ({exc}); not enforcing")
            self._retry_at = time.monotonic() + 30
            return None
        self._clients[db] = client
        return client

    def failed(self, db: int) -> None:
        self._clients.pop(db, None)
        self._retry_at = time.monotonic() + 30


_redis = _Redis()


def check_org_rate(organization_id: str, size: int, settings: TraceIngestSettings) -> None:
    """Count ``size`` against the org's bytes for this minute. Raises :class:`IngestRejected`."""
    limit = settings.org_bytes_per_minute
    if not limit:
        return
    client = _redis.get(RedisDatabase.RATE_LIMITS)
    if client is None:
        return
    window = int(time.time() // 60)
    key = f"{_ORG_KEY}{organization_id}:{window}"
    try:
        pipe = client.pipeline()
        pipe.incrby(key, size)
        pipe.expire(key, 120)
        used, _ = pipe.execute()
    except Exception as exc:
        logger.warning(f"Trace ingest rate check failed ({exc}); allowing")
        _redis.failed(RedisDatabase.RATE_LIMITS)
        return
    if used > limit:
        retry_after = max(1, 60 - int(time.time()) % 60)
        raise IngestRejected(
            Rejection(429, "Trace ingest rate limit reached for this organization", retry_after)
        )


class _QueueDepth:
    def __init__(self) -> None:
        self._value: Optional[int] = None
        self._read_at = 0.0

    def get(self) -> Optional[int]:
        now = time.monotonic()
        if now - self._read_at < _QUEUE_DEPTH_CACHE_SECONDS:
            return self._value
        self._read_at = now
        client = _redis.get(RedisDatabase.CELERY_BROKER)
        if client is None:
            self._value = None
            return None
        try:
            pipe = client.pipeline()
            for key in _QUEUE_KEYS:
                pipe.llen(key)
            self._value = sum(int(n) for n in pipe.execute())
        except Exception as exc:
            logger.warning(f"Trace ingest queue depth check failed ({exc}); allowing")
            _redis.failed(RedisDatabase.CELERY_BROKER)
            self._value = None
        return self._value


_queue_depth = _QueueDepth()


def check_queue_depth(settings: TraceIngestSettings) -> None:
    """Raise :class:`IngestRejected` when the ingest queue is too deep."""
    if not settings.max_queue_depth:
        return
    depth = _queue_depth.get()
    if depth is not None and depth >= settings.max_queue_depth:
        raise IngestRejected(
            Rejection(503, "Trace ingest queue is full; retry later", settings.retry_after_seconds)
        )
