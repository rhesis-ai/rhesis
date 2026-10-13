"""``AuditSink``: stores ``AuditRecorded`` events in ``audit_event``.

Critical. With the caller's session (every change) it writes in the caller's
transaction, so the entry and the change commit or roll back together, and a
failed write fails the request. Without one (a denial or a failed sign-in,
whose own transaction is rolling back) it writes on a short session of its
own, and a failure is logged rather than raised: the request is failing anyway.

Writes only for orgs entitled to ``FeatureName.AUDIT_LOG``. Follows the org's
privacy settings as it writes: a masked IP when "mask IP" is on (the default),
and content field values, encrypted, only when "include content" is on.
Changing either affects new rows only.
"""

import ipaddress
import json
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.models.audit_capture import audit_enabled, session_org
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.organization_settings import AuditLogSettingsAccessor
from rhesis.backend.ee.audit.crud import insert_audit_event
from rhesis.backend.events.types import AuditRecorded, PlatformEvent

logger = logging.getLogger(__name__)

_MASK_PREFIX = {4: 24, 6: 48}


def masked_ip(ip: str) -> str:
    """The network an address belongs to: its /24 for IPv4, its /48 for IPv6."""
    address = ipaddress.ip_address(ip)
    prefix = _MASK_PREFIX[address.version]
    return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False).network_address)


def audit_row(event: AuditRecorded, mask_ip: bool = True, include_content: bool = False) -> dict:
    """The ``audit_event`` columns for ``event``.

    With ``mask_ip`` only the address's network is stored, so the full address
    is never kept. Content values never go in ``changes``. With
    ``include_content`` they go in ``content_changes``, which the column type
    encrypts; without, they are dropped.
    """
    ip = str(event.ip) if event.ip is not None else None
    if ip is not None and mask_ip:
        ip = masked_ip(ip)
    content = None
    if event.summary is not None:
        changes = {"count": event.summary.count, "ids": [str(i) for i in event.summary.ids]}
    else:
        changes = [
            c.model_dump(mode="json", exclude={"before", "after"} if c.kind == "content" else None)
            for c in event.changes
        ]
        if include_content:
            values = [
                c.model_dump(mode="json", exclude={"kind"})
                for c in event.changes
                if c.kind == "content"
            ]
            content = json.dumps(values) if values else None
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
        "ip": ip,
        "user_agent": event.user_agent,
        "resource_id": event.entity_id,
        "resource_label": event.resource_label,
        "request_id": event.request_id,
        "trace_id": event.trace_id,
        "span_id": event.span_id,
        "job_id": event.job_id,
        "changes": changes,
        "content_changes": content,
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


def _audit_settings(db: Session, organization_id) -> AuditLogSettingsAccessor:
    with db.no_autoflush:
        org = db.get(Organization, UUID(str(organization_id)))
    # Not org.settings: its cached manager points back at the org, and a response that
    # serializes an ORM row holding that org would then recurse forever.
    raw = (org.organization_settings or {}) if org is not None else {}
    return AuditLogSettingsAccessor(raw.get("audit_log") or {})


def _write(db: Session, event: AuditRecorded) -> None:
    as_org = session_org(db) != str(event.organization_id)
    settings = _audit_settings(db, event.organization_id)
    row = audit_row(event, mask_ip=settings.mask_ip, include_content=settings.include_content)
    insert_audit_event(db.connection(), row, as_org=as_org)
