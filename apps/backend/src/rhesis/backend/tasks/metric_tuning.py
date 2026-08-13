"""Background task for a tuning run.

Orchestration only -- everything it does lives in
``app/services/metric_tuning/runs.py``, so the run can be exercised without a
broker. The task exists because a set of thirty cases is thirty LLM calls, which
is not something to hold a browser open for.
"""

import logging
import uuid

from rhesis.backend.app.crud.metric import get_metric
from rhesis.backend.app.services import metric_tuning as service
from rhesis.backend.celery.core import app
from rhesis.backend.tasks.base import BaseTask

logger = logging.getLogger(__name__)


@app.task(
    base=BaseTask,
    name="rhesis.backend.tasks.run_metric_tuning",
    bind=True,
    display_name="Metric Tuning Run",
    # A run costs one LLM call per case, so a retry is a second bill for the
    # same work. The run marks itself failed instead and the author presses
    # again if they want it.
    autoretry_for=(),
    max_retries=0,
)
def run_metric_tuning(self, metric_id: str):
    """Run a metric over every one of its tuning cases."""
    org_id, user_id, _ = self.get_tenant_context()
    metric_uuid = uuid.UUID(metric_id)

    self.log_with_context("info", "Starting tuning run", metric_id=metric_id)

    with self.get_db_session() as db:
        metric = get_metric(db, metric_id=metric_uuid, organization_id=org_id, user_id=user_id)
        if metric is None:
            # Nothing to mark failed -- without the metric there is no way to
            # reach its tuning set either.
            self.log_with_context("error", "Tuning run: metric not found", metric_id=metric_id)
            return {"metric_id": metric_id, "status": "failed", "error": "Metric not found"}

        try:
            summary = service.execute_tuning_run(db, metric, org_id)
        except Exception as e:
            self.log_with_context("error", "Tuning run failed", metric_id=metric_id, error=str(e))
            # Leaving the run marked `running` would both look like progress and
            # block the next attempt, so the failure is recorded before it is
            # re-raised.
            db.rollback()
            service.fail_tuning_run(db, metric, org_id, str(e))
            raise

    self.log_with_context(
        "info",
        "Tuning run complete",
        metric_id=metric_id,
        completed_cases=summary.completed_cases,
        errored_cases=summary.errored_cases,
    )
    return {
        "metric_id": metric_id,
        "status": summary.status.value,
        "total_cases": summary.total_cases,
        "completed_cases": summary.completed_cases,
        "errored_cases": summary.errored_cases,
    }
