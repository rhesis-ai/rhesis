"""Fails the job rows that outlived their time limit (see ``app/services/job_deadlines.py``).

A worker that died, or a prefork child killed at its hard limit, never writes a
terminal status, so without this the row would show the job running for good.
"""

import logging

from rhesis.backend.app.crud.organization import list_organization_ids
from rhesis.backend.app.database import SessionLocal, bind_scope_to_session
from rhesis.backend.app.services.job_deadlines import fail_overdue_jobs
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)


def _fail_for_organization(organization_id: str) -> int:
    db = SessionLocal()
    try:
        bind_scope_to_session(db, organization_id)
        failed = fail_overdue_jobs(db, organization_id)
        db.commit()
        return failed
    except Exception:
        db.rollback()
        logger.exception("Overdue job sweep failed for organization %s", organization_id)
        return 0
    finally:
        db.close()


@app.task(bind=True)
def sweep_overdue_jobs(self) -> dict:
    """Mark every organization's overdue job rows failed, one organization at a time."""
    db = SessionLocal()
    try:
        organization_ids = list_organization_ids(db)
    finally:
        db.close()

    failed = 0
    for organization_id in organization_ids:
        failed += _fail_for_organization(organization_id)
    if failed:
        logger.warning("Marked %d job(s) failed past their time limit", failed)
    return {"failed": failed}
