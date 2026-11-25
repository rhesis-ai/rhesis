"""Beat job: start the test runs whose schedule is due. Runs every minute.

Orchestration only; the claim and submit logic is in
``app/services/test_run_schedule/dispatch.py``. Walks organizations one by one,
since RLS hides every other tenant's schedules from a session bound to one.
"""

import logging
from collections import Counter
from datetime import datetime, timezone

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.services.test_run_schedule.dispatch import (
    all_organization_ids,
    due_in_org,
    fire_due_schedule,
)
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)


@app.task(bind=True)
def dispatch_due_schedules(self) -> dict:
    """Fire every due schedule once. Off when SCHEDULE_DISPATCH_ENABLED is false."""
    if not get_application_settings().schedule_dispatch_enabled:
        logger.debug("Schedule dispatch disabled (SCHEDULE_DISPATCH_ENABLED=false); skipping")
        return {"enabled": False}
    now = datetime.now(timezone.utc)
    counts: Counter = Counter()
    for organization_id in all_organization_ids():
        # One organization's trouble never costs the others their runs.
        try:
            for config_id, project_id in due_in_org(organization_id, now):
                counts["due"] += 1
                counts[fire_due_schedule(config_id, organization_id, project_id, now).value] += 1
        except Exception:
            logger.exception("Schedule dispatch failed for organization %s", organization_id)
            counts["org_errors"] += 1
    if counts:
        logger.info("Schedule dispatch: %s", dict(counts), extra=dict(counts))
    return dict(counts)
