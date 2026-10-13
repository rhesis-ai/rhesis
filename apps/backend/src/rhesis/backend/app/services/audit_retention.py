"""How long each org keeps its audit log, and the purge that enforces it.

The org picks a window (``audit_log.retention_days`` in its settings, 1 year
by default). ``QuotaPolicy.retention_days``, the plan's retention, caps it.
A deleted org keeps the window it had when it was deleted
(``retention_days_at_deletion``), so its rows go when that ends, whatever its
licence does afterwards. An org that lost the feature is purged on its stored
choice, so rows recorded while it had the feature do not stay forever.

The purge cuts on ``recorded_at``, the column later integrity checkpoints seal.

The same daily job deletes old export files, through the cleanup the EE
package registers with ``register_export_cleanup``: core does not know where
exports are stored.
"""

from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.audit_event import has_audit_events_before, purge_audit_events
from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import QuotaRegistry
from rhesis.backend.events.correlation import resolve_ids

MIN_RETENTION_DAYS = 90
MAX_RETENTION_DAYS = 3650
# EU AI Act Art. 19 and 26 ask deployers of high-risk systems for at least six
# months of logs. Shown as a warning; not a floor.
EU_AI_ACT_MIN_DAYS = 183

#: ``(db, org, now) -> files deleted``; ``db`` is scoped to the org.
ExportCleanup = Callable[[Session, Organization, datetime], int]
_export_cleanup: Optional[ExportCleanup] = None


def register_export_cleanup(cleanup: ExportCleanup) -> None:
    global _export_cleanup
    _export_cleanup = cleanup


def export_cleanup() -> Optional[ExportCleanup]:
    return _export_cleanup


def max_retention_days(org: Organization) -> int:
    cap = QuotaRegistry.get_policy(org).retention_days
    return MAX_RETENTION_DAYS if cap is None else min(cap, MAX_RETENTION_DAYS)


def retention_days(org: Organization) -> int:
    """The window in force: the org's choice, capped by its plan."""
    return min(org.settings.audit_log.retention_days, max_retention_days(org))


def purge_retention_days(org: Organization) -> int:
    """The window the purge applies to ``org``.

    An org that lost the feature keeps its stored choice, uncapped: with no
    licence there is no plan to cap it, and its rows must still go.
    """
    snapshot = org.settings.audit_log.retention_days_at_deletion
    if org.deleted_at is not None and snapshot:
        return snapshot
    if FeatureRegistry.is_available(FeatureName.AUDIT_LOG, org):
        return retention_days(org)
    return org.settings.audit_log.retention_days


def purge_expired_audit_events(db: Session, org: Organization, now: datetime) -> int:
    """Purge ``org``'s rows older than its window; returns the count.

    Calls the purge function only when a row has expired, so a run with nothing
    to do writes no ``audit_log.purged`` row. ``db`` must be scoped to the org.
    """
    cutoff = now - timedelta(days=purge_retention_days(org))
    if not has_audit_events_before(db, org.id, cutoff):
        return 0
    trace_id, span_id = resolve_ids()
    return purge_audit_events(db, org.id, cutoff, trace_id, span_id)
