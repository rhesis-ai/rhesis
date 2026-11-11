"""Per-organization cap on heavy background jobs.

Workers are shared by every organization and take jobs first in, first out, so one
organization queueing many long jobs would hold every worker thread for hours. This
caps how many of those jobs an organization may have queued or running at once.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.config.settings import get_job_limit_settings
from rhesis.backend.app.crud.job import count_active_jobs
from rhesis.backend.app.crud.project import list_org_project_ids

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

# Longer than any capped job's own time limit, so the row of a job whose worker
# died without finishing it stops counting.
ACTIVE_JOB_WINDOW = timedelta(hours=3)


class JobCapacityExceededError(HTTPException):
    def __init__(self, limit: int):
        super().__init__(
            status_code=429,
            detail=(
                f"Your organization has reached its limit of {limit} jobs queued or "
                "running at once. Wait for one to finish and try again."
            ),
        )


def _count_org_active_jobs(db: Session, organization_id: str, user_id: str) -> int:
    from rhesis.backend.app.database import temporary_project_scope

    job_types = sorted(CAPPED_JOB_TYPES)
    since = datetime.now(timezone.utc) - ACTIVE_JOB_WINDOW
    # Project RLS shows one project's rows at a time, so count project by project.
    total = count_active_jobs(db, organization_id, None, job_types, since)
    for project_id in list_org_project_ids(db, organization_id):
        with temporary_project_scope(db, organization_id, user_id, str(project_id)):
            total += count_active_jobs(db, organization_id, project_id, job_types, since)
    return total


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
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"job-capacity:{organization_id}"},
        )
    active = _count_org_active_jobs(db, str(organization_id), str(user_id or ""))
    if active >= limit:
        logger.warning(f"Organization {organization_id} at its job cap ({active}/{limit})")
        raise JobCapacityExceededError(limit)
