from sqlalchemy import Boolean, Column, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin, ProjectMixin


class Notification(Base, ProjectMixin, OrganizationAndUserMixin):
    """In-app notification for a completed background job (test set generation,
    test run execution, ...).

    ``event_type`` and ``section`` store the ``.value`` of the matching enum in
    ``models/enums.py``; ``entity_type`` stores the ``.value`` of
    :class:`rhesis.backend.app.constants.EntityType` (the same enum
    ``Comment.entity_type`` uses). Application code always writes through the
    enum, never a raw string.

    ``user_id`` is the recipient, set explicitly at creation time (not relied on
    for auto-stamp) since it is not necessarily "whoever is running the current
    request". ``project_id`` is nullable: NULL means org-wide, visible regardless
    of the caller's active project (same convention as every other ProjectMixin
    table).

    The org/user/project FKs come from the mixins, which declare no
    ``ondelete``; the ``ON DELETE CASCADE`` that makes a notification die with
    its recipient, org, or project is defined in the create-table migration
    only. Same split as ``Chunk`` -- so a schema built by
    ``Base.metadata.create_all`` instead of Alembic has no cascade.
    """

    __tablename__ = "notification"

    event_type = Column(String, nullable=False, index=True)
    section = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    is_failure = Column(Boolean, nullable=False, server_default=text("false"))
    entity_type = Column(String, nullable=True)
    entity_id = Column(GUID(), nullable=True, index=True)
    payload = Column(JSONB, nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True, index=True)
