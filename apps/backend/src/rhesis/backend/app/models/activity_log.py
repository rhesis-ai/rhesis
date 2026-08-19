from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationMixin, ProjectMixin


class ActivityLog(Base, OrganizationMixin, ProjectMixin):
    """A user-facing log entry.

    Named for activity rather than jobs because ``job_id`` is nullable: an
    entry usually belongs to a background job and shows in that job's detail
    view, but it does not have to. A quota warning, a connector failure, or any
    synchronous operation worth telling the user about can write here without
    inventing a fake job to hang it from.

    Filtering is on declared columns -- ``job_id``, ``entity_type``,
    ``entity_id``, ``source``, ``level`` -- rather than a free-form tag bag.
    That indexes properly and keeps the set of things an entry can say
    reviewable, which a JSONB tag column would not.

    Entries hold identifiers and counts, never payloads. "Generated 40 of 120
    tests", not the tests; "endpoint returned 500", not the response body.
    Anything a reader needs beyond that is reachable by following the ids, and
    those paths are already behind RLS and RBAC. LLM prompts and completions,
    test bodies, request and response bodies, and connector credentials must
    never reach this table.
    """

    __tablename__ = "activity_log"

    # Nullable on purpose: see the class docstring. CASCADE so a purged job
    # takes its narrative with it.
    job_id = Column(GUID(), ForeignKey("job.id", ondelete="CASCADE"), nullable=True)

    entity_type = Column(String(64), nullable=True)
    entity_id = Column(GUID(), nullable=True)

    # Emitting subsystem, e.g. "test_set_generation". A filter dimension, and
    # the thing to group by when a job has no id to group by.
    source = Column(String(128), nullable=True)

    # Monotonic per job. Gives the detail view a stable order and a cursor to
    # page from; timestamps tie under concurrent writes.
    sequence = Column(Integer, nullable=True)

    # User-facing severities only. A reader of a job log has no use for DEBUG
    # and no business seeing CRITICAL internals.
    level = Column(String(16), nullable=False)
    message = Column(Text, nullable=False)

    context = Column(JSONB, nullable=True)

    job = relationship("Job", foreign_keys=[job_id])

    __table_args__ = (
        # The job detail cursor.
        Index("ix_activity_log_job_sequence", "job_id", "sequence"),
        Index("ix_activity_log_organization_id", "organization_id"),
        # The eventual general activity query: this project, newest first.
        Index("ix_activity_log_project_created", "project_id", "created_at"),
        Index("ix_activity_log_entity", "entity_type", "entity_id"),
        # The retention sweep's global "created_at < cutoff" scan, across
        # every org/project -- the project-led index above cannot serve that.
        Index("ix_activity_log_created_at", "created_at"),
    )
