"""The schedule service against a real database: create, change, pause, take over, run now."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app import models
from rhesis.backend.app.schemas.test_run_schedule import (
    OccurrenceEdit,
    ScheduleSpecIn,
    ScheduleUpdate,
)
from rhesis.backend.app.schemas.test_set import TestSetExecutionRequest
from rhesis.backend.app.services.test_run_schedule import service, timing
from rhesis.backend.app.services.test_run_schedule.errors import (
    ScheduleConflict,
    ScheduleNotFound,
    ScheduleValidationError,
)
from rhesis.backend.app.utils.crud_utils import get_or_create_status

DAILY = "0 9 * * *"


def _spec(**overrides) -> ScheduleSpecIn:
    return ScheduleSpecIn(**({"name": "Daily check", "cron": DAILY, "timezone": "UTC"} | overrides))


@pytest.fixture
def user(authenticated_user):
    return authenticated_user


@pytest.fixture
def create(test_db, user, schedule_test_set, schedule_endpoint):
    def _create(spec=None, **kwargs):
        config = service.create_schedule(
            test_db,
            user,
            test_set_id=kwargs.pop("test_set_id", schedule_test_set.id),
            endpoint_id=schedule_endpoint.id,
            spec=spec or _spec(),
            **kwargs,
        )
        test_db.refresh(config)
        return config

    return _create


def _schedule(config):
    return config.attributes["schedule"]


def _next(config) -> datetime:
    return timing.parse_instant(_schedule(config)["next_run_at"])


def _runs(test_db, config) -> int:
    return (
        test_db.query(models.TestRun)
        .filter(models.TestRun.test_configuration_id == config.id)
        .count()
    )


def _add_run(test_db, config, status_name, created_at=None, trigger="schedule"):
    status = get_or_create_status(
        test_db, status_name, "TestRun", organization_id=str(config.organization_id), commit=False
    )
    run = models.TestRun(
        test_configuration_id=config.id,
        organization_id=config.organization_id,
        user_id=config.user_id,
        project_id=config.project_id,
        status_id=status.id,
        attributes={"trigger": trigger},
    )
    test_db.add(run)
    test_db.flush()
    if created_at:
        run.created_at = created_at
        test_db.flush()
    return run


class TestCreate:
    def test_creates_a_scheduled_configuration_and_no_run(self, test_db, create, user):
        config = create()

        assert service.status_of(config) == service.SCHEDULED
        assert config.user_id == user.id
        schedule = _schedule(config)
        assert schedule["name"] == "Daily check"
        assert schedule["notify"] == "problems"
        assert _next(config) > datetime.now(timezone.utc)
        assert _next(config).hour == 9
        assert config.attributes["metrics_source"] == "requirement"
        assert _runs(test_db, config) == 0

    def test_a_blank_name_takes_the_test_set_name(self, create):
        config = create(_spec(name=""))
        assert _schedule(config)["name"] == "Weekday regression set"

    def test_refuses_output_reuse(self, create):
        settings = TestSetExecutionRequest(reference_test_run_id=uuid.uuid4())
        with pytest.raises(ScheduleValidationError, match="reuse"):
            create(run_settings=settings)

    def test_stores_run_settings(self, create):
        settings = TestSetExecutionRequest(execution_options={"execution_mode": "Sequential"})
        config = create(run_settings=settings)
        assert config.attributes["execution_mode"] == "Sequential"

    def test_bulk_creates_one_schedule_per_set_named_after_it(
        self, test_db, user, make_test_set, schedule_endpoint
    ):
        first, second = make_test_set("Smoke"), make_test_set("Refunds")
        configs = service.create_schedules_bulk(
            test_db,
            user,
            test_set_ids=[first.id, second.id],
            endpoint_id=schedule_endpoint.id,
            spec=_spec(),
        )
        assert sorted(_schedule(c)["name"] for c in configs) == ["Refunds", "Smoke"]

    def test_bulk_creates_nothing_when_one_set_is_invalid(
        self, test_db, user, make_test_set, schedule_endpoint
    ):
        good = make_test_set("Smoke")
        test_db.commit()
        with pytest.raises(ValueError):
            service.create_schedules_bulk(
                test_db,
                user,
                test_set_ids=[good.id, uuid.uuid4()],
                endpoint_id=schedule_endpoint.id,
                spec=_spec(),
            )
        assert (
            test_db.query(models.TestConfiguration)
            .filter(models.TestConfiguration.test_set_id == good.id)
            .count()
            == 0
        )


class TestUpdate:
    def test_timing_change_recomputes_the_next_run(self, test_db, create):
        config = create()
        service.update_schedule(test_db, config, ScheduleUpdate(cron="30 14 * * *"))
        assert (_next(config).hour, _next(config).minute) == (14, 30)

    def test_name_change_keeps_the_timing(self, test_db, create):
        config = create()
        before = _next(config)
        service.update_schedule(test_db, config, ScheduleUpdate(name="Renamed"))
        assert _schedule(config)["name"] == "Renamed"
        assert _next(config) == before

    def test_moving_to_another_test_set_is_refused(self, test_db, create):
        config = create()
        with pytest.raises(ScheduleValidationError, match="another test set"):
            service.update_schedule(test_db, config, ScheduleUpdate(test_set_id=uuid.uuid4()))

    def test_run_settings_change_replaces_the_old_ones(self, test_db, create):
        config = create(
            run_settings=TestSetExecutionRequest(execution_options={"execution_mode": "Sequential"})
        )
        service.update_schedule(
            test_db, config, ScheduleUpdate(run_settings=TestSetExecutionRequest())
        )
        assert config.attributes["execution_mode"] == "Parallel"
        assert "schedule" in config.attributes

    def test_finished_schedule_with_a_new_date_is_scheduled_again(self, test_db, create):
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        config = create(_spec(cron=None, run_at=tomorrow))
        schedule = _schedule(config)
        schedule["run_at"] = timing.format_instant(tomorrow - timedelta(days=3))
        from rhesis.backend.app.crud.test_configuration import set_schedule

        set_schedule(test_db, config, schedule, service.FINISHED)

        later = tomorrow + timedelta(days=2)
        service.update_schedule(test_db, config, ScheduleUpdate(run_at=later))
        assert service.status_of(config) == service.SCHEDULED
        assert _next(config) == later


class TestOccurrences:
    def test_moving_one_run_writes_an_exception(self, test_db, create):
        config = create()
        first = _next(config)
        moved = first + timedelta(hours=3)
        service.edit_occurrence(test_db, config, first, "one", OccurrenceEdit(move_to=moved))
        assert _next(config) == moved
        assert _schedule(config)["exceptions"] == [
            {"occurrence": first.isoformat(), "run_at": moved.isoformat()}
        ]

    def test_one_run_only_takes_a_new_time(self, test_db, create):
        config = create()
        with pytest.raises(ScheduleValidationError, match="Only the date and time"):
            service.edit_occurrence(
                test_db, config, _next(config), "one", OccurrenceEdit(name="Other")
            )

    def test_following_from_the_next_run_changes_the_time(self, test_db, create):
        config = create()
        first = _next(config)
        service.edit_occurrence(
            test_db,
            config,
            first,
            "following",
            OccurrenceEdit(move_to=first.replace(hour=11)),
        )
        assert _schedule(config)["cron"] == "0 11 * * *"
        assert _next(config) == first.replace(hour=11)
        assert _schedule(config)["exceptions"] == []

    def test_following_from_a_later_run_keeps_the_runs_before_it(self, test_db, create):
        config = create()
        first = _next(config)
        third = first + timedelta(days=2)
        service.edit_occurrence(
            test_db, config, third, "following", OccurrenceEdit(move_to=third.replace(hour=11))
        )
        upcoming = timing.occurrences(
            timing.ScheduleTiming.from_dict(_schedule(config)),
            datetime.now(timezone.utc),
            third + timedelta(days=2),
            _schedule(config)["exceptions"],
        )
        assert [o.at for o in upcoming] == [
            first,
            first + timedelta(days=1),
            third.replace(hour=11),
            third.replace(hour=11) + timedelta(days=1),
        ]

    def test_following_cannot_move_the_day(self, test_db, create):
        config = create()
        first = _next(config)
        with pytest.raises(ScheduleValidationError, match="change Repeats"):
            service.edit_occurrence(
                test_db,
                config,
                first,
                "following",
                OccurrenceEdit(move_to=first + timedelta(days=1)),
            )

    def test_a_run_that_is_not_planned_is_a_conflict(self, test_db, create):
        config = create()
        with pytest.raises(ScheduleConflict):
            service.edit_occurrence(
                test_db,
                config,
                _next(config) + timedelta(minutes=7),
                "one",
                OccurrenceEdit(move_to=_next(config)),
            )

    def test_delete_one_skips_it(self, test_db, create):
        config = create()
        first = _next(config)
        service.delete_occurrence(test_db, config, first, "one")
        assert _next(config) == first + timedelta(days=1)

    def test_delete_following_ends_the_schedule_before_it(self, test_db, create):
        config = create()
        second = _next(config) + timedelta(days=1)
        service.delete_occurrence(test_db, config, second, "following")
        assert timing.parse_instant(_schedule(config)["ends_at"]) < second
        service.skip_next(test_db, config)
        assert service.status_of(config) == service.FINISHED
        assert _schedule(config)["next_run_at"] is None

    def test_skip_next(self, test_db, create):
        config = create()
        first = _next(config)
        service.skip_next(test_db, config)
        assert _next(config) == first + timedelta(days=1)


class TestState:
    def test_pause_and_resume(self, test_db, create):
        config = create()
        service.pause(test_db, config)
        assert service.status_of(config) == service.PAUSED
        assert _schedule(config)["paused_reason"] == "user"

        service.resume(test_db, config)
        assert service.status_of(config) == service.SCHEDULED
        assert _schedule(config)["paused_reason"] is None

    def test_resume_is_refused_when_the_creator_lost_access(self, test_db, create):
        config = create()
        service.pause(test_db, config, reason=service.CREATOR_ACCESS)
        with pytest.raises(ScheduleValidationError, match="Take it over"):
            service.resume(test_db, config)

    def test_delete_removes_the_schedule_and_keeps_the_configuration(self, test_db, create):
        config = create()
        service.delete_schedule(test_db, config)
        assert "schedule" not in config.attributes
        assert config.status_id is None
        with pytest.raises(ScheduleNotFound):
            service.load_schedule(test_db, config.id)


_AUTHORIZE = "rhesis.backend.app.services.test_run_schedule.service.authorize"
_PLAN = "rhesis.backend.jobs.execution.run.plan_run_for_user"


class TestTakeOver:
    @pytest.fixture
    def other_user(self, test_db, test_org_id):
        other = models.User(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            organization_id=uuid.UUID(test_org_id),
        )
        test_db.add(other)
        test_db.flush()
        return other

    def test_take_over_makes_the_caller_the_owner_and_resumes(self, test_db, create, other_user):
        config = create()
        service.pause(test_db, config, reason=service.CREATOR_ACCESS)
        with patch(_AUTHORIZE, return_value=True), patch(_PLAN) as plan:
            service.take_over(test_db, config, other_user)
        plan.assert_called_once()
        assert config.user_id == other_user.id
        assert service.status_of(config) == service.SCHEDULED
        assert _schedule(config)["paused_reason"] is None

    def test_refused_without_permission_to_run_tests(self, test_db, create, other_user, user):
        config = create()
        with patch(_AUTHORIZE, return_value=False), pytest.raises(PermissionError):
            service.take_over(test_db, config, other_user)
        assert config.user_id == user.id

    def test_a_model_the_caller_cannot_use_changes_nothing(self, test_db, create, other_user, user):
        config = create()
        service.pause(test_db, config, reason=service.CREATOR_ACCESS)
        with (
            patch(_AUTHORIZE, return_value=True),
            patch(_PLAN, side_effect=ValueError("No evaluation model")),
            pytest.raises(ValueError),
        ):
            service.take_over(test_db, config, other_user)
        assert config.user_id == user.id
        assert service.status_of(config) == service.PAUSED


class TestRunNow:
    def test_refused_while_a_run_is_in_flight(self, test_db, create):
        config = create()
        _add_run(test_db, config, "Progress")
        with pytest.raises(ScheduleConflict, match="still going"):
            service.run_now(test_db, config, MagicMock())

    def test_an_old_stuck_run_does_not_block(self, test_db, create, user):
        config = create()
        planned = _next(config)
        _add_run(test_db, config, "Progress", datetime.now(timezone.utc) - timedelta(hours=25))
        with (
            patch(_PLAN, return_value=None),
            patch("rhesis.backend.jobs.launch_job", return_value=MagicMock(id="task")),
        ):
            _, run = service.run_now(test_db, config, user)
        assert run.attributes["trigger"] == "manual"
        assert _next(config) == planned

    def test_max_runs_counts_only_scheduled_runs(self, test_db, create):
        config = create(_spec(max_runs=1))
        _add_run(test_db, config, "Completed", trigger="manual")
        service.update_schedule(test_db, config, ScheduleUpdate(name="Still going"))
        assert service.status_of(config) == service.SCHEDULED
        _add_run(test_db, config, "Completed")
        service.update_schedule(test_db, config, ScheduleUpdate(name="Done"))
        assert service.status_of(config) == service.FINISHED
