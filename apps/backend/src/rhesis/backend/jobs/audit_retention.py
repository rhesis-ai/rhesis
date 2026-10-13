"""Daily purge of audit events past each org's retention window.

Runs only where the audit log is installed (the EE package registers it).
Every org is visited, including soft-deleted ones and ones that lost the
feature; which window applies, and why only expired rows go: see
``app/services/audit_retention.py``.

Each org runs in its own session and transaction, scoped to that org for RLS,
so one org's failure costs no other org its purge.
"""

import logging
from datetime import datetime, timezone

from rhesis.backend.app.database import (
    SessionLocal,
    bind_scope_to_session,
    without_soft_delete_filter,
)
from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.services.audit_retention import purge_expired_audit_events
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)


def _organizations() -> list[Organization]:
    db = SessionLocal()
    try:
        with without_soft_delete_filter():
            return db.query(Organization).all()
    finally:
        db.close()


def _purge_organization(org: Organization, now: datetime) -> int:
    db = SessionLocal()
    try:
        bind_scope_to_session(db, str(org.id))
        count = purge_expired_audit_events(db, org, now)
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@app.task(bind=True)
def sweep_expired_audit_events(self) -> dict:
    """Purge expired audit events, org by org."""
    if not FeatureRegistry.is_registered(FeatureName.AUDIT_LOG):
        return {"enabled": False}

    now = datetime.now(timezone.utc)
    purged = orgs_purged = orgs_failed = 0
    for org in _organizations():
        try:
            count = _purge_organization(org, now)
        except Exception:
            logger.exception("Audit purge failed for organization %s", org.id)
            orgs_failed += 1
            continue
        if count:
            logger.info("Audit purge: org=%s rows=%d", org.id, count)
            purged += count
            orgs_purged += 1

    logger.info(
        "Audit purge complete: %d row(s) across %d org(s), %d failed",
        purged,
        orgs_purged,
        orgs_failed,
    )
    return {
        "enabled": True,
        "events_purged": purged,
        "orgs_purged": orgs_purged,
        "orgs_failed": orgs_failed,
    }
