"""Per-organization cap on heavy background jobs.

Workers are shared by every organization and take jobs first in, first out, so one
organization queueing many long jobs would hold every worker thread for hours. This
caps how many of those jobs an organization may have queued or running at once.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.config.settings import get_job_limit_settings
from rhesis.backend.app.crud.job import count_active_jobs
from rhesis.backend.app.database import advisory_xact_lock, sum_over_org_projects

logger = logging.getLogger(__name__)

# Job types (Celery task names minus "rhesis.backend.jobs.") that hold a worker for long.
CAPPED_JOB_TYPES = frozenset(
    {
        "execute_test_configuration",
        "generate_and_save_test_set",
        "generate_and_save_owasp_test_set",
        "import_garak_probes",
        "sync_garak_test_set",
        "endpoint.explore.run_exploration_task",
        "run_metric_tuning",
    }
)

# Rows whose job never reached a terminal status (a worker died, a message was lost)
# must stop counting at some point, or the organization stays at its cap for good.
# A queued job may wait behind a backlog, so it counts for a day, like the test-run
# quota's in-flight window. A running test run or exploration stops itself at its
# time limit, so it counts for that limit plus a margin. The other types have no
# in-job limit yet and count for the same day as a queued job.
QUEUED_JOB_WINDOW = timedelta(hours=24)
RUNNING_JOB_MARGIN = timedelta(minutes=30)
TIMED_JOB_TYPES = frozenset({"execute_test_configuration", "endpoint.explore.run_exploration_task"})


class JobCapacityExceededError(HTTPException):
    def __init__(self, limit: int):
        super().__init__(
            status_code=429,
            detail=(
                f"Your organization has reached its limit of {limit} jobs queued or "
                "running at once. Wait for one to finish and try again."
            ),
        )


def running_job_window() -> timedelta:
    limits = get_job_limit_settings()
    longest = max(limits.execution_time_limit, limits.exploration_time_limit)
    return timedelta(seconds=longest) + RUNNING_JOB_MARGIN


def _count_org_active_jobs(db: Session, organization_id: str, user_id: str) -> int:
    now = datetime.now(timezone.utc)
    queued_since = now - QUEUED_JOB_WINDOW
    started_since = {
        job_type: now - (running_job_window() if job_type in TIMED_JOB_TYPES else QUEUED_JOB_WINDOW)
        for job_type in sorted(CAPPED_JOB_TYPES)
    }
    return sum_over_org_projects(
        db,
        organization_id,
        user_id,
        lambda project_id: count_active_jobs(
            db, organization_id, project_id, queued_since, started_since
        ),
    )


def enforce_job_capacity(
    db: Session, organization_id: str, user_id: str, serialize: bool = False
) -> None:
    """Raise JobCapacityExceededError if the org is at its cap of capped jobs.

    *serialize* holds a per-org lock until *db* commits, for a caller that inserts
    the counted job row in the same transaction.
    """
    limit = get_job_limit_settings().max_active_jobs_per_org
    if not limit or not organization_id:
        return
    if serialize:
        advisory_xact_lock(db, f"job-capacity:{organization_id}")
    active = _count_org_active_jobs(db, str(organization_id), str(user_id or ""))
    if active >= limit:
        logger.warning(f"Organization {organization_id} at its job cap ({active}/{limit})")
        raise JobCapacityExceededError(limit)
