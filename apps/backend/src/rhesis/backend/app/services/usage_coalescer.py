"""Sum model-token accruals in process and queue one ``accrue_usage`` per org per interval.

Every LLM call used to queue its own ``accrue_usage`` task: four per executed test
with three metrics, each a broker round trip plus a worker slot and a DB session.
Under load those tasks queued behind real work in the same queue. Summing per
``(organization, resource)`` and flushing every ``USAGE_ACCRUAL_FLUSH_SECONDS``
keeps the same write path (the task and its upsert) at a fraction of the volume.

What this trades: tokens summed but not yet flushed are lost if the process is
killed without a clean shutdown (at most one interval). The hosted spend caps are
enforced separately (``hosted_spend``), so this only delays the usage counter.
"""

import atexit
import logging
import os
import threading
from collections import defaultdict

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.services.usage import dispatch_accrual

logger = logging.getLogger(__name__)


def flush_seconds() -> float:
    """Summing interval; 0 or less dispatches each accrual at once."""
    return float(os.environ.get("USAGE_ACCRUAL_FLUSH_SECONDS", "2.0"))


_lock = threading.Lock()
_pending: dict[tuple[str, QuotaResource], int] = defaultdict(int)
_flusher: threading.Thread | None = None
_flusher_pid: int | None = None


def add(organization_id: str, resource: QuotaResource, amount: int) -> None:
    """Add *amount* to the pending sum, or dispatch now when coalescing is off."""
    if flush_seconds() <= 0:
        dispatch_accrual(organization_id, resource, amount)
        return
    with _lock:
        _pending[(organization_id, resource)] += amount
        _ensure_flusher()


def flush() -> None:
    """Queue one accrual per pending ``(org, resource)``. Never raises."""
    with _lock:
        batch = dict(_pending)
        _pending.clear()
    for (organization_id, resource), amount in batch.items():
        dispatch_accrual(organization_id, resource, amount)


def _ensure_flusher() -> None:
    # Started lazily and per pid: a thread does not survive fork, so a forked child
    # (prefork pool, uvicorn workers) starts its own on first use.
    global _flusher, _flusher_pid
    if _flusher is not None and _flusher_pid == os.getpid() and _flusher.is_alive():
        return
    _flusher_pid = os.getpid()
    _flusher = threading.Thread(target=_run, name="usage-accrual-flush", daemon=True)
    _flusher.start()


def _run() -> None:
    stop = threading.Event()
    while not stop.wait(max(flush_seconds(), 0.1)):
        try:
            flush()
        except Exception:
            logger.warning("usage accrual flush failed", exc_info=True)


def _reset_in_child() -> None:
    # The parent flushes what it summed; a child counting it again would bill it twice.
    # A fresh lock too, in case another thread held it at the fork.
    global _lock, _flusher, _flusher_pid
    _lock = threading.Lock()
    _pending.clear()
    _flusher = _flusher_pid = None


os.register_at_fork(after_in_child=_reset_in_child)
atexit.register(flush)
