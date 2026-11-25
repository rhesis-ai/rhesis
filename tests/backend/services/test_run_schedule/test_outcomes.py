"""After a scheduled run: failure streak, notify setting, first-run notice, who hears about it."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app import models
from rhesis.backend.app.crud.test_configuration import set_schedule
from rhesis.backend.app.schemas.test_run_schedule import ScheduleSpecIn
from rhesis.backend.app.services.notification.catalog import NOTIFICATION_CATALOG
from rhesis.backend.app.services.test_run_schedule import outcomes, service
from rhesis.backend.jobs.base import _wants_notification

_NOTIFY = "rhesis.backend.app.services.test_run_schedule.outcomes.notify"


@pytest.fixture
def config(test_db, authenticated_user, schedule_test_set, schedule_endpoint):
    created = service.create_schedule(
        test_db,
        authenticated_user,
        test_set_id=schedule_test_set.id,
        endpoint_id=schedule_endpoint.id,
        spec=ScheduleSpecIn(name="Weekday regression", cron="0 9 * * 1-5"),
    )
    test_db.commit()
    return created


def _run(config, status, trigger="schedule"):
    return MagicMock(
        test_configuration_id=config.id, attributes={"trigger": trigger, "status": status}
    )


def _summary(passed, total):
    return {"tests_passed": passed, "total_tests": total}


def _set(test_db, config, **changes):
    schedule = service.schedule_of(config) | changes
    set_schedule(test_db, config, schedule, service.status_of(config))
    test_db.commit()


class TestRecordRunOutcome:
    def test_a_manual_run_changes_nothing(self, test_db, config):
        assert outcomes.record_run_outcome(test_db, _run(config, "Completed", "manual"), {}) is None

    def test_first_clean_run_notifies_once(self, test_db, config):
        first = outcomes.record_run_outcome(test_db, _run(config, "Completed"), _summary(23, 25))
        assert first["notify"] is True
        assert first["schedule_title"] == "Weekday regression ran for the first time · 92% pass"
        second = outcomes.record_run_outcome(test_db, _run(config, "Completed"), _summary(23, 25))
        assert second["notify"] is False

    def test_never_sends_nothing_not_even_the_first_run(self, test_db, config):
        _set(test_db, config, notify="never")
        outcome = outcomes.record_run_outcome(test_db, _run(config, "Failed"), _summary(0, 5))
        assert outcome["notify"] is False

    @pytest.mark.parametrize("status", ["Failed", "Partial"])
    def test_problems_notify(self, test_db, config, status):
        _set(test_db, config, first_run_notified=True)
        outcome = outcomes.record_run_outcome(test_db, _run(config, status), _summary(1, 5))
        assert outcome["notify"] is True
        assert outcome["schedule_problem"] is True

    def test_a_drop_in_pass_rate_notifies(self, test_db, config):
        _set(test_db, config, first_run_notified=True, last_pass_rate=0.92)
        outcome = outcomes.record_run_outcome(test_db, _run(config, "Completed"), _summary(39, 50))
        assert outcome["notify"] is True
        assert outcome["schedule_title"] == (
            "Weekday regression pass rate dropped to 78% (was 92%)"
        )

    def test_always_notifies_a_clean_run(self, test_db, config):
        _set(test_db, config, first_run_notified=True, notify="always")
        outcome = outcomes.record_run_outcome(test_db, _run(config, "Completed"), _summary(5, 5))
        assert outcome["notify"] is True
        assert outcome["task_name"] == "Weekday regression"

    def test_five_failures_in_a_row_pause_the_schedule(self, test_db, config):
        _set(test_db, config, first_run_notified=True)
        with patch(_NOTIFY) as notify:
            for _ in range(outcomes.FAILURE_STREAK_LIMIT):
                outcomes.record_run_outcome(test_db, _run(config, "Failed"), _summary(0, 5))
        assert service.status_of(config) == service.PAUSED
        assert service.schedule_of(config)["paused_reason"] == "failure_streak"
        assert notify.call_count == 1
        assert "last 5 runs failed" in notify.call_args.kwargs["rendered"].title

    def test_a_success_resets_the_streak(self, test_db, config):
        _set(test_db, config, first_run_notified=True, failure_streak=4)
        outcomes.record_run_outcome(test_db, _run(config, "Completed"), _summary(5, 5))
        assert service.schedule_of(config)["failure_streak"] == 0


class TestNotifications:
    def test_needs_owner_goes_to_editors_not_the_creator(self, test_db, config, test_org_id):
        editor = models.User(
            email=f"e-{uuid.uuid4().hex[:6]}@example.com", organization_id=uuid.UUID(test_org_id)
        )
        test_db.add(editor)
        test_db.flush()
        with (
            patch(
                "rhesis.backend.app.services.test_run_schedule.outcomes.authorize",
                return_value=True,
            ),
            patch(_NOTIFY) as notify,
        ):
            outcomes.notify_needs_owner(test_db, config, "Alex Morgan")
        recipients = {call.kwargs["user_id"] for call in notify.call_args_list}
        assert str(editor.id) in recipients
        assert str(config.user_id) not in recipients
        rendered = notify.call_args.kwargs["rendered"]
        assert rendered.title == (
            "Weekday regression needs a new owner: Alex Morgan can no longer run tests here"
        )
        assert rendered.payload["link"] == f"/test-runs?tab=schedules&schedule={config.id}"

    def test_quota_skip_notifies_once_per_streak(self, test_db, config):
        schedule = service.schedule_of(config)
        with patch(_NOTIFY) as notify:
            outcomes.notify_quota_once(test_db, config, schedule)
            outcomes.notify_quota_once(test_db, config, schedule)
        assert notify.call_count == 1

    def test_every_schedule_kind_is_in_the_catalog(self):
        for kind in (
            "test_run_schedule.paused",
            "test_run_schedule.missed",
            "test_run_schedule.skipped",
            "test_run_schedule.needs_owner",
        ):
            assert kind in NOTIFICATION_CATALOG


class TestCompletionGate:
    def test_only_an_explicit_false_silences(self):
        assert _wants_notification({"notify": False}) is False
        assert _wants_notification({"notify": True}) is True
        assert _wants_notification({}) is True
        assert _wants_notification(None) is True

    def test_renderer_uses_the_schedule_title_or_stays_quiet(self):
        render = NOTIFICATION_CATALOG["test_run.execution_completed"].render
        task = MagicMock()
        task.request.headers = {}
        assert render(task, {"notify": False, "test_run_id": "r"}, None) is None
        rendered = render(
            task,
            {"schedule_name": "Smoke", "schedule_title": "Smoke failed", "schedule_problem": True},
            None,
        )
        assert rendered.title == "Smoke failed"
        assert rendered.is_failure is True
        manual = render(task, {"test_set_name": "Set", "tests_passed": 1}, None)
        assert manual.title == '"Set" finished'
