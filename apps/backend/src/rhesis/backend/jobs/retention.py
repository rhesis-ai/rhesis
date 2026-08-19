"""Hard-deletes old ``job``/``activity_log`` rows past the retention window.

Disabled by default (``JOB_RETENTION_ENABLED``, see ``JobRetentionSettings``):
a scheduled hard-delete is a deployment-owner decision. The task always runs
on the beat schedule below so toggling the flag is a config change, not a
redeploy of the schedule itself -- but it returns immediately when disabled.

Both tables' ``tenant_isolation`` policy is ``FORCE``d (see
d2c3b4a5e6f7_add_job_and_activity_log_tables.py), so even the table owner
cannot read across organizations without either ``BYPASSRLS`` or scoping the
query per organization. This loops over every organization and deletes
within that org's own scope -- correct without granting the app's runtime DB
role a new, broader privilege.

Each delete filters on ``organization_id`` explicitly rather than trusting
the ORM's ``before_compile`` auto-filter to inject it: that listener does
not reliably cover ``Query.delete()`` (confirmed empirically -- a bulk
delete scoped only via ``bind_scope_to_session`` deleted another
organization's rows). ``bind_scope_to_session`` is still called, for the RLS
GUCs it sets, but the org filter here does not depend on it.

Jobs are swept by ``finished_at``, not ``created_at``: a long-running job is
never a candidate just because it started long ago, only because it
*finished* long ago. A job that never reached a terminal status
(``finished_at IS NULL``) is never swept by this task at all.
``activity_log`` has no such distinction -- its own ``created_at`` is the
only signal, and a stray entry with no owning job is still swept on that
basis, not tied to any job's lifecycle.
"""

import logging
from datetime import datetime, timedelta, timezone

from rhesis.backend.app.config.settings import get_job_retention_settings
from rhesis.backend.app.database import SessionLocal, bind_scope_to_session
from rhesis.backend.app.models.activity_log import ActivityLog
from rhesis.backend.app.models.job import Job
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)


def _organization_ids() -> list[str]:
    """Every organization id, unscoped -- Organization is an ORM auto-filter
    exempt table (see models/scope_events.py's EXEMPT_TABLES), queried before
    any tenant context exists, same as auth lookups.
    """
    db = SessionLocal()
    try:
        return [str(row[0]) for row in db.query(Organization.id).all()]
    finally:
        db.close()


def _sweep_organization(organization_id: str, cutoff: datetime) -> tuple[int, int]:
    """Delete this org's rows past *cutoff*. Returns (jobs_deleted, logs_deleted)."""
    db = SessionLocal()
    try:
        bind_scope_to_session(db, organization_id)
        logs_deleted = (
            db.query(ActivityLog)
            .filter(
                ActivityLog.organization_id == organization_id,
                ActivityLog.created_at < cutoff,
            )
            .delete(synchronize_session=False)
        )
        jobs_deleted = (
            db.query(Job)
            .filter(
                Job.organization_id == organization_id,
                Job.finished_at.isnot(None),
                Job.finished_at < cutoff,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        return jobs_deleted, logs_deleted
    except Exception:
        db.rollback()
        logger.exception("Retention sweep failed for organization %s", organization_id)
        return 0, 0
    finally:
        db.close()


@app.task(bind=True)
def sweep_expired_jobs(self) -> dict:
    """Delete job/activity_log rows past the retention window, org by org."""
    settings = get_job_retention_settings()
    if not settings.enabled:
        logger.debug("Job retention sweep disabled (JOB_RETENTION_ENABLED=false); skipping")
        return {"enabled": False}

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)

    total_jobs_deleted = 0
    total_logs_deleted = 0
    for organization_id in _organization_ids():
        # _sweep_organization already catches its own errors: this second
        # layer only guards the part outside its try block (SessionLocal()
        # itself failing), so one organization's trouble never costs every
        # other organization its sweep for this run.
        try:
            jobs_deleted, logs_deleted = _sweep_organization(organization_id, cutoff)
        except Exception:
            logger.exception("Unexpected error sweeping organization %s", organization_id)
            continue
        total_jobs_deleted += jobs_deleted
        total_logs_deleted += logs_deleted

    logger.info(
        "Job retention sweep complete: %d job row(s), %d activity_log row(s) deleted (cutoff=%s)",
        total_jobs_deleted,
        total_logs_deleted,
        cutoff.isoformat(),
    )
    return {
        "enabled": True,
        "cutoff": cutoff.isoformat(),
        "jobs_deleted": total_jobs_deleted,
        "activity_log_deleted": total_logs_deleted,
    }
