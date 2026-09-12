from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import ActivityTrackableMixin, OrganizationAndUserMixin, ProjectMixin


class Annotation(Base, ActivityTrackableMixin, ProjectMixin, OrganizationAndUserMixin):
    __tablename__ = "annotation"

    entity_type = Column(String, nullable=False)
    entity_id = Column(GUID(), nullable=False)
    target_type = Column(String, nullable=False)
    target_reference = Column(String, nullable=True)

    status_id = Column(GUID(), ForeignKey("status.id"), nullable=False)
    comments = Column(Text, nullable=True)

    resolved = Column(Boolean, nullable=False, server_default="false")
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by_id = Column(GUID(), ForeignKey("user.id"), nullable=True)

    attributes = Column(JSONB, nullable=True)

    status = relationship("Status", foreign_keys=[status_id])
    user = relationship("User", back_populates="annotations", foreign_keys="[Annotation.user_id]")
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    organization = relationship("Organization", backref="annotations")

    __table_args__ = (
        Index("ix_annotation_entity", "entity_type", "entity_id"),
        Index("ix_annotation_org_project_updated", "organization_id", "project_id", "updated_at"),
    )
