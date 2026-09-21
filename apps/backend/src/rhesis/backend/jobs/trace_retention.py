"""Hard-deletes trace (span) rows past each org's tier retention window.

Disabled by default (``TRACE_RETENTION_ENABLED``), and defaults to dry-run
when first enabled (``TRACE_RETENTION_DRY_RUN``) so the blast radius is
visible in logs before anything is actually deleted.

Retention days come from the org's resolved ``QuotaPolicy.retention_days``
(tier catalog + any per-org ``custom_retention_days`` override on the
license token). ``TRACE_RETENTION_DAYS`` overrides the tier value for all
orgs when set (useful for self-hosted deployments without the EE tier
system). An org whose resolved retention is ``None`` (unlimited) is skipped.

That last rule is what makes ``TRACE_RETENTION_DAYS`` the operative knob off
Rhesis cloud: with ``USAGE_QUOTAS_ENABLED`` false (the default), every policy
resolves unlimited and so carries ``retention_days=None``, meaning enabling
the sweep on its own deletes nothing. Set the override too, or leave quotas on.

Each org is swept in its own session and transaction, same pattern as
``jobs/retention.py``. See that module's docstring for the rationale on
explicit ``organization_id`` filters, ``bind_scope_to_session`` for RLS
GUCs, and per-org error isolation.
"""

import logging
from datetime import datetime, timedelta, timezone

from rhesis.backend.app.config.settings import get_trace_retention_settings
from rhesis.backend.app.database import (
    SessionLocal,
    bind_scope_to_session,
    temporary_project_scope,
)
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.quota import QuotaRegistry
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)

#: Rows deleted per transaction. The first live run on an org with a long
#: ingest history would otherwise delete its whole backlog in one statement,
#: holding row locks and writing one large WAL burst for as long as that
#: takes. Batching bounds both, at the cost of the sweep no longer being
#: atomic per org -- which is fine here: a partial sweep just leaves rows for
#: the next run, and the cutoff is recomputed from scratch each time.
DELETE_BATCH_SIZE = 5_000


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


def _expired_traces(db, org: Organization, cutoff: datetime, project_id):
    """Query for *org*'s trace rows older than *cutoff* within one project.

    A ``project_id`` of ``None`` selects the traces that carry no project.

    The explicit ``organization_id`` predicate is what keeps the sweep
    inside this org -- do not remove it. It is load-bearing rather than
    belt-and-braces because callers run this under
    :func:`~rhesis.backend.app.scope.bypass_tenant_filter`, so the ORM
    auto-filter adds nothing of its own.
    """
    query = db.query(Trace).filter(
        Trace.organization_id == str(org.id),
        Trace.created_at < cutoff,
    )
    if project_id is None:
        return query.filter(Trace.project_id.is_(None))
    return query.filter(Trace.project_id == project_id)


def _delete_in_batches(db, org: Organization, cutoff: datetime, project_id) -> int:
    """Delete *org*'s expired traces in :data:`DELETE_BATCH_SIZE` chunks.

    Returns the total number of rows deleted. Commits per batch, so a
    failure part-way leaves the batches that already landed deleted and
    the rest for the next run.

    Selects primary keys first, then deletes by id: Postgres has no
    ``DELETE ... LIMIT``, and this keeps each statement's row count bounded
    without a correlated subquery.
    """
    total = 0
    while True:
        batch = (
            _expired_traces(db, org, cutoff, project_id)
            .with_entities(Trace.id)
            .limit(DELETE_BATCH_SIZE)
        )
        ids = [row[0] for row in batch]
        if not ids:
            break

        db.query(Trace).filter(Trace.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        total += len(ids)

        # A short batch means the table had fewer than a full batch left,
        # so there is nothing to come back for.
        if len(ids) < DELETE_BATCH_SIZE:
            break
    return total


def _sweep_scope(db, org: Organization, cutoff: datetime, project_id, *, dry_run: bool) -> int:
    """Count or delete one project's expired traces, under the caller's scope."""
    if dry_run:
        return _expired_traces(db, org, cutoff, project_id).count()
    return _delete_in_batches(db, org, cutoff, project_id)


def _sweep_organization(
    org: Organization,
    cutoff: datetime,
    *,
    dry_run: bool,
) -> int | None:
    """Delete (or count) this org's trace rows past *cutoff*.

    Returns the number of rows deleted (or that would be deleted in
    dry-run mode), or ``None`` if the sweep failed for this org.

    ``None`` rather than ``0`` on failure so the caller can tell "nothing
    to delete" apart from "the delete blew up"; both used to report zero,
    which made a run where every org errored indistinguishable from a
    clean one.

    Runs under ``bypass_tenant_filter``: the session's scope has no
    project, so the ORM auto-filter would otherwise add
    ``project_id IS NULL`` and match no traces at all.

    Swept one project at a time because ``project_isolation`` is a
    RESTRICTIVE policy: a session holding an org but no project matches
    none of that org's project-scoped traces, so a single org-wide pass
    deletes nothing and still reports success. ``bypass_tenant_filter``
    does not rescue this -- it drops the ORM's WHERE clause, not the
    database's policy.
    """
    db = SessionLocal()
    try:
        bind_scope_to_session(db, str(org.id))
        with bypass_tenant_filter():
            project_ids = [
                row[0]
                for row in db.query(Project.id).filter(Project.organization_id == str(org.id))
            ]

            total = 0
            for project_id in project_ids:
                with temporary_project_scope(db, str(org.id), "", str(project_id)):
                    total += _sweep_scope(db, org, cutoff, project_id, dry_run=dry_run)

            # Traces carrying no project satisfy project_isolation whatever
            # the project GUC holds, so this pass needs no scope shift.
            total += _sweep_scope(db, org, cutoff, None, dry_run=dry_run)
            return total
    except Exception:
        db.rollback()
        logger.exception("Trace retention sweep failed for organization %s", org.id)
        return None
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
    orgs_failed = 0

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
            if count is None:
                orgs_failed += 1
                continue
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
            orgs_failed += 1
            continue

    logger.info(
        "Trace retention sweep complete (%s): %d row(s) across %d org(s), %d failed",
        "dry-run" if settings.dry_run else "live",
        total_deleted,
        orgs_swept,
        orgs_failed,
    )
    return {
        "enabled": True,
        "dry_run": settings.dry_run,
        "traces_affected": total_deleted,
        "orgs_swept": orgs_swept,
        "orgs_failed": orgs_failed,
    }
