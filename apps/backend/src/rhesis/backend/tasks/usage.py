"""Celery task that performs usage accrual off the caller's path.

One task for every :class:`QuotaResource`, not one per resource: the work
is identical in each case (bind tenant scope, upsert a counter), only the
resource name and amount differ. Always reached via
``app.services.usage.dispatch_accrual`` -- see that function for why
accrual is queued rather than written inline by its callers.
"""

import logging

from rhesis.backend.app.database import SessionLocal, bind_scope_to_session
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.services.usage import increment_usage
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=30)
def accrue_usage(self, organization_id: str, resource: str, amount: int) -> None:
    """Add *amount* to *organization_id*'s counter for *resource*.

    *resource* arrives as a plain string because task arguments are JSON
    over the broker; it is converted back to :class:`QuotaResource` here so
    an unknown value fails loudly instead of quietly creating a counter
    nobody reads. That conversion sits outside the retry block on purpose:
    a bad resource name is a programming error, and retrying it three times
    will not make it a good one.
    """
    quota_resource = QuotaResource(resource)

    db = SessionLocal()
    try:
        # This task owns its session for its whole lifetime, so scope is
        # bound onto it directly rather than through a request-scoped
        # context manager. Required, not merely tidy: the `usage` table's
        # FORCE'd `tenant_isolation` RLS policy rejects the upsert outright
        # when `app.current_organization` is unset.
        bind_scope_to_session(db, organization_id)
        increment_usage(db, organization_id, quota_resource, amount)
    except Exception as e:
        logger.warning(
            "Failed to accrue %s usage (amount=%s) for org %s",
            resource,
            amount,
            organization_id,
            exc_info=True,
        )
        raise self.retry(exc=e)
    finally:
        db.close()
