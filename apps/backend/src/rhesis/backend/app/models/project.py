from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.models.pydantic_column import pydantic_jsonb_column
from rhesis.backend.app.schemas.parameters import (
    ParameterSchema,
    ProjectEnvironments,
)

from .base import Base
from .guid import GUID
from .mixins import ActivityTrackableMixin, TagsMixin


class Project(Base, ActivityTrackableMixin, TagsMixin):
    __tablename__ = "project"

    # Basic information
    name = Column(String, nullable=False)
    description = Column(Text)
    icon = Column(String)

    # Project settings
    is_active = Column(Boolean, default=True)
    attributes = Column(JSONB, nullable=True)

    # Parameter management — schema declares the typed slots; environments map
    # well-known names (``default`` etc.) to a single (experiment, version)
    # pair. Both default to empty so existing projects pick up the feature
    # without a row-level migration.
    parameters_schema = Column(
        pydantic_jsonb_column(ParameterSchema),
        nullable=False,
        server_default='{"fields": []}',
    )
    parameter_environments = Column(
        pydantic_jsonb_column(ProjectEnvironments),
        nullable=False,
        server_default='{"environments": {}}',
    )

    # Relationships - Foreign Keys
    user_id = Column(GUID(), ForeignKey("user.id"))
    owner_id = Column(GUID(), ForeignKey("user.id"))
    organization_id = Column(GUID(), ForeignKey("organization.id"))
    status_id = Column(GUID(), ForeignKey("status.id"))

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="created_projects")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_projects")
    organization = relationship("Organization", back_populates="projects")
    endpoints = relationship("Endpoint", back_populates="project")
    status = relationship("Status", foreign_keys=[status_id], back_populates="projects")
    traces = relationship("Trace", back_populates="project", cascade="all, delete-orphan")
    memberships = relationship(
        "ProjectMembership", back_populates="project", cascade="all, delete-orphan"
    )
