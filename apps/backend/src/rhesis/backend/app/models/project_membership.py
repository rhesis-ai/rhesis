"""ProjectMembership model — maps users to projects within an organization."""

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID


class ProjectMembership(Base):
    """Records that a user is a member of a project.

    A user can be a member of multiple projects within the same organization.
    The (project_id, user_id) pair is unique — no duplicate memberships.

    Created automatically when:
    - A user creates a project (auto-enrolled as owner)
    - A user is invited to an organization that has a Default Project

    ``role_id`` references ``role.id`` (ON DELETE SET NULL).  While NULL the
    community DefaultAuthorizationProvider treats the row as plain binary
    membership.  The EE PermissionAuthorizationProvider reads this column to
    resolve the caller's effective project role; on role deletion the FK clears
    the column and the member falls back to their org-level role.
    """

    __tablename__ = "project_membership"

    project_id = Column(
        GUID(),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        GUID(),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id = Column(
        GUID(),
        ForeignKey("role.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_membership_project_user"),
    )

    # Relationships
    project = relationship("Project", back_populates="memberships")
    user = relationship("User", back_populates="project_memberships")
    organization = relationship("Organization")
