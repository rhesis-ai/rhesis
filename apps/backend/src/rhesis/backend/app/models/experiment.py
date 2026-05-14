"""Experiment model — a named, versioned bundle of parameter values.

An :class:`Experiment` belongs to a :class:`Project` and an organization.
It accumulates immutable :class:`ExperimentVersion` rows in its JSONB
``versions`` array; each save with novel content appends one entry, and
saves with an existing content hash are no-ops at the API layer (the
server returns the existing version rather than appending a duplicate).

Visibility (``private`` vs ``shared``) is enforced at the route layer:
the list/detail endpoints exclude other users' private experiments,
and only ``shared`` experiments may be promoted onto a project label.

The ``update_count`` is the optimistic-concurrency guard for version
appends; the route handler does ``SELECT ... FOR UPDATE`` and bumps it
on every successful append.
"""

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from rhesis.backend.app.models.guid import GUID
from rhesis.backend.app.models.pydantic_column import (
    pydantic_list_jsonb_column,
)
from rhesis.backend.app.schemas.parameters import (
    ExperimentVersion as ExperimentVersionSchema,
)

from .base import Base
from .mixins import OrganizationMixin


class Experiment(Base, OrganizationMixin):
    """One named attempt at a configuration for a project."""

    __tablename__ = "experiment"

    project_id = Column(
        GUID(),
        ForeignKey("project.id"),
        nullable=False,
        index=True,
    )
    owner_user_id = Column(
        GUID(),
        ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Visibility is a string (not an Enum) to keep migrations cheap when
    # the value set evolves; the application layer constrains it to the
    # closed set ``{'private', 'shared'}``.
    visibility = Column(
        String(16),
        nullable=False,
        server_default="private",
    )

    versions = Column(
        pydantic_list_jsonb_column(ExperimentVersionSchema),
        nullable=False,
        server_default="[]",
    )

    update_count = Column(Integer, nullable=False, server_default="0")

    project = relationship("Project", foreign_keys=[project_id])
    owner = relationship("User", foreign_keys=[owner_user_id])
