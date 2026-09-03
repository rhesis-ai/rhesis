"""The broker's visibility timeout must outlast the longest task.

With ``task_acks_late`` the message is only acknowledged once the task
finishes. If a task can still be running when Redis decides the message was
never picked up, Redis hands the *same* message to a second worker while the
first is mid-run. Nothing guards against that duplicate -- a run already in
Progress is re-executed from the first test -- and progress is stored as an
absolute value keyed by ``celery_task_id``, which a redelivery reuses, so the
second pass drags the counter backwards over the first.

kombu's default is 3600s, which was shorter than the 3900s hard limit on
execute_test_configuration. This pins the ordering so the two cannot drift
apart again.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/jobs/test_celery_timeouts.py -v
"""

from rhesis.backend.celery.config import CELERY_CONFIG


def _longest_hard_limit() -> int:
    limits = [
        opts["time_limit"]
        for opts in CELERY_CONFIG.get("task_annotations", {}).values()
        if "time_limit" in opts
    ]
    assert limits, "expected at least one annotated time_limit"
    return max(limits)


def test_visibility_timeout_is_set_explicitly():
    """Relying on kombu's default is what caused the inversion."""
    assert "visibility_timeout" in CELERY_CONFIG["broker_transport_options"]


def test_visibility_timeout_outlasts_the_longest_task():
    visibility = CELERY_CONFIG["broker_transport_options"]["visibility_timeout"]
    assert visibility > _longest_hard_limit()


def test_acks_late_is_on():
    """The invariant above only matters because of this; if it ever goes
    off, the reasoning in this file needs revisiting rather than deleting."""
    assert CELERY_CONFIG["task_acks_late"] is True


def test_soft_limits_stay_below_their_hard_limits():
    for name, opts in CELERY_CONFIG.get("task_annotations", {}).items():
        if "soft_time_limit" in opts and "time_limit" in opts:
            assert opts["soft_time_limit"] < opts["time_limit"], name
