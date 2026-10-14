"""Reading the audit log is itself recorded, as ``audit_log.viewed``.

At most one row per minute for each org, actor and credential, decided by a
``RepeatWindow``.

The row is written in the request's transaction, like a change. A failed write
fails the read, and the key is released so the next read records.
"""

from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.provenance import RequestProvenance, provenance_of
from rhesis.backend.app.services.audit_events import RepeatWindow, record_audit_event
from rhesis.backend.events.audit_actions import audit_action

VIEWED = audit_action(Permission.AuditLog.READ.value)
WINDOW_SECONDS = 60
_PREFIX = "audit_viewed:v1:"

_window = RepeatWindow("audit-viewed", WINDOW_SECONDS)


def _key(organization_id: str, provenance: RequestProvenance) -> str:
    return (
        f"{_PREFIX}{organization_id}:{provenance.actor_type.value}:"
        f"{provenance.actor_id}:{provenance.credential_id}"
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
        record_audit_event(VIEWED, organization_id, db=db)
    except Exception:
        _window.release(key)
        raise
