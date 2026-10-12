"""jobs/heartbeat.py and the beat schedule it sits on.

The heartbeat is only useful if three things line up: beat schedules a task name
the worker actually has, the task logs its message, and the Grafana alert looks
for that same message in Loki. A drift in any of them silences the alert while
beat is down, so each is pinned here.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/jobs/test_beat_heartbeat.py -v
"""

import logging
from datetime import datetime, timedelta, timezone

from rhesis.backend.celery.config import CELERY_CONFIG
from rhesis.backend.celery.core import app
from rhesis.backend.jobs.heartbeat import HEARTBEAT_MESSAGE, beat_heartbeat


def test_heartbeat_logs_message_with_time(caplog):
    with caplog.at_level(logging.INFO, logger="rhesis.backend.jobs.heartbeat"):
        ran_at = beat_heartbeat()

    ran_at_dt = datetime.fromisoformat(ran_at)
    assert abs(datetime.now(timezone.utc) - ran_at_dt) < timedelta(minutes=1)
    assert [r.getMessage() for r in caplog.records] == [f"{HEARTBEAT_MESSAGE} at {ran_at}"]


def test_heartbeat_is_on_the_beat_schedule():
    entry = CELERY_CONFIG["beat_schedule"]["beat-heartbeat"]
    assert entry["task"] == beat_heartbeat.name
    # The alert counts heartbeats over 20 minutes; keep several inside that window.
    assert entry["schedule"] <= 5 * 60


def test_every_scheduled_task_is_registered():
    # Beat sends tasks by name, and a worker drops a name it never registered.
    # Workers only load the modules in `include`, so the module must be listed
    # there; this file importing it would hide a missing entry.
    app.loader.import_default_modules()
    for name, entry in CELERY_CONFIG["beat_schedule"].items():
        module = entry["task"].rsplit(".", 1)[0]
        assert module in CELERY_CONFIG["include"], f"{name}: {module} is not in include"
        assert entry["task"] in app.tasks, f"{name}: {entry['task']} is not a registered task"
