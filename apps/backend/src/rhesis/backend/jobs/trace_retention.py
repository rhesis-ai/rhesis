"""Hard-deletes trace (span) rows past each org's tier retention window.

Disabled by default (``TRACE_RETENTION_ENABLED``), and defaults to dry-run
when first enabled (``TRACE_RETENTION_DRY_RUN``) so the blast radius is
visible in logs before anything is actually deleted.

Retention days come from the org's resolved ``QuotaPolicy.retention_days``
(tier catalog + any per-org ``custom_retention_days`` override on the
license token). ``TRACE_RETENTION_DAYS`` overrides the tier value for all
orgs when set (useful for self-hosted deployments without the EE tier
system). An org whose resolved retention is ``None`` (unlimited) is skipped.

Each org is swept in its own session and transaction, same pattern as
``jobs/retention.py``. See that module's docstring for the rationale on
explicit ``organization_id`` filters, ``bind_scope_to_session`` for RLS
GUCs, and per-org error isolation.
"""

import logging
from datetime import datetime, timedelta, timezone

from rhesis.backend.app.config.settings import get_trace_retention_settings
from rhesis.backend.app.database import SessionLocal, bind_scope_to_session
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.quota import QuotaRegistry
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)

BACKSTOP_MULTIPLIER = 10


def _resolve_retention_days(org: Organization, override_days: int | None) -> int | None:
    """Return the effective retention window for *org*, in days.

    If the settings carry a global ``TRACE_RETENTION_DAYS`` override, it
    wins for every org (self-hosted convenience). Otherwise the tier
    catalog + any per-org ``custom_retention_days`` on the license token
    is used.
    """
    if override_days is not None:
        return override_days
    return QuotaRegistry.get_policy(org).retention_days


def _sweep_organization(
    org: Organization,
    cutoff: datetime,
    *,
    dry_run: bool,
) -> int:
    """Delete (or count) this org's trace rows past *cutoff*.

    Returns the number of rows deleted (or that would be deleted in
    dry-run mode).
    """
    db = SessionLocal()
    try:
        bind_scope_to_session(db, str(org.id))
        with bypass_tenant_filter():
            query = db.query(Trace).filter(
                Trace.organization_id == str(org.id),
                Trace.created_at < cutoff,
            )
            if dry_run:
                count = query.count()
            else:
                count = query.delete(synchronize_session=False)
                db.commit()
        return count
    except Exception:
        db.rollback()
        logger.exception("Trace retention sweep failed for organization %s", org.id)
        return 0
    finally:
        db.close()


@app.task(bind=True)
def sweep_expired_traces(self) -> dict:
    """Delete trace rows past each org's retention window, org by org."""
    settings = get_trace_retention_settings()
    if not settings.enabled:
        logger.debug("Trace retention sweep disabled (TRACE_RETENTION_ENABLED=false); skipping")
        return {"enabled": False}

    now = datetime.now(timezone.utc)
    total_deleted = 0
    orgs_swept = 0

    db = SessionLocal()
    try:
        all_orgs = db.query(Organization).all()
    finally:
        db.close()

    for org in all_orgs:
        try:
            retention_days = _resolve_retention_days(org, settings.override_days)
            if retention_days is None:
                continue

            cutoff = now - timedelta(days=retention_days)
            count = _sweep_organization(org, cutoff, dry_run=settings.dry_run)
            if count > 0:
                logger.info(
                    "Trace retention %s: org=%s retention=%dd cutoff=%s rows=%d",
                    "dry-run" if settings.dry_run else "deleted",
                    org.id,
                    retention_days,
                    cutoff.isoformat(),
                    count,
                )
                total_deleted += count
                orgs_swept += 1
        except Exception:
            logger.exception("Unexpected error sweeping organization %s", org.id)
            continue

    logger.info(
        "Trace retention sweep complete (%s): %d row(s) across %d org(s)",
        "dry-run" if settings.dry_run else "live",
        total_deleted,
        orgs_swept,
    )
    return {
        "enabled": True,
        "dry_run": settings.dry_run,
        "traces_affected": total_deleted,
        "orgs_swept": orgs_swept,
    }
