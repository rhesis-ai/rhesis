"""Audit log settings: retention and privacy, stored under ``audit_log`` in the
org's settings. The defaults and the retention rules are core
(``AuditLogSettingsAccessor``, ``services/audit_retention.py``), because the
purge job is core.

Both privacy settings apply when the sink writes a row, so a change affects
new rows only:

- **Mask IP** (on by default): only the address's network is stored.
- **Include content** (off by default): content field values are stored
  encrypted in ``content_changes``. Only the detail route returns them, and
  only while the setting is on.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.organization import get_organization, merge_organization_settings
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.services.audit_retention import (
    EU_AI_ACT_MIN_DAYS,
    max_retention_days,
    retention_days,
)
from rhesis.backend.app.services.beat_heartbeat import beat_signal
from rhesis.backend.ee.audit.models import AuditEvent
from rhesis.backend.ee.audit.schemas import (
    AuditEventDetail,
    AuditEventRead,
    AuditLogSettingsRead,
    AuditLogSettingsUpdate,
)


class RetentionAboveCap(ValueError):
    pass


def organization(db: Session, organization_id: str) -> Organization:
    return get_organization(db, UUID(str(organization_id)))


def read_settings(org: Organization) -> AuditLogSettingsRead:
    stored = org.settings.audit_log
    days = retention_days(org)
    return AuditLogSettingsRead(
        retention_days=days,
        max_retention_days=max_retention_days(org),
        below_eu_ai_act_minimum=days < EU_AI_ACT_MIN_DAYS,
        mask_ip=stored.mask_ip,
        include_content=stored.include_content,
        scheduled_jobs_running=beat_signal.running(),
    )


def update_settings(
    db: Session, org: Organization, update: AuditLogSettingsUpdate
) -> AuditLogSettingsRead:
    """Merge the fields sent. Raises ``RetentionAboveCap`` past the plan's cap."""
    changes = update.model_dump(exclude_none=True)
    days = changes.get("retention_days")
    if days is not None and days > max_retention_days(org):
        raise RetentionAboveCap(
            f"retention_days can be at most {max_retention_days(org)} on this plan"
        )
    if changes:
        merge_organization_settings(db, org, {"audit_log": changes})
    return read_settings(org)


def event_detail(event: AuditEvent, org: Organization) -> AuditEventDetail:
    content: Optional[Any] = None
    if org.settings.audit_log.include_content and event.content_changes:
        content = json.loads(event.content_changes)
    read = AuditEventRead.model_validate(event)
    return AuditEventDetail(**read.model_dump(), content_changes=content)
