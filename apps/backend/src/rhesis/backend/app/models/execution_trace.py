"""SQLAlchemy model for SDK connector execution traces."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.guid import GUID


class ExecutionTrace(Base):
    """Persisted execution trace reported by the SDK connector.

    Stores the function-level traces posted to ``/connector/trace`` so they
    survive log rotation and are queryable for analytics. This is distinct
    from the OpenTelemetry span model (``Trace``): no OTel identifiers are
    required here.
    """

    __tablename__ = "execution_trace"

    project_id = Column(
        GUID(), ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(GUID(), nullable=False, index=True)
    environment = Column(String(50), nullable=False, index=True)
    function_name = Column(String(255), nullable=False, index=True)
    inputs = Column(JSONB, nullable=False, default=dict)
    output = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, index=True)
    error = Column(Text, nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=False, index=True)
