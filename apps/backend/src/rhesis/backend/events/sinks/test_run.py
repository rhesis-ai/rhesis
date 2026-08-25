"""Publishes coalesced ``test_run.progressed`` ticks to ``test_run:{id}``.

Opens NO database session, unlike ``WebSocketSink``. The channel comes
straight from the event's own ``entity_id`` -- ``entity_type="test_run"`` is
set at the call site, no ``celery_task_id`` -> job lookup needed. That is the
whole point of this sink: a run emits far too many of these ticks (one per
test phase transition) for a DB round-trip per event to be affordable, so
ticks are coalesced in-process and flushed at most once per window.
"""

import logging
import threading
from typing import Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    EventType,
    WebSocketMessage,
)
from rhesis.backend.app.services.websocket.publisher import publish_event
from rhesis.backend.events.types import PlatformEvent, TestRunProgressed

logger = logging.getLogger(__name__)

COALESCE_WINDOW_S = 0.5


class TestRunSink:
    name = "test_run"
    critical = False

    def __init__(self) -> None:
        self._pending: Dict[str, TestRunProgressed] = {}
        self._lock = threading.Lock()
        self._timers: Dict[str, threading.Timer] = {}

    def handles(self, event: PlatformEvent) -> bool:
        return isinstance(event, TestRunProgressed)

    def deliver(self, event: PlatformEvent, db: Optional[Session]) -> None:
        if not isinstance(event, TestRunProgressed):
            return
        entity_id = str(event.entity_id) if event.entity_id else None
        if not entity_id:
            return

        with self._lock:
            self._pending[entity_id] = event
            if entity_id not in self._timers:
                timer = threading.Timer(COALESCE_WINDOW_S, self._flush, args=[entity_id])
                timer.daemon = True
                timer.start()
                self._timers[entity_id] = timer

    def _flush(self, entity_id: str) -> None:
        with self._lock:
            event = self._pending.pop(entity_id, None)
            self._timers.pop(entity_id, None)
        if event is None:
            return
        try:
            channel = ChannelTarget(channel=f"test_run:{entity_id}")
            publish_event(
                WebSocketMessage(
                    type=EventType.TEST_RUN_PROGRESSED,
                    channel=channel.channel,
                    payload={
                        "completed": event.completed,
                        "total": event.total,
                        "generating_test_ids": [str(tid) for tid in event.generating_test_ids],
                        "evaluating_test_ids": [str(tid) for tid in event.evaluating_test_ids],
                    },
                ),
                channel,
            )
        except Exception:
            logger.debug("TestRunSink: publish failed for %s", entity_id, exc_info=True)
