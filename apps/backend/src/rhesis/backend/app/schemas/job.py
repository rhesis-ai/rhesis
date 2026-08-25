from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import UUID4, BaseModel, ConfigDict, computed_field

from rhesis.backend.app.models.enums import JobStatus


class Job(BaseModel):
    """A background job as the Jobs screen sees it."""

    id: UUID4
    nano_id: Optional[str] = None
    organization_id: Optional[UUID4] = None
    project_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None

    celery_task_id: Optional[str] = None
    trace_id: Optional[str] = None

    job_type: str
    name: Optional[str] = None
    status: str

    entity_type: Optional[str] = None
    entity_id: Optional[UUID4] = None

    progress_current: Optional[int] = None
    progress_total: Optional[int] = None

    queued_at: Optional[Union[datetime, str]] = None
    started_at: Optional[Union[datetime, str]] = None
    finished_at: Optional[Union[datetime, str]] = None

    error_message: Optional[str] = None
    error_type: Optional[str] = None
    attempt: int = 0

    job_metadata: Optional[Dict[str, Any]] = None

    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]

    user_display_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def is_terminal(self) -> bool:
        """Whether the job has stopped for good.

        Served rather than left to the client so the frontend does not have to
        keep its own copy of which statuses are final -- a list that would
        silently rot the next time one is added.
        """
        try:
            return JobStatus(self.status).is_terminal
        except ValueError:
            # An unrecognised status is treated as still running: showing a live
            # job is recoverable, hiding a finished one from polling is not.
            return False

    @computed_field
    @property
    def cancellable(self) -> bool:
        """Whether asking this job to stop could do anything.

        Job *state*, not permission -- ``job:cancel`` governs who may ask. A
        terminal job has nothing left to stop, and one already cancelling has
        been asked.
        """
        return self.status in {JobStatus.QUEUED.value, JobStatus.RUNNING.value}


class ActivityLogEntry(BaseModel):
    """One user-facing log line."""

    id: UUID4
    job_id: Optional[UUID4] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID4] = None
    source: Optional[str] = None
    sequence: Optional[int] = None
    level: str
    message: str
    context: Optional[Dict[str, Any]] = None
    created_at: Union[datetime, str]

    model_config = ConfigDict(from_attributes=True)


class JobActivity(BaseModel):
    """A page of log entries plus the cursor to continue from.

    The cursor is returned rather than left for the client to compute from the
    last entry, so an empty page still advances correctly.
    """

    entries: List[ActivityLogEntry]
    next_after_sequence: Optional[int] = None
