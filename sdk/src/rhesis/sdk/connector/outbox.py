"""Results on their way to the backend.

A result is kept until the backend acknowledges it, when the backend says it sends
acks. Without acks (older backends) it is kept only while it cannot be sent at all.
"""

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


def run_id_of(message: dict[str, Any]) -> str | None:
    return message.get("test_run_id") or message.get("metric_run_id")


def is_connection_error(error: Exception) -> bool:
    """Whether a failed send is worth retrying on the next connection."""
    if isinstance(error, (ConnectionClosed, OSError)):
        return True
    # WebSocketConnection.send raises this when no socket is up.
    return isinstance(error, RuntimeError) and "not connected" in str(error)


@dataclass
class _Entry:
    message: dict[str, Any]
    queued_at: float
    sent_at: float | None = None
    # Sends since the last reconnect; drives the resend backoff.
    attempts: int = 0


class ResultOutbox:
    """Results not yet confirmed as delivered, keyed by run id, oldest first."""

    # Bounds for a long outage. The backend gives up on a call whose connector stays
    # away for long, so older results are of no use to it.
    MAX_SIZE = 1000
    MAX_AGE_SECONDS = 600.0
    # With acks, an unacknowledged result is sent again after 30s, then 60s, 120s...
    # up to 5 minutes, so a backlog the backend is slow to ack does not snowball.
    RESEND_AFTER_SECONDS = 30.0
    MAX_RESEND_AFTER_SECONDS = 300.0
    # 50 frames per 0.25s is 200/s, well under the backend's default WS_RATE_LIMIT of
    # 500/s per connection, which drops frames over it without telling the sender.
    BATCH_SIZE = 50
    BATCH_PAUSE_SECONDS = 0.25

    def __init__(self, send: Callable[[dict[str, Any]], Awaitable[None]]):
        self._send = send
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = asyncio.Lock()
        # Set from the backend's `registered` reply.
        self.acks = False

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, run_id: str) -> bool:
        return run_id in self._entries

    async def send(self, message: dict[str, Any]) -> bool:
        """Send a result now, keeping it until it is known to be delivered."""
        run_id = run_id_of(message)
        if not run_id:
            await self._send(message)
            return True
        self._add(run_id, message)
        return await self._send_entry(run_id)

    def ack(self, run_id: str | None) -> None:
        if run_id:
            self._entries.pop(run_id, None)

    async def flush(self, resend_all: bool = False) -> None:
        """Send what is due, in paced batches, stopping at the first connection error.

        Due: never sent, sent without an ack for ``RESEND_AFTER_SECONDS``, or, with
        *resend_all* (a new connection just registered), everything.
        """
        async with self._lock:
            self._drop_expired()
            now = time.monotonic()
            if resend_all:
                for entry in self._entries.values():
                    entry.attempts = 0  # earlier sends went to a socket that is gone
                due = list(self._entries)
            else:
                due = [r for r, entry in self._entries.items() if self._is_due(entry, now)]
            if due:
                logger.info(f"Resending {len(due)} result(s) not yet delivered")
            for index, run_id in enumerate(due):
                if index and index % self.BATCH_SIZE == 0:
                    await asyncio.sleep(self.BATCH_PAUSE_SECONDS)
                if run_id not in self._entries:
                    continue  # acked or evicted meanwhile
                if not await self._send_entry(run_id) and run_id in self._entries:
                    logger.warning(f"Resend interrupted; {len(self._entries)} result(s) kept")
                    return

    def _is_due(self, entry: _Entry, now: float) -> bool:
        if entry.sent_at is None:
            return True
        backoff = min(
            self.RESEND_AFTER_SECONDS * 2 ** max(entry.attempts - 1, 0),
            self.MAX_RESEND_AFTER_SECONDS,
        )
        return self.acks and now - entry.sent_at >= backoff

    def _add(self, run_id: str, message: dict[str, Any]) -> None:
        self._drop_expired()
        self._entries.pop(run_id, None)
        while len(self._entries) >= self.MAX_SIZE:
            dropped, _ = self._entries.popitem(last=False)
            logger.warning(
                f"Result outbox is full ({self.MAX_SIZE}); dropped the oldest result "
                f"(run {dropped})"
            )
        self._entries[run_id] = _Entry(message=message, queued_at=time.monotonic())

    async def _send_entry(self, run_id: str) -> bool:
        """Send one kept result. True if the socket took it."""
        entry = self._entries[run_id]
        entry.sent_at = time.monotonic()
        entry.attempts += 1
        try:
            await self._send(entry.message)
        except Exception as e:
            if run_id not in self._entries:
                return False
            if is_connection_error(e):
                entry.sent_at = None
                logger.warning(
                    f"Could not send result for run {run_id} ({e}); keeping it to resend "
                    f"after reconnecting ({len(self._entries)} kept)"
                )
            else:
                self._entries.pop(run_id, None)
                logger.error(f"Dropped result for run {run_id}: it cannot be sent: {e}")
            return False
        if not self.acks:
            self._entries.pop(run_id, None)
        return True

    def _drop_expired(self) -> None:
        cutoff = time.monotonic() - self.MAX_AGE_SECONDS
        for run_id in [r for r, e in self._entries.items() if e.queued_at < cutoff]:
            self._entries.pop(run_id, None)
            logger.warning(
                f"Dropped result for run {run_id}: not delivered within {self.MAX_AGE_SECONDS:.0f}s"
            )
