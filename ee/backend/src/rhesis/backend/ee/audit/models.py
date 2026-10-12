"""Read-side mapping of ``audit_event`` (migration ``ef7fe15a29ee``).

On its own declarative base, not the app's ``Base``: that one would add
``nano_id``/``updated_at``/``deleted_at`` columns the table does not have, and
everything that walks ``Base.registry`` would pick the table up (the recycle
bin's soft delete and restore, ``/resolve``, the tenant auto-filter, and
``metadata.create_all``). The table is append-only at the database anyway.

``content_changes`` is not mapped: it is ciphertext and nothing reads it yet.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Integer, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AuditBase(DeclarativeBase):
    pass


class AuditEvent(AuditBase):
    __tablename__ = "audit_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    action: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    status_code: Mapped[Optional[int]] = mapped_column(Integer)
    actor_type: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    actor_credential_id: Mapped[Optional[str]] = mapped_column(Text)
    actor_credential_hint: Mapped[Optional[str]] = mapped_column(Text)
    actor_label: Mapped[Optional[str]] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(Text)
    ip: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    resource_label: Mapped[Optional[str]] = mapped_column(Text)
    request_id: Mapped[Optional[str]] = mapped_column(Text)
    trace_id: Mapped[str] = mapped_column(Text)
    span_id: Mapped[str] = mapped_column(Text)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    changes: Mapped[Any] = mapped_column(JSONB)
