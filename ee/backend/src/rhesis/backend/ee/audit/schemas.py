"""Response shapes of the audit log read API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rhesis.backend.app.models.organization_settings import MIN_RETENTION_DAYS
from rhesis.backend.app.services.audit_retention import MAX_RETENTION_DAYS


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    occurred_at: datetime
    recorded_at: datetime
    action: str
    outcome: str
    status_code: Optional[int] = None
    actor_type: str
    actor_id: Optional[UUID] = None
    actor_credential_id: Optional[str] = None
    actor_credential_hint: Optional[str] = None
    actor_label: Optional[str] = None
    channel: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    resource_id: Optional[UUID] = None
    resource_label: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: str
    span_id: str
    job_id: Optional[UUID] = None
    # A list of field changes, or an object for summaries such as audit_log.purged.
    changes: Any

    @field_validator("ip", mode="before")
    @classmethod
    def _ip_as_text(cls, value: Any) -> Optional[str]:
        # psycopg hands back an ipaddress object for inet.
        return None if value is None else str(value)


def event_payload(row) -> dict:
    """An event exactly as ``GET /audit-events`` lists it: what streaming and
    export send. Never ``content_changes``: those stay behind the detail route."""
    return AuditEventRead.model_validate(row).model_dump(mode="json")


class AuditEventDetail(AuditEventRead):
    # [{field, before, after}] for content fields, only while the org includes content.
    content_changes: Optional[list[dict[str, Any]]] = None


class AuditActionRead(BaseModel):
    """One action the log can hold: ``endpoint.updated`` is ``endpoint`` + ``updated``."""

    action: str
    resource: str
    verb: str


class AuditLogSettingsRead(BaseModel):
    #: The window in force: the org's choice, capped by its plan.
    retention_days: int
    max_retention_days: int
    #: Shorter than the six months the EU AI Act asks of high-risk systems. A warning only.
    below_eu_ai_act_minimum: bool
    mask_ip: bool
    include_content: bool
    #: Whether beat's heartbeat is recent, so the purge is actually running; null if unknown.
    scheduled_jobs_running: Optional[bool]


class AuditLogSettingsUpdate(BaseModel):
    """Partial update; a field left out or null keeps its value."""

    model_config = ConfigDict(extra="forbid")

    retention_days: Optional[int] = Field(None, ge=MIN_RETENTION_DAYS, le=MAX_RETENTION_DAYS)
    mask_ip: Optional[bool] = None
    include_content: Optional[bool] = None


class AuditExportCreate(BaseModel):
    """What to export. ``filter`` is the list's OData ``$filter``; rows are
    ordered by ``occurred_at`` in ``sort_order``."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["jsonl", "csv"] = "jsonl"
    filter: Optional[str] = None
    sort_order: Literal["asc", "desc"] = "desc"


class AuditExportCreated(BaseModel):
    #: The ``job`` row, as the Jobs screen shows it; null if it could not be recorded.
    job_id: Optional[UUID] = None
    #: Poll ``GET /jobs/{task_id}`` for status.
    task_id: str
    format: str
    message: str
