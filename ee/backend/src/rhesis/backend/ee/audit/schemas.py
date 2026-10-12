"""Response shapes of the audit log read API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


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


class AuditActionRead(BaseModel):
    """One action the log can hold: ``endpoint.updated`` is ``endpoint`` + ``updated``."""

    action: str
    resource: str
    verb: str
