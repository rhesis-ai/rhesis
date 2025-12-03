from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

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
    status = relationship("Status", back_populates="projects")
