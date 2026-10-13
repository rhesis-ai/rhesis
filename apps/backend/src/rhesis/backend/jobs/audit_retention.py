"""Daily purge of audit events past each org's retention window.

Runs only where the audit log is installed (the EE package registers it).
Every org is visited, including soft-deleted ones and ones that lost the
feature; which window applies, and why only expired rows go: see
``app/services/audit_retention.py``.

Each org runs in its own session and transaction, scoped to that org for RLS,
so one org's failure costs no other org its purge. Old export files are then
deleted in a second transaction (see ``register_export_cleanup``).
"""

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from rhesis.backend.app.database import (
    SessionLocal,
    bind_scope_to_session,
    without_soft_delete_filter,
)
from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.services.audit_retention import (
    export_cleanup,
    purge_expired_audit_events,
)
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)

_RESULT_KEYS = (
    "events_purged",
    "orgs_purged",
    "orgs_failed",
    "export_files_deleted",
    "export_cleanups_failed",
)


def _organizations() -> list[Organization]:
    db = SessionLocal()
    try:
        with without_soft_delete_filter():
            return db.query(Organization).all()
    finally:
        db.close()


def _in_org_session(org: Organization, work: Callable[[Session], int]) -> int:
    db = SessionLocal()
    try:
        bind_scope_to_session(db, str(org.id))
        result = work(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _purge_organization(org: Organization, now: datetime) -> int:
    return _in_org_session(org, lambda db: purge_expired_audit_events(db, org, now))


def _clean_exports(org: Organization, now: datetime) -> int:
    cleanup = export_cleanup()
    if cleanup is None:
        return 0
    return _in_org_session(org, lambda db: cleanup(db, org, now))


def _purge_one(org: Organization, now: datetime, totals: Counter) -> None:
    try:
        count = _purge_organization(org, now)
    except Exception:
        logger.exception("Audit purge failed for organization %s", org.id)
        totals["orgs_failed"] += 1
        return
    if count:
        logger.info("Audit purge: org=%s rows=%d", org.id, count)
        totals["events_purged"] += count
        totals["orgs_purged"] += 1


def _clean_one(org: Organization, now: datetime, totals: Counter) -> None:
    # Apart from the purge, so a storage outage never holds back the events' purge.
    try:
        totals["export_files_deleted"] += _clean_exports(org, now)
    except Exception:
        logger.exception("Audit export cleanup failed for organization %s", org.id)
        totals["export_cleanups_failed"] += 1


@app.task(bind=True)
def sweep_expired_audit_events(self) -> dict:
    """Purge expired audit events and old export files, org by org."""
    if not FeatureRegistry.is_registered(FeatureName.AUDIT_LOG):
        return {"enabled": False}

    now = datetime.now(timezone.utc)
    totals: Counter = Counter()
    for org in _organizations():
        _purge_one(org, now, totals)
        _clean_one(org, now, totals)

    result = {key: totals[key] for key in _RESULT_KEYS}
    logger.info("Audit purge complete: %s", result)
    return {"enabled": True, **result}
