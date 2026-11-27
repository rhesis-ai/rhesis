"""Which traces still have spans queued for storage.

Spans are accepted, queued, and stored later by a worker. An evaluation that reads a trace
right after the endpoint answered would otherwise see only part of it. The intake marks each
queued message against the traces it carries; the ingest job clears the mark once the spans
are stored (or can never be), and a reader waits, up to a limit, for its trace's marks to go.
"""

import logging
import time
from typing import Iterable

from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase

logger = logging.getLogger(__name__)

_PREFIX = "traceingest:v1:pending:"
# A worker lost for good leaves its mark; a reader then waits only up to its own limit.
_TTL_SECONDS = 600
_POLL_SECONDS = 0.25
DEFAULT_WAIT_SECONDS = 15.0


def _key(organization_id: str, project_id: str, trace_id: str) -> str:
    return f"{_PREFIX}{organization_id}:{project_id}:{trace_id}"


class IngestPendingCache(RedisBackedCache):
    """One hash per trace, a field per queued message still to be stored."""

    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.CONVERSATION_LINKING,
            cache_name="trace-ingest-pending",
            ttl=_TTL_SECONDS,
        )

    def has_marks(self, key: str) -> bool:
        # The primary, not a read replica: a mark set a moment ago must be seen.
        if self._redis is not None:
            try:
                return bool(self._redis.exists(key))
            except Exception as exc:
                logger.warning(f"{self._cache_name}: Redis exists failed: {exc}")
        return bool(self._hgetall(key))


_cache = IngestPendingCache()


def _get_cache() -> IngestPendingCache:
    if _cache._initialized:
        _cache._reconnect_if_due()
    else:
        _cache.initialize()
    return _cache


def mark_queued(
    message_id: str, organization_id: str, project_id: str, trace_ids: Iterable[str]
) -> None:
    """Note that ``message_id`` carries spans of ``trace_ids`` not stored yet."""
    cache = _get_cache()
    for trace_id in set(trace_ids):
        cache._hset(_key(organization_id, project_id, trace_id), message_id, "1")


def mark_done(
    message_id: str, organization_id: str, project_id: str, trace_ids: Iterable[str]
) -> None:
    """The spans of ``message_id`` are stored, or never will be."""
    cache = _get_cache()
    for trace_id in set(trace_ids):
        cache._hdel(_key(organization_id, project_id, trace_id), message_id)


def is_pending(organization_id: str, project_id: str, trace_id: str) -> bool:
    return _get_cache().has_marks(_key(organization_id, project_id, trace_id))


def wait_until_stored(
    organization_id: str,
    project_id: str,
    trace_id: str,
    timeout_seconds: float = DEFAULT_WAIT_SECONDS,
) -> bool:
    """Wait until no queued spans of the trace remain. False when the wait ran out."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            if not is_pending(organization_id, project_id, trace_id):
                return True
        except Exception:
            logger.debug("Could not check pending ingest for %s", trace_id, exc_info=True)
            return True
        if time.monotonic() >= deadline:
            logger.warning(
                "Spans of trace %s are still queued after %.0fs; evaluating what is stored",
                trace_id,
                timeout_seconds,
            )
            return False
        time.sleep(_POLL_SECONDS)
