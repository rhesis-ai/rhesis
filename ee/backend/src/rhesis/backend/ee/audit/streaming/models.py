"""``audit_destination``: where an org streams its audit log, and how far delivery got.

Migration ``a7c3e9d2f410``. Org-scoped with ``tenant_isolation`` RLS.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from rhesis.backend.app.models.audit_policy import AuditPolicy
from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.guid import GUID
from rhesis.backend.app.utils.encryption import EncryptedString

# Written by the delivery job on every batch; recording them would flood the log.
DELIVERY_STATE = (
    "cursor_recorded_at",
    "cursor_id",
    "consecutive_failures",
    "next_attempt_at",
    "last_success_at",
    "last_error",
    "last_error_at",
)


class AuditDestination(Base):
    __tablename__ = "audit_destination"
    # Adding, pausing (also auto-pausing) and deleting are recorded; delivery progress is not.
    __audit__ = AuditPolicy(resource="audit_destination", ignore=DELIVERY_STATE)

    organization_id = Column(
        GUID(), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(120), nullable=False)
    kind = Column(String(32), nullable=False)
    # JSON with the kind's settings, secrets included.
    config = Column(EncryptedString(), nullable=False)
    paused = Column(Boolean, nullable=False, default=False, server_default="false")
    # "manual" or "failures"; null while running.
    paused_reason = Column(String(16), nullable=True)

    # Last event delivered, on (recorded_at, id).
    cursor_recorded_at = Column(DateTime(timezone=True), nullable=False)
    cursor_id = Column(GUID(), nullable=False)
    consecutive_failures = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
