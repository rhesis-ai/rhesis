"""How long each kind of job may run, and failing the job rows that outlived it.

Long jobs stop themselves at their limit (see ``app/utils/deadline.py``); the CPU-bound
ones get Celery time limits, which the prefork pool enforces by killing the child.
A job whose worker died, or whose child was killed, never writes a terminal status,
so :func:`fail_overdue_jobs` marks its row failed once it is past its limit plus
:data:`RUNNING_JOB_MARGIN`. Job capacity (``job_capacity.py``) stops counting a row
at the same point.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.config.settings import get_job_limit_settings

# A queued job may wait behind a backlog, so it is given a day, like the test-run
# quota's in-flight window.
QUEUED_JOB_WINDOW = timedelta(hours=24)
# Room for a job that stopped at its limit to write its result and status.
RUNNING_JOB_MARGIN = timedelta(minutes=30)

# (soft, hard) seconds for jobs that compute rather than wait. Enforced by the prefork
# pool only; on the thread pool the row is still failed by the sweep.
CPU_JOB_TIME_LIMITS: Dict[str, tuple[int, int]] = {
    "embedding.compute_graph_test_set": (600, 660),
    "embedding.compute_graph_source": (600, 660),
    "file.extract_text": (1800, 1860),
    "import_garak_probes": (1800, 1860),
}


def job_time_limits() -> Dict[str, int]:
    """Seconds each job type with a time limit may run, keyed by job type."""
    limits = get_job_limit_settings()
    return {
        "execute_test_configuration": limits.execution_time_limit,
        "endpoint.explore.run_exploration_task": limits.exploration_time_limit,
        "generate_and_save_test_set": limits.generation_time_limit,
        "generate_and_save_owasp_test_set": limits.generation_time_limit,
        "run_metric_tuning": limits.metric_tuning_time_limit,
        "sync_garak_test_set": limits.garak_sync_time_limit,
        **{job_type: hard for job_type, (_, hard) in CPU_JOB_TIME_LIMITS.items()},
    }


def running_job_window(job_type: str) -> Optional[timedelta]:
    """How long a running *job_type* job is believed to be alive, or None if unbounded."""
    seconds = job_time_limits().get(job_type)
    return None if seconds is None else timedelta(seconds=seconds) + RUNNING_JOB_MARGIN


def fail_overdue_jobs(db: Session, organization_id: str, now: Optional[datetime] = None) -> int:
    """Mark the org's job rows that outlived their limit as failed. Returns how many.

    A running job counts from its start, a queued one from when it was queued. Does
    not commit.
    """
    # Here, not at the top: celery/config.py reads the limits above and must not need a database.
    from rhesis.backend.app.crud.job import fail_overdue_jobs_in_scope
    from rhesis.backend.app.database import sum_over_org_projects

    now = now or datetime.now(timezone.utc)
    started_before = {
        job_type: now - timedelta(seconds=seconds) - RUNNING_JOB_MARGIN
        for job_type, seconds in job_time_limits().items()
    }
    queued_before = now - QUEUED_JOB_WINDOW
    return sum_over_org_projects(
        db,
        organization_id,
        "",
        lambda project_id: fail_overdue_jobs_in_scope(
            db, organization_id, project_id, started_before, queued_before, now
        ),
    )
