from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import ActivityTrackableMixin, OrganizationAndUserMixin, TagsMixin


class Task(Base, ActivityTrackableMixin, OrganizationAndUserMixin, TagsMixin):
    __tablename__ = "task"

    # Core fields
    title = Column(String, nullable=False)
    description = Column(Text)

    # User relationships
    assignee_id = Column(GUID(), ForeignKey("user.id"), nullable=True)

    # Status and priority relationships
    status_id = Column(GUID(), ForeignKey("status.id"), nullable=False)
    priority_id = Column(GUID(), ForeignKey("type_lookup.id"), nullable=True)

    # Entity relationship (polymorphic)
    entity_id = Column(GUID(), nullable=True)
    entity_type = Column(String, nullable=True)  # "Test", "TestSet", "TestRun", "Comment"

    # Timestamps
    completed_at = Column(DateTime, nullable=True)

    # Metadata
    task_metadata = Column(JSON, default=dict)

    # Relationships
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_tasks")
    status = relationship("Status", back_populates="tasks")
    priority = relationship("TypeLookup", back_populates="task_priorities")

    # Comment relationship (polymorphic)
    comments = relationship(
        "Comment",
        primaryjoin="and_(Comment.entity_id == foreign(Task.id), Comment.entity_type == 'Task')",
        viewonly=True,
        uselist=True,
    )

    @property
    def comment_count(self):
        """Get the count of comments for this task"""
        return len(self.comments) if self.comments else 0
