"""What happens after a scheduled run, and the notifications a schedule sends."""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.auth.principal import resolve_principal
from rhesis.backend.app.auth.rbac import authorize
from rhesis.backend.app.crud.test_configuration import get_schedule, set_schedule
from rhesis.backend.app.crud.user import get_organization_users
from rhesis.backend.app.models.enums import NotificationEventType
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.services.notification.catalog import RenderedNotification
from rhesis.backend.app.services.notification.service import notify
from rhesis.backend.app.services.test_run_schedule.service import (
    PAUSED,
    schedule_of,
    status_of,
)

logger = logging.getLogger(__name__)

# Failed runs in a row before the schedule pauses itself.
FAILURE_STREAK_LIMIT = 5

PROBLEM_STATUSES = {"Failed", "Partial"}

PAUSE_REASONS = {
    "endpoint_missing": "the endpoint was deleted",
    "test_set_missing": "the test set was deleted",
    "test_set_empty": "the test set has no tests",
    "model_unavailable": "a model its runs need isn't available",
    "failure_streak": f"its last {FAILURE_STREAK_LIMIT} runs failed",
    "creator_access": "its owner can no longer run tests here",
}


def schedule_link(config_id) -> str:
    return f"/test-runs?tab=schedules&schedule={config_id}"


# --- after a run ------------------------------------------------------------------------------


def record_run_outcome(
    db: Session, test_run: TestRun, summary: dict[str, Any]
) -> dict[str, Any] | None:
    """Update the schedule after one of its runs and decide whether to notify.

    Returns keys to merge into the run's result (``notify``, ``schedule_name``, ...), or
    ``None`` for a run no schedule started, which keeps today's behaviour exactly.
    """
    attributes = test_run.attributes or {}
    if attributes.get("trigger") != "schedule":
        return None
    config = get_schedule(db, test_run.test_configuration_id, for_update=True)
    if config is None:  # deleted since the run started
        return None
    schedule = schedule_of(config)
    status = attributes.get("status") or summary.get("execution_status")
    total = summary.get("total_tests") or 0
    pass_rate = (summary.get("tests_passed", 0) / total) if total else None

    previous_rate = schedule.get("last_pass_rate")
    dropped = pass_rate is not None and previous_rate is not None and pass_rate < previous_rate
    problem = status in PROBLEM_STATUSES or dropped
    first_run = not schedule.get("first_run_notified")

    streak = schedule.get("failure_streak") or 0
    schedule["failure_streak"] = streak + 1 if status == "Failed" else 0
    schedule["last_pass_rate"] = pass_rate
    schedule["quota_skip_notified"] = False
    notify_setting = schedule.get("notify") or "problems"
    if first_run and notify_setting != "never":
        schedule["first_run_notified"] = True

    state = status_of(config)
    paused_now = schedule["failure_streak"] >= FAILURE_STREAK_LIMIT and state != PAUSED
    if paused_now:
        schedule["paused_reason"] = "failure_streak"
        state = PAUSED
    set_schedule(db, config, schedule, state)
    db.commit()
    if paused_now:
        notify_paused(db, config, "failure_streak")

    wanted = notify_setting == "always" or (notify_setting == "problems" and problem)
    name = schedule.get("name") or "Scheduled run"
    return {
        "notify": notify_setting != "never" and (wanted or first_run),
        "schedule_name": name,
        "schedule_title": _run_title(name, status, pass_rate, previous_rate, first_run, dropped),
        "schedule_problem": problem,
        # The email subject reads task_name.
        "task_name": name,
    }


def _percent(rate: float | None) -> str:
    return f"{round(rate * 100)}%" if rate is not None else "no"


def _run_title(name, status, rate, previous, first_run, dropped) -> str:
    if first_run:
        return f"{name} ran for the first time · {_percent(rate)} pass"
    if status == "Failed":
        return f"{name} failed"
    if dropped:
        return f"{name} pass rate dropped to {_percent(rate)} (was {_percent(previous)})"
    return f"{name} finished · {_percent(rate)} pass"


# --- notifications ----------------------------------------------------------------------------


def _send(
    db: Session,
    config: TestConfiguration,
    event_type: NotificationEventType.TestRunSchedule,
    title: str,
    user_id,
    *,
    is_failure: bool = True,
    **payload,
) -> None:
    schedule = schedule_of(config)
    try:
        notify(
            db,
            event_type=event_type,
            rendered=RenderedNotification(
                title=title,
                is_failure=is_failure,
                payload={
                    "schedule_id": str(config.id),
                    "schedule_name": schedule.get("name"),
                    "link": schedule_link(config.id),
                    **payload,
                },
            ),
            user_id=str(user_id),
            organization_id=str(config.organization_id),
            project_id=str(config.project_id) if config.project_id else None,
        )
    except Exception:
        # A notification must never stop the dispatcher.
        logger.exception("Could not send %s for schedule %s", event_type, config.id)


def notify_paused(db: Session, config: TestConfiguration, reason: str) -> None:
    name = schedule_of(config).get("name")
    why = PAUSE_REASONS.get(reason, "it could not run")
    _send(
        db,
        config,
        NotificationEventType.TestRunSchedule.PAUSED,
        f"{name} paused: {why}",
        config.user_id,
        reason=reason,
    )


def notify_missed(db: Session, config: TestConfiguration, occurrence: datetime) -> None:
    name = schedule_of(config).get("name")
    _send(
        db,
        config,
        NotificationEventType.TestRunSchedule.MISSED,
        f"{name} didn't run because the scheduler was unavailable",
        config.user_id,
        reason="missed",
        occurrence=occurrence.isoformat(),
    )


def notify_quota_once(db: Session, config: TestConfiguration, schedule: dict) -> None:
    """Once per streak of quota skips; a run that goes through resets it."""
    if schedule.get("quota_skip_notified"):
        return
    schedule["quota_skip_notified"] = True
    _send(
        db,
        config,
        NotificationEventType.TestRunSchedule.SKIPPED,
        f"{schedule.get('name')} skipped: your organization reached its test execution limit",
        config.user_id,
        is_failure=False,
        reason="quota",
    )


def notify_needs_owner(db: Session, config: TestConfiguration, creator_name: str) -> None:
    """Tell everyone who could take the schedule over. Not the creator: they can't."""
    name = schedule_of(config).get("name")
    title = f"{name} needs a new owner: {creator_name} can no longer run tests here"
    for user_id in editor_ids(db, config):
        _send(
            db,
            config,
            NotificationEventType.TestRunSchedule.NEEDS_OWNER,
            title,
            user_id,
            reason="creator_access",
        )


def editor_ids(db: Session, config: TestConfiguration) -> list:
    """Active members of the organization who can change test runs in the project."""
    return [
        user.id
        for user in get_organization_users(db, str(config.organization_id))
        if user.id != config.user_id
        and authorize(
            resolve_principal(user),
            Permission.TestRun.UPDATE,
            project_id=config.project_id,
            db=db,
        )
    ]
