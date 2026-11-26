"""Per-organization cap on heavy background jobs.

Workers are shared by every organization and take jobs first in, first out, so one
organization queueing many long jobs would hold every worker thread for hours. This
caps how many of those jobs an organization may have queued or running at once.
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.config.settings import get_job_limit_settings
from rhesis.backend.app.crud.job import count_active_jobs
from rhesis.backend.app.database import advisory_xact_lock, sum_over_org_projects
from rhesis.backend.app.services.job_deadlines import QUEUED_JOB_WINDOW, running_job_window

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
# They stop counting when the deadline sweep would fail them (see job_deadlines.py).


class JobCapacityExceededError(HTTPException):
    def __init__(self, limit: int, detail: str | None = None):
        super().__init__(
            status_code=429,
            detail=detail
            or (
                f"Your organization has reached its limit of {limit} jobs queued or "
                "running at once. Wait for one to finish and try again."
            ),
        )


def _count_org_active_jobs(db: Session, organization_id: str, user_id: str) -> int:
    now = datetime.now(timezone.utc)
    queued_since = now - QUEUED_JOB_WINDOW
    started_since = {
        job_type: now - (running_job_window(job_type) or QUEUED_JOB_WINDOW)
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
    db: Session, organization_id: str, user_id: str, serialize: bool = False, slots: int = 1
) -> None:
    """Raise JobCapacityExceededError unless the org has ``slots`` free under its job cap.

    *serialize* holds a per-org lock until *db* commits, for a caller that inserts
    the counted job row in the same transaction.
    """
    limit = get_job_limit_settings().max_active_jobs_per_org
    if not limit or not organization_id:
        return
    if serialize:
        advisory_xact_lock(db, f"job-capacity:{organization_id}")
    if slots > limit:
        raise JobCapacityExceededError(
            limit,
            f"This would start {slots} jobs, and your organization can have at most "
            f"{limit} queued or running at once. Start fewer at a time.",
        )
    active = _count_org_active_jobs(db, str(organization_id), str(user_id or ""))
    if active + slots > limit:
        logger.warning(f"Organization {organization_id} at its job cap ({active}/{limit})")
        if slots == 1:
            raise JobCapacityExceededError(limit)
        raise JobCapacityExceededError(
            limit,
            f"This would start {slots} jobs, but your organization has {max(limit - active, 0)} of "
            f"its {limit} free. Wait for some to finish and try again.",
        )
