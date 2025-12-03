from sqlalchemy import JSON, Column, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import ActivityTrackableMixin, OrganizationAndUserMixin


class Comment(Base, ActivityTrackableMixin, OrganizationAndUserMixin):
    __tablename__ = "comment"

    # Comment content
    content = Column(Text, nullable=False)

    # Emoji reactions stored as JSON
    emojis = Column(JSON, default=dict)

    # Entity relationship (polymorphic)
    entity_id = Column(GUID(), nullable=False)
    entity_type = Column(String, nullable=False)  # "Test", "TestSet", "TestRun", "Source"

    # Relationships
    user = relationship("User", back_populates="comments")
    organization = relationship("Organization", backref="comments")
