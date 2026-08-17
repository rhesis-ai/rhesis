from sqlalchemy import Column, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin, ProjectMixin


class Job(Base, OrganizationAndUserMixin, ProjectMixin):
    """A unit of background work, recorded so users can see what is running.

    One row per dispatch, created by ``launch_job`` before the message is
    published and advanced by ``BaseJob``'s lifecycle hooks. The row is the
    record of truth for the Jobs screen; Celery's result backend is not, since
    it expires after an hour and stores neither task name nor arguments.

    ``celery_task_id`` is the seam between our vocabulary and Celery's: the
    field name says which side of the line the value came from. It is indexed
    because looking a job up by it is how an API caller polls status.

    ``project_id`` is nullable, following ``ProjectMixin``. NULL means the job
    is org-wide and appears in every project's view *within its own
    organization* -- the tenant boundary is ``organization_id``, enforced by
    the auto-filter and by RLS. Making it NOT NULL was considered and rejected:
    a dispatch with no project in scope would fail its insert, which would let
    bookkeeping break real work.
    """

    __tablename__ = "job"

    celery_task_id = Column(String(255), nullable=True)

    # W3C trace-id (32 hex chars). Ties this job to its spans, its log entries,
    # and the request that dispatched it.
    trace_id = Column(String(32), nullable=True)

    job_type = Column(String(255), nullable=False)
    name = Column(String, nullable=True)
    status = Column(String(32), nullable=False, server_default=text("'queued'"))

    # Polymorphic link to whatever the job is about, so the detail view can
    # offer a way back to it. Same shape as Task.entity_type/entity_id.
    entity_type = Column(String(64), nullable=True)
    entity_id = Column(GUID(), nullable=True)

    progress_current = Column(Integer, nullable=True)
    progress_total = Column(Integer, nullable=True)

    queued_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    error_message = Column(String, nullable=True)
    error_type = Column(String(255), nullable=True)

    # Celery retry count, so a job that succeeded on its third attempt does not
    # look like one that succeeded first time.
    attempt = Column(Integer, nullable=False, server_default=text("0"))

    job_metadata = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_job_celery_task_id", "celery_task_id"),
        Index("ix_job_organization_id", "organization_id"),
        # The Jobs list is "this project's jobs, newest first".
        Index("ix_job_project_created", "project_id", "created_at"),
        Index("ix_job_trace_id", "trace_id"),
    )
