"""SQLAlchemy models for traces."""

from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.guid import GUID
from rhesis.backend.app.models.mixins import CommentsMixin, TagsMixin

if TYPE_CHECKING:
    pass


class Trace(Base, TagsMixin, CommentsMixin):
    """OpenTelemetry trace span model."""

    __tablename__ = "trace"

    # OpenTelemetry identifiers
    trace_id = Column(String(32), nullable=False, index=True)
    span_id = Column(String(16), nullable=False, index=True)
    parent_span_id = Column(String(16), nullable=True, index=True)

    # Rhesis identifiers
    project_id = Column(
        GUID(), ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(GUID(), nullable=False, index=True)
    environment = Column(String(50), nullable=False, index=True)

    # Span metadata
    span_name = Column(String(255), nullable=False, index=True)
    span_kind = Column(String(20), nullable=False)

    # Timing
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    duration_ms = Column(Float, nullable=False)

    # Status
    status_code = Column(String(20), nullable=False, index=True)
    status_message = Column(Text, nullable=True)

    # Flexible data storage
    attributes = Column(JSONB, nullable=False, default=dict)
    events = Column(JSONB, nullable=False, default=list)
    links = Column(JSONB, nullable=False, default=list)
    resource = Column(JSONB, nullable=False, default=dict)

    # Processing metadata
    processed_at = Column(DateTime, nullable=True)
    enriched_data = Column(JSONB, default=dict)

    # Relationships
    project = relationship("Project", back_populates="traces")

    # Composite indexes
    __table_args__ = (
        Index("idx_trace_project_time", "project_id", start_time.desc()),
        Index("idx_trace_trace_id", "trace_id", "start_time"),
        Index("idx_trace_span_name_time", "span_name", start_time.desc()),
        Index("idx_trace_environment_time", "environment", start_time.desc()),
        Index("idx_trace_status_time", "status_code", start_time.desc()),
        Index("idx_trace_org_time", "organization_id", start_time.desc()),
        Index(
            "idx_trace_unprocessed",
            "created_at",
            postgresql_where=(processed_at.is_(None)),
        ),
        Index(
            "idx_trace_attributes",
            "attributes",
            postgresql_using="gin",
            postgresql_ops={"attributes": "jsonb_path_ops"},
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Trace(id={self.id}, trace_id={self.trace_id}, "
            f"span_name={self.span_name}, duration={self.duration_ms}ms)>"
        )

    @property
    def operation_type(self) -> str | None:
        """Extract operation type from attributes."""
        return self.attributes.get("ai.operation.type")

    @property
    def model_name(self) -> str | None:
        """Extract model name from attributes."""
        return self.attributes.get("ai.model.name")

    @property
    def total_tokens(self) -> int | None:
        """Extract total tokens from attributes."""
        return self.attributes.get("ai.llm.tokens.total")
