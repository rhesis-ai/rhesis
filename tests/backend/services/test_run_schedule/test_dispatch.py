"""The Beat dispatcher: claim, fire once, skip, pause, and the kill switch."""

import contextlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app import models
from rhesis.backend.app.crud.test_configuration import set_schedule
from rhesis.backend.app.database import bind_scope_to_session
from rhesis.backend.app.quota.enforcement import QuotaExceededError
from rhesis.backend.app.schemas.test_run_schedule import ScheduleSpecIn
from rhesis.backend.app.services.test_run_schedule import dispatch, service, timing
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.app.utils.model_errors import ModelNotConfiguredError

_DISPATCH = "rhesis.backend.app.services.test_run_schedule.dispatch"
_OUTCOMES = "rhesis.backend.app.services.test_run_schedule.outcomes"


@pytest.fixture(autouse=True)
def sessions(test_db):
    """The dispatcher's own sessions become the test session, bound as it asks."""

    @contextlib.contextmanager
    def _session(organization_id="", user_id="", project_id=""):
        bind_scope_to_session(test_db, organization_id, user_id, project_id)
        yield test_db

    with patch(f"{_DISPATCH}.get_db_with_tenant_variables", _session):
        yield


@pytest.fixture
def launched():
    with (
        patch("rhesis.backend.jobs.execution.run.plan_run_for_user", return_value=None) as plan,
        patch("rhesis.backend.jobs.launch_job", return_value=MagicMock(id="task")) as launch,
    ):
        yield launch, plan


@pytest.fixture
def make(test_db, authenticated_user, schedule_test_set, schedule_endpoint):
    def _make(spec=None, due_minutes_ago=1):
        config = service.create_schedule(
            test_db,
            authenticated_user,
            test_set_id=schedule_test_set.id,
            endpoint_id=schedule_endpoint.id,
            spec=spec or ScheduleSpecIn(name="Daily", cron="0 9 * * *"),
        )
        due = datetime.now(timezone.utc) - timedelta(minutes=due_minutes_ago)
        schedule = service.schedule_of(config) | {"next_run_at": due.isoformat()}
        if schedule.get("run_at"):
            schedule["run_at"] = due.isoformat()
        set_schedule(test_db, config, schedule, service.SCHEDULED)
        test_db.commit()
        return config

    return _make


def _fire(config, now=None):
    return dispatch.fire_due_schedule(
        config.id,
        str(config.organization_id),
        str(config.project_id) if config.project_id else None,
        now or datetime.now(timezone.utc),
    )


def _reload(test_db, config):
    test_db.expire_all()
    return service.load_schedule(test_db, config.id)


def _runs(test_db, config):
    return (
        test_db.query(models.TestRun)
        .filter(models.TestRun.test_configuration_id == config.id)
        .all()
    )


class TestFire:
    def test_fires_once_and_moves_to_the_next_run(self, test_db, make, launched):
        config = make()
        due = timing.parse_instant(service.schedule_of(config)["next_run_at"])

        assert _fire(config) == dispatch.FireResult.FIRED
        assert _fire(config) == dispatch.FireResult.RACE

        runs = _runs(test_db, config)
        assert len(runs) == 1
        assert runs[0].attributes["trigger"] == "schedule"
        assert timing.parse_instant(runs[0].attributes["scheduled_for"]) == due
        config = _reload(test_db, config)
        assert timing.parse_instant(service.schedule_of(config)["next_run_at"]) > due
        assert launched[0].call_args.kwargs["current_user"].id == config.user_id

    def test_found_by_the_org_walk(self, test_db, make, launched):
        config = make()
        found = dispatch.due_in_org(str(config.organization_id), datetime.now(timezone.utc))
        project = str(config.project_id) if config.project_id else None
        assert [entry for entry in found if entry[0] == config.id] == [(config.id, project)]

    def test_paused_and_deleted_schedules_are_not_due(self, test_db, make):
        paused, removed = make(), make()
        service.pause(test_db, paused)
        removed.deleted_at = datetime.now(timezone.utc)
        test_db.commit()
        found = dispatch.due_in_org(str(paused.organization_id), datetime.now(timezone.utc))
        assert {paused.id, removed.id}.isdisjoint({config_id for config_id, _ in found})

    def test_run_once_finishes(self, test_db, make, launched):
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        config = make(ScheduleSpecIn(name="Once", run_at=tomorrow))
        assert _fire(config) == dispatch.FireResult.FIRED
        assert service.status_of(_reload(test_db, config)) == service.FINISHED

    def test_max_runs_counts_the_run_it_starts(self, test_db, make, launched):
        config = make(ScheduleSpecIn(name="Twice", cron="0 9 * * *", max_runs=1))
        assert _fire(config) == dispatch.FireResult.FIRED
        assert service.status_of(_reload(test_db, config)) == service.FINISHED


