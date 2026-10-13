"""Liveness signal for the Celery beat scheduler.

Beat queues ``beat_heartbeat`` every few minutes (``beat_schedule`` in
``celery/config.py``) and a worker runs it, so its log line only appears while
beat, the broker and a worker are all up. The "Celery beat heartbeat missing"
Grafana alert (kubernetes/base/grafana-resources/beat-alerts.yaml) counts these
lines in Loki and fires when they stop. Change ``HEARTBEAT_MESSAGE`` and that
alert's query together. It also sets a Redis key the API reads
(``app/services/beat_heartbeat.py``), so the audit log settings can say when
scheduled jobs are not running.
"""

import logging
from datetime import datetime, timezone

from rhesis.backend.app.services.beat_heartbeat import beat_signal
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)

HEARTBEAT_MESSAGE = "Celery beat heartbeat"


@app.task(ignore_result=True)
def beat_heartbeat() -> str:
    """Log the heartbeat with the time it ran, and tell the API (``beat_signal``).

    Returns that time for tests.
    """
    ran_at = datetime.now(timezone.utc).isoformat()
    logger.info("%s at %s", HEARTBEAT_MESSAGE, ran_at)
    beat_signal.record(ran_at)
    return ran_at
