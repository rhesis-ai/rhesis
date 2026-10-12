"""Reading the audit log is itself recorded, as ``audit_log.viewed``.

At most one row per minute for each org, actor and credential. Rows cannot be
updated to merge repeats, so a Redis key (``SET NX EX``) decides which read
records. When Redis cannot answer, the read records anyway: an extra row is
better than a missing one.

The row is written in the request's transaction, like a change. A failed write
fails the read, and the key is released so the next read records.
"""

import logging

from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.models.audit_capture import _Context
from rhesis.backend.app.provenance import RequestProvenance, provenance_of
from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase
from rhesis.backend.events import emit
from rhesis.backend.events.audit_actions import audit_action
from rhesis.backend.events.types import AuditRecorded

logger = logging.getLogger(__name__)

VIEWED = audit_action(Permission.AuditLog.READ.value)
WINDOW_SECONDS = 60
_PREFIX = "audit_viewed:v1:"


class ViewWindow(RedisBackedCache):
    """Which reads still fall inside the last recorded view's minute."""

    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.AUDIT_VIEWED, cache_name="audit-viewed", ttl=WINDOW_SECONDS
        )

    def claim(self, key: str) -> bool:
        """True when this read should record: first in the window, or Redis cannot say.

        No in-memory fallback: it would suppress rows per process with nothing shared.
        """
        self.initialize()
        if self._redis is None:
            return True
        try:
            return bool(self._redis.set(key, "1", nx=True, ex=self._ttl))
        except Exception as exc:
            logger.warning(f"{self._cache_name}: Redis claim failed, recording anyway: {exc}")
            return True

    def release(self, key: str) -> None:
        self._delete(key)


_window = ViewWindow()


def _key(organization_id: str, provenance: RequestProvenance) -> str:
    return (
        f"{_PREFIX}{organization_id}:{provenance.actor_type.value}:"
        f"{provenance.actor_id}:{provenance.credential_id}"
    )


def _viewed_event(
    db: Session, provenance: RequestProvenance, organization_id: str
) -> AuditRecorded:
    ctx = _Context(db, provenance)
    trace_id, span_id = ctx.ids
    return AuditRecorded(
        occurred_at=ctx.occurred_at,
        organization_id=organization_id,
        user_id=provenance.actor_id,
        trace_id=trace_id,
        span_id=span_id,
        source="audit",
        action=VIEWED,
        outcome="success",
        actor_type=provenance.actor_type,
        actor_credential_id=provenance.credential_id,
        actor_credential_hint=provenance.credential_hint,
        actor_label=ctx.actor_label,
        channel=provenance.channel,
        ip=provenance.ip,
        user_agent=provenance.user_agent,
        request_id=provenance.request_id,
    )


def record_view(db: Session, organization_id: str) -> None:
    """Record that the request on ``db`` read the org's audit log. Call after the read."""
    provenance = provenance_of(db)
    if provenance is None:
        return
    key = _key(organization_id, provenance)
    if not _window.claim(key):
        return
    try:
        emit(_viewed_event(db, provenance, organization_id), db=db)
    except Exception:
        _window.release(key)
        raise