class TestSkips:
    def test_missed_past_the_grace_is_recorded_and_notified(self, test_db, make, launched):
        config = make(due_minutes_ago=90)
        with patch(f"{_OUTCOMES}.notify") as notify:
            assert _fire(config) == dispatch.FireResult.MISSED
        assert _runs(test_db, config) == []
        config = _reload(test_db, config)
        assert service.schedule_of(config)["last_skip"]["reason"] == "missed"
        assert timing.parse_instant(service.schedule_of(config)["next_run_at"]) > datetime.now(
            timezone.utc
        )
        assert "scheduler was unavailable" in notify.call_args.kwargs["rendered"].title

    def test_late_inside_the_grace_still_fires(self, make, launched):
        assert _fire(make(due_minutes_ago=50)) == dispatch.FireResult.FIRED

    def _in_flight(self, test_db, config, hours_ago=0):
        progress = get_or_create_status(
            test_db,
            "Progress",
            "TestRun",
            organization_id=str(config.organization_id),
            commit=False,
        )
        run = models.TestRun(
            test_configuration_id=config.id,
            organization_id=config.organization_id,
            user_id=config.user_id,
            project_id=config.project_id,
            status_id=progress.id,
        )
        test_db.add(run)
        test_db.flush()
        run.created_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        test_db.commit()

    def test_overlap_skips(self, test_db, make, launched):
        config = make()
        self._in_flight(test_db, config)
        assert _fire(config) == dispatch.FireResult.OVERLAP
        assert service.schedule_of(_reload(test_db, config))["last_skip"]["reason"] == "overlap"

    def test_a_stuck_run_older_than_a_day_does_not_block(self, test_db, make, launched):
        config = make()
        self._in_flight(test_db, config, hours_ago=25)
        assert _fire(config) == dispatch.FireResult.FIRED

    def test_quota_skips_and_stays_scheduled(self, test_db, make, launched):
        config = make()
        with (
            patch(
                "rhesis.backend.app.services.test_set.enforce_test_run_quota",
                side_effect=QuotaExceededError(MagicMock()),
            ),
            patch(f"{_OUTCOMES}.notify") as notify,
        ):
            assert _fire(config) == dispatch.FireResult.QUOTA
        config = _reload(test_db, config)
        assert service.status_of(config) == service.SCHEDULED
        assert service.schedule_of(config)["last_skip"]["reason"] == "quota"
        assert service.schedule_of(config)["quota_skip_notified"] is True
        assert notify.call_count == 1


class TestPauses:
    def _assert_paused(self, test_db, config, reason):
        config = _reload(test_db, config)
        assert service.status_of(config) == service.PAUSED
        assert service.schedule_of(config)["paused_reason"] == reason
        assert _runs(test_db, config) == []

    def test_endpoint_deleted(self, test_db, make, launched, schedule_endpoint):
        config = make()
        schedule_endpoint.deleted_at = datetime.now(timezone.utc)
        test_db.commit()
        with patch(f"{_OUTCOMES}.notify"):
            assert _fire(config) == dispatch.FireResult.PAUSED
        self._assert_paused(test_db, config, "endpoint_missing")

    def test_test_set_emptied(self, test_db, make, launched, schedule_test_set):
        config = make()
        test_db.execute(
            models.test_test_set_association.delete().where(
                models.test_test_set_association.c.test_set_id == schedule_test_set.id
            )
        )
        test_db.commit()
        with patch(f"{_OUTCOMES}.notify"):
            assert _fire(config) == dispatch.FireResult.PAUSED
        self._assert_paused(test_db, config, "test_set_empty")

    def test_model_unavailable(self, test_db, make, launched):
        config = make()
        launched[1].side_effect = ModelNotConfiguredError("evaluation", ValueError("no key"))
        with patch(f"{_OUTCOMES}.notify") as notify:
            assert _fire(config) == dispatch.FireResult.PAUSED
        self._assert_paused(test_db, config, "model_unavailable")
        assert "model" in notify.call_args.kwargs["rendered"].title

    def test_creator_inactive(self, test_db, make, launched, authenticated_user):
        config = make()
        authenticated_user.is_active = False
        test_db.commit()
        with patch(f"{_OUTCOMES}.notify_needs_owner") as needs_owner:
            assert _fire(config) == dispatch.FireResult.PAUSED
        self._assert_paused(test_db, config, "creator_access")
        needs_owner.assert_called_once()

    def test_creator_without_permission_to_run(self, test_db, make, launched):
        config = make()
        with (
            patch(f"{_DISPATCH}.authorize", return_value=False),
            patch(f"{_OUTCOMES}.notify_needs_owner"),
        ):
            assert _fire(config) == dispatch.FireResult.PAUSED
        self._assert_paused(test_db, config, "creator_access")


class TestBeatJob:
    def test_kill_switch(self, make):
        from rhesis.backend.jobs.test_run_schedules import dispatch_due_schedules

        make()
        with (
            patch("rhesis.backend.jobs.test_run_schedules.get_application_settings") as settings,
            patch("rhesis.backend.jobs.test_run_schedules.fire_due_schedule") as fire,
        ):
            settings.return_value.schedule_dispatch_enabled = False
            assert dispatch_due_schedules.run() == {"enabled": False}
        fire.assert_not_called()

    def test_one_org_failing_does_not_stop_the_others(self):
        from rhesis.backend.jobs.test_run_schedules import dispatch_due_schedules

        with (
            patch(
                "rhesis.backend.jobs.test_run_schedules.all_organization_ids",
                return_value=["a", "b"],
            ),
            patch(
                "rhesis.backend.jobs.test_run_schedules.due_in_org",
                side_effect=[RuntimeError("boom"), [("c", None)]],
            ),
            patch(
                "rhesis.backend.jobs.test_run_schedules.fire_due_schedule",
                return_value=dispatch.FireResult.FIRED,
            ),
        ):
            counts = dispatch_due_schedules.run()
        assert counts == {"org_errors": 1, "due": 1, "fired": 1}

    def test_beat_runs_it_every_minute(self):
        from rhesis.backend.celery.config import CELERY_CONFIG

        entry = CELERY_CONFIG["beat_schedule"]["test-run-schedule-dispatch"]
        assert entry["schedule"] == 60.0
        assert "rhesis.backend.jobs.test_run_schedules" in CELERY_CONFIG["include"]
