"""Settling the quota a route reserved for a job, at most once per job.

The reservation lives on the job row (``job.quota_reservation``). Every path that
ends a job settles it through :func:`settle_job_reservation`: success with the
real count, a permanent failure or a revoke with zero. One guarded update marks it
settled in the same transaction that gives the unused part back, so a redelivered,
retried or revoked job can never settle twice.
"""

import enum
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class Settled(enum.Enum):
    NOW = "now"  # this call settled it
    ALREADY = "already"  # an earlier run, a failure hook or a revoke did
    NO_ROW = "no_row"  # no job row holds a reservation for this task


def settle_job_reservation(
    celery_task_id: Optional[str],
    tenant: Tuple[Optional[str], Optional[str], Optional[str]],
    consumed: int,
) -> Settled:
    """Settle the reservation on this task's job row with *consumed* units, once."""
    from rhesis.backend.app.crud.job import claim_quota_reservation, has_quota_reservation
    from rhesis.backend.app.database import get_db_with_tenant_variables
    from rhesis.backend.app.quota.enforcement import QuotaReservation

    if not celery_task_id:
        return Settled.NO_ROW
    org_id, user_id, project_id = tenant
    with get_db_with_tenant_variables(org_id or "", user_id or "", project_id or "") as db:
        claimed = claim_quota_reservation(db, celery_task_id)
        if claimed is None:
            db.rollback()
            if has_quota_reservation(db, celery_task_id):
                return Settled.ALREADY
            return Settled.NO_ROW
        # Same transaction as the claim: if giving it back fails, so does the claim.
        QuotaReservation.from_wire(claimed).apply(db, consumed)
        db.commit()
        return Settled.NOW
