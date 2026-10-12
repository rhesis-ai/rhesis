"""Liveness signal for the Celery beat scheduler.

Beat queues ``beat_heartbeat`` every few minutes (``beat_schedule`` in
``celery/config.py``) and a worker runs it, so its log line only appears while
beat, the broker and a worker are all up. The "Celery beat heartbeat missing"
Grafana alert (kubernetes/base/grafana-resources/beat-alerts.yaml) counts these
lines in Loki and fires when they stop. Change ``HEARTBEAT_MESSAGE`` and that
alert's query together.
"""

import logging
from datetime import datetime, timezone

from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)

HEARTBEAT_MESSAGE = "Celery beat heartbeat"


@app.task(ignore_result=True)
def beat_heartbeat() -> str:
    """Log the heartbeat with the time it ran. Returns that time for tests."""
    ran_at = datetime.now(timezone.utc).isoformat()
    logger.info("%s at %s", HEARTBEAT_MESSAGE, ran_at)
    return ran_at
