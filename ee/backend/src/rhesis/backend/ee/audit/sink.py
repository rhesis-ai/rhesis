"""``AuditSink``: stores ``AuditRecorded`` events in ``audit_event``.

Critical. With the caller's session (every change) it writes in the caller's
transaction, so the entry and the change commit or roll back together, and a
failed write fails the request. Without one (a denial or a failed sign-in,
whose own transaction is rolling back) it writes on a short session of its
own, and a failure is logged rather than raised: the request is failing anyway.

Writes only for orgs entitled to ``FeatureName.AUDIT_LOG``.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.models.audit_capture import audit_enabled, session_org
from rhesis.backend.ee.audit.crud import insert_audit_event
from rhesis.backend.events.types import AuditRecorded, PlatformEvent

logger = logging.getLogger(__name__)


def audit_row(event: AuditRecorded) -> dict:
    """The ``audit_event`` columns for ``event``."""
    if event.summary is not None:
        changes = {"count": event.summary.count, "ids": [str(i) for i in event.summary.ids]}
    else:
        # Content values are opt-in per org (PR 9); until then they are dropped.
        changes = [
            c.model_dump(mode="json", exclude={"before", "after"} if c.kind == "content" else None)
            for c in event.changes
        ]
    return {
        "organization_id": event.organization_id,
        "project_id": event.project_id,
        "occurred_at": event.occurred_at,
        "action": event.action,
        "outcome": event.outcome,
        "status_code": event.status_code,
        "actor_type": event.actor_type.value,
        "actor_id": event.user_id,
        "actor_credential_id": event.actor_credential_id,
        "actor_credential_hint": event.actor_credential_hint,
        "actor_label": event.actor_label,
        "channel": event.channel.value,
        "ip": str(event.ip) if event.ip is not None else None,
        "user_agent": event.user_agent,
        "resource_id": event.entity_id,
        "resource_label": event.resource_label,
        "request_id": event.request_id,
        "trace_id": event.trace_id,
        "span_id": event.span_id,
        "job_id": event.job_id,
        "changes": changes,
        "content_changes": None,
    }


class AuditSink:
    name = "audit"
    critical = True

    def handles(self, event: PlatformEvent) -> bool:
        return isinstance(event, AuditRecorded)

    def deliver(self, event: PlatformEvent, db: Optional[Session]) -> None:
        if db is None:
            self._deliver_alone(event)
            return
        if not audit_enabled(db, event.organization_id):
            return
        try:
            _write(db, event)
        except Exception:
            logger.error(
                f"Audit write failed for {event.action} in org {event.organization_id}; "
                "failing the change with it"
            )
            raise

    @staticmethod
    def _deliver_alone(event: AuditRecorded) -> None:
        try:
            with get_db_with_tenant_variables(str(event.organization_id)) as own_db:
                if audit_enabled(own_db, event.organization_id):
                    _write(own_db, event)
        except Exception:
            logger.exception(
                f"Audit write failed for {event.action} in org {event.organization_id}"
            )


def _write(db: Session, event: AuditRecorded) -> None:
    as_org = session_org(db) != str(event.organization_id)
    insert_audit_event(db.connection(), audit_row(event), as_org=as_org)
