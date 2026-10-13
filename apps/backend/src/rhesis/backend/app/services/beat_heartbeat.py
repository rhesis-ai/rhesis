"""Whether Celery beat is running, as the API can see it.

Each heartbeat (``jobs/heartbeat.py``, every 5 minutes) sets a Redis key that
expires a little after two missed heartbeats. While the key exists, beat, the
broker and a worker were all up recently; scheduled work such as the audit log
purge is running.

Redis trouble never fails the heartbeat or a reader: recording is skipped, and
reading answers None ("unknown"). No in-memory fallback, which would only
know about its own process. A failed connect is retried on the next call.
"""

import logging
from typing import Optional

from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 300
# Two missed heartbeats, plus a minute for queueing.
TTL_SECONDS = 2 * HEARTBEAT_INTERVAL_SECONDS + 60
_KEY = "beat_heartbeat:v1:last"


class BeatSignal(RedisBackedCache):
    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.BEAT_HEARTBEAT, cache_name="beat-heartbeat", ttl=TTL_SECONDS
        )

    def _client(self):
        if self._redis is None:
            self._initialized = False
            try:
                self.initialize()
            except Exception as exc:
                logger.warning(f"{self._cache_name}: Redis unavailable: {exc}")
        return self._redis

    def record(self, ran_at: str) -> None:
        client = self._client()
        if client is None:
            return
        try:
            client.set(_KEY, ran_at, ex=self._ttl)
        except Exception as exc:
            logger.warning(f"{self._cache_name}: could not record the heartbeat: {exc}")

    def running(self) -> Optional[bool]:
        """True while a recent heartbeat exists, False when none does, None if unknown."""
        client = self._client()
        if client is None:
            return None
        try:
            return bool(client.exists(_KEY))
        except Exception as exc:
            logger.warning(f"{self._cache_name}: could not read the heartbeat: {exc}")
            return None


beat_signal = BeatSignal()
