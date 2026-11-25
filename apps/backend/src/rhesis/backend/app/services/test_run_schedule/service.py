"""Create and change test run schedules.

A schedule is ``test_configuration.attributes["schedule"]`` plus the configuration's status
(Scheduled, Paused, Finished). Functions here flush but don't commit, so the caller decides the
transaction; ``run_now`` is the exception because starting a run commits.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.auth.principal import resolve_principal
from rhesis.backend.app.auth.rbac import authorize
from rhesis.backend.app.crud.test_configuration import (
    count_schedule_runs,
    get_schedule,
    has_in_flight_run,
    replace_run_settings,
    set_schedule,
)
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.test_run_schedule import (
    SPEC_FIELDS,
    OccurrenceEdit,
    ScheduleSpecIn,
    ScheduleUpdate,
)
from rhesis.backend.app.schemas.test_set import TestSetExecutionRequest
from rhesis.backend.app.services.test_configuration_execution import (
    build_parameters_ref,
    execute_configuration,
)
from rhesis.backend.app.services.test_run_schedule import timing
from rhesis.backend.app.services.test_run_schedule.errors import (
    ScheduleConflict,
    ScheduleNotFound,
    ScheduleValidationError,
)

SCHEDULED = "Scheduled"
PAUSED = "Paused"
FINISHED = "Finished"

# Same window the quota uses: an older Queued or Progress run is almost always a crashed one.
IN_FLIGHT_RUN_WINDOW = timedelta(hours=24)
IN_FLIGHT_STATUSES = ["Queued", "Progress"]

# Runs a "this and following" edit keeps from the old timetable before the edited run.
MAX_PINNED_RUNS = 100

CREATOR_ACCESS = "creator_access"

Scope = Literal["one", "following"]

# Keys a schedule's run settings write on the configuration.
_RUN_SETTING_KEYS = (
    "metrics",
    "metrics_source",
    "execution_model_id",
    "evaluation_model_id",
    "parameters_ref",
    "execution_mode",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- reading ----------------------------------------------------------------------------------


def load_schedule(db: Session, config_id: UUID) -> TestConfiguration:
    config = get_schedule(db, config_id)
    if config is None:
        raise ScheduleNotFound("Schedule not found")
    return config


def schedule_of(config: TestConfiguration) -> dict[str, Any]:
    """A copy of the stored schedule, safe to change and write back."""
    return dict((config.attributes or {}).get("schedule") or {})


def status_of(config: TestConfiguration) -> str | None:
    return config.status.name if config.status else None


def timing_of(schedule: dict[str, Any]) -> timing.ScheduleTiming:
    return timing.ScheduleTiming.from_dict(schedule)


# --- shared steps -----------------------------------------------------------------------------


def _new_schedule(spec: ScheduleSpecIn) -> dict[str, Any]:
    return {
        "name": spec.name,
        "cron": spec.cron,
        "run_at": timing.format_instant(spec.run_at),
        "timezone": spec.timezone,
        "ends_at": timing.format_instant(spec.ends_at),
        "starts_at": None,
        "max_runs": spec.max_runs,
        "notify": spec.notify,
        "next_run_at": None,
        "last_run_at": None,
        "last_skip": None,
        "paused_reason": None,
        "failure_streak": 0,
        "quota_skip_notified": False,
        "first_run_notified": False,
        "exceptions": [],
    }


def plan_next_run(db: Session, config: TestConfiguration, schedule: dict, after: datetime) -> str:
    """Set ``next_run_at`` from ``after`` on and return the state that follows from it."""
    max_runs = schedule.get("max_runs")
    if max_runs is not None and count_schedule_runs(db, config.id) >= max_runs:
        upcoming = None
    else:
        upcoming = timing.compute_next_run(
            timing_of(schedule), after, schedule.get("exceptions") or []
        )
    schedule["next_run_at"] = timing.format_instant(upcoming.at) if upcoming else None
    return SCHEDULED if upcoming else FINISHED


def _replan(db: Session, config: TestConfiguration, schedule: dict) -> TestConfiguration:
    """Recompute the next run from now. A paused schedule stays paused."""
    state = plan_next_run(db, config, schedule, _now())
    if status_of(config) == PAUSED and state == SCHEDULED:
        state = PAUSED
    return set_schedule(db, config, schedule, state)


def _validated_spec(schedule: dict, changes: dict) -> ScheduleSpecIn:
    merged = {field: schedule.get(field) for field in SPEC_FIELDS} | changes
    unchanged = {field for field in ("run_at", "ends_at") if field not in changes}
    return ScheduleSpecIn.model_validate(merged, context={"unchanged": unchanged})


def _apply_spec(schedule: dict, spec: ScheduleSpecIn) -> None:
    schedule.update(
        name=spec.name,
        cron=spec.cron,
        run_at=timing.format_instant(spec.run_at),
        timezone=spec.timezone,
        ends_at=timing.format_instant(spec.ends_at),
        max_runs=spec.max_runs,
        notify=spec.notify,
    )


def _settings_attributes(
    db: Session, test_set_id: UUID, settings: TestSetExecutionRequest | None
) -> dict[str, Any]:
    from rhesis.backend.app.services.test_set import resolve_metrics_source

    settings = settings or TestSetExecutionRequest()
    metrics = [
        {"id": str(m.id), "name": m.name, "scope": m.scope} for m in settings.metrics or []
    ] or None
    attributes: dict[str, Any] = dict(settings.execution_options or {"execution_mode": "Parallel"})
    attributes["metrics_source"] = resolve_metrics_source(db, test_set_id, metrics)
    if metrics:
        attributes["metrics"] = metrics
    if settings.execution_model_id:
        attributes["execution_model_id"] = str(settings.execution_model_id)
    if settings.evaluation_model_id:
        attributes["evaluation_model_id"] = str(settings.evaluation_model_id)
    parameters_ref = build_parameters_ref(
        settings.experiment_id, settings.version, settings.environment
    )
    if parameters_ref:
        attributes["parameters_ref"] = parameters_ref
    return attributes


def _refuse_reuse(settings: TestSetExecutionRequest | None) -> None:
    if settings and settings.reference_test_run_id:
        raise ScheduleValidationError(
            "Scheduled runs always call the endpoint, so they can't reuse earlier outputs."
        )


# --- create -----------------------------------------------------------------------------------


def create_schedule(
    db: Session,
    user: User,
    *,
    test_set_id: UUID,
    endpoint_id: UUID,
    spec: ScheduleSpecIn,
    run_settings: TestSetExecutionRequest | None = None,
    name_after_test_set: bool = False,
) -> TestConfiguration:
    """A new configuration for the test set and endpoint, carrying the schedule. No run yet."""
    from rhesis.backend.app.crud.test_configuration import get_test_configuration
    from rhesis.backend.app.services.test_set import (
        _create_test_configuration,
        resolve_execution_targets,
    )

    _refuse_reuse(run_settings)
    test_set, endpoint = resolve_execution_targets(db, str(test_set_id), endpoint_id, user)
    attributes = _settings_attributes(db, test_set.id, run_settings)
    config_id = _create_test_configuration(
        db,
        endpoint.id,
        test_set.id,
        user,
        test_configuration_attributes=attributes,
        organization_id=str(user.organization_id),
        user_id=str(user.id),
        commit=False,
    )
    config = get_test_configuration(
        db, UUID(config_id), organization_id=str(user.organization_id), user_id=str(user.id)
    )
    schedule = _new_schedule(spec)
    if name_after_test_set:
        schedule["name"] = test_set.name
    state = plan_next_run(db, config, schedule, _now())
    if state == FINISHED:
        raise ScheduleValidationError("This schedule has no future runs.")
    return set_schedule(db, config, schedule, state)


def create_schedules_bulk(
    db: Session,
    user: User,
    *,
    test_set_ids: list[UUID],
    endpoint_id: UUID,
    spec: ScheduleSpecIn,
    run_settings: TestSetExecutionRequest | None = None,
) -> list[TestConfiguration]:
    """One schedule per test set, named after it. One that can't be created undoes them all."""
    try:
        return [
            create_schedule(
                db,
                user,
                test_set_id=test_set_id,
                endpoint_id=endpoint_id,
                spec=spec,
                run_settings=run_settings,
                name_after_test_set=True,
            )
            for test_set_id in test_set_ids
        ]
    except Exception:
        db.rollback()
        raise


# --- change -----------------------------------------------------------------------------------


def update_schedule(
    db: Session, config: TestConfiguration, update: ScheduleUpdate
) -> TestConfiguration:
    """Change the schedule from now on. Runs that already happened keep their settings."""
    if update.test_set_id is not None and update.test_set_id != config.test_set_id:
        raise ScheduleValidationError(
            "A schedule can't move to another test set. Create a new schedule instead."
        )
    schedule = schedule_of(config)
    spec = _validated_spec(schedule, update.spec_changes())
    _apply_spec(schedule, spec)
    if update.touches_timing():
        schedule["starts_at"] = None
        schedule["exceptions"] = []
    _apply_run_settings(db, config, update)
    return _replan(db, config, schedule)


def _apply_run_settings(db: Session, config: TestConfiguration, update: ScheduleUpdate) -> None:
    if "run_settings" not in update.model_fields_set and update.endpoint_id is None:
        return
    _refuse_reuse(update.run_settings)
    attributes = None
    if "run_settings" in update.model_fields_set:
        attributes = {
            k: v for k, v in (config.attributes or {}).items() if k not in _RUN_SETTING_KEYS
        }
        attributes |= _settings_attributes(db, config.test_set_id, update.run_settings)
    replace_run_settings(db, config, attributes=attributes, endpoint_id=update.endpoint_id)


def edit_occurrence(
    db: Session,
    config: TestConfiguration,
    occurrence: datetime,
    scope: Scope,
    edit: OccurrenceEdit,
) -> TestConfiguration:
    """A change made from one upcoming run: to that run only, or to it and the ones after."""
    schedule = schedule_of(config)
    current = _upcoming(schedule, occurrence)
    if scope == "one":
        return _move_one(db, config, schedule, current, edit)
    return _change_following(db, config, schedule, current, edit)


def _upcoming(schedule: dict, occurrence: datetime) -> timing.Occurrence:
    found = timing.find_occurrence(
        timing_of(schedule), occurrence, schedule.get("exceptions") or []
    )
    if found is None or found.at <= _now():
        raise ScheduleConflict("This run isn't planned anymore. Refresh to see the schedule.")
    return found


def _move_one(
    db: Session,
    config: TestConfiguration,
    schedule: dict,
    current: timing.Occurrence,
    edit: OccurrenceEdit,
) -> TestConfiguration:
    if edit.model_fields_set - {"move_to"} or edit.move_to is None:
        raise ScheduleValidationError("Only the date and time can change for a single run.")
    move_to = edit.move_to.astimezone(timezone.utc)
    if move_to <= _now():
        raise ScheduleValidationError("Pick a time in the future.")
    if schedule.get("run_at"):
        schedule["run_at"] = timing.format_instant(move_to)
        return _replan(db, config, schedule)
    schedule["exceptions"] = _with_exception(schedule, current, move_to)
    return _replan(db, config, schedule)


def _with_exception(schedule: dict, current: timing.Occurrence, move_to: datetime) -> list:
    original = timing.format_instant(current.original)
    kept, was_extra = [], False
    for entry in schedule.get("exceptions") or []:
        if timing.parse_instant(entry["occurrence"]) == current.original:
            was_extra = was_extra or bool(entry.get("extra"))
            continue
        kept.append(entry)
    moved = {"occurrence": original, "run_at": timing.format_instant(move_to)}
    if was_extra:
        kept.append(moved | {"extra": True})
    elif move_to != current.original:
        kept.append(moved)
    return kept


def _change_following(
    db: Session,
    config: TestConfiguration,
    schedule: dict,
    current: timing.Occurrence,
    edit: OccurrenceEdit,
) -> TestConfiguration:
    if schedule.get("run_at"):
        raise ScheduleValidationError("A schedule that runs once has no following runs.")
    changes = edit.spec_changes()
    if edit.move_to is not None:
        changes["cron"] = _cron_at_new_time(schedule, current, edit.move_to)
    spec = _validated_spec(schedule, changes)
    _apply_run_settings(db, config, edit)
    if not (edit.touches_timing() or edit.move_to is not None):
        _apply_spec(schedule, spec)
        return _replan(db, config, schedule)

    starts_at = min(current.original, (edit.move_to or current.original).astimezone(timezone.utc))
    kept = timing.occurrences(
        timing_of(schedule), _now(), starts_at, schedule.get("exceptions") or []
    )
    if len(kept) > MAX_PINNED_RUNS:
        raise ScheduleValidationError(
            "Too many runs come before this one. Change the schedule from the list instead."
        )
    _apply_spec(schedule, spec)
    schedule["starts_at"] = timing.format_instant(starts_at)
    schedule["exceptions"] = [
        {
            "occurrence": timing.format_instant(o.original),
            "run_at": timing.format_instant(o.at),
            "extra": True,
        }
        for o in kept
    ]
    return _replan(db, config, schedule)


def _cron_at_new_time(schedule: dict, current: timing.Occurrence, move_to: datetime) -> str:
    """The same days at the run's new time, or a refusal when the day itself moved."""
    zone = timing_of(schedule).zone
    before, after = current.original.astimezone(zone), move_to.astimezone(zone)
    if before.date() != after.date():
        raise ScheduleValidationError("To change which days it runs, change Repeats.")
    minute, hour, *days = (schedule.get("cron") or "").split()
    if not (minute.isdigit() and hour.isdigit()):
        raise ScheduleValidationError(
            "This schedule runs at several times. Change its cron expression instead."
        )
    return " ".join([str(after.minute), str(after.hour), *days])


def delete_occurrence(
    db: Session, config: TestConfiguration, occurrence: datetime, scope: Scope
) -> TestConfiguration:
    """Skip one upcoming run, or end the schedule just before it."""
    schedule = schedule_of(config)
    current = _upcoming(schedule, occurrence)
    if schedule.get("run_at"):
        raise ScheduleValidationError("Delete the whole schedule instead.")
    if scope == "one":
        original = timing.format_instant(current.original)
        schedule["exceptions"] = [
            e
            for e in schedule.get("exceptions") or []
            if timing.parse_instant(e["occurrence"]) != current.original or e.get("extra")
        ] + [{"occurrence": original, "skip": True}]
        return _replan(db, config, schedule)
    ends_at = min(current.original, current.at) - timedelta(seconds=1)
    schedule["ends_at"] = timing.format_instant(ends_at)
    schedule["exceptions"] = [
        e
        for e in schedule.get("exceptions") or []
        if e.get("skip") or timing.parse_instant(e["run_at"]) <= ends_at
    ]
    return _replan(db, config, schedule)


def skip_next(db: Session, config: TestConfiguration) -> TestConfiguration:
    schedule = schedule_of(config)
    next_run_at = timing.parse_instant(schedule.get("next_run_at"))
    if next_run_at is None:
        raise ScheduleConflict("There is no next run to skip.")
    current = timing.current_occurrence(next_run_at, schedule.get("exceptions") or [])
    if schedule.get("run_at"):
        raise ScheduleValidationError("Delete the schedule instead; it runs only once.")
    return delete_occurrence(db, config, current.original, "one")


# --- state ------------------------------------------------------------------------------------


def pause(db: Session, config: TestConfiguration, reason: str = "user") -> TestConfiguration:
    if status_of(config) == FINISHED:
        raise ScheduleConflict("This schedule has finished. Give it a new date to run again.")
    schedule = schedule_of(config)
    schedule["paused_reason"] = reason
    return set_schedule(db, config, schedule, PAUSED)


def resume(db: Session, config: TestConfiguration) -> TestConfiguration:
    """Run again from the next future time. Missed runs are not made up."""
    schedule = schedule_of(config)
    if schedule.get("paused_reason") == CREATOR_ACCESS:
        raise ScheduleValidationError(
            "This schedule's owner can no longer run tests here. Take it over instead."
        )
    return _restart(db, config, schedule)


def _restart(
    db: Session, config: TestConfiguration, schedule: dict, owner_id: UUID | None = None
) -> TestConfiguration:
    schedule.update(paused_reason=None, failure_streak=0, quota_skip_notified=False)
    state = plan_next_run(db, config, schedule, _now())
    return set_schedule(db, config, schedule, state, owner_id=owner_id)


def take_over(db: Session, config: TestConfiguration, user: User) -> TestConfiguration:
    """Make ``user`` the owner, after checking they can run it, and resume it if paused."""
    from rhesis.backend.jobs.execution.run import plan_run_for_user

    allowed = authorize(
        resolve_principal(user), Permission.TestRun.EXECUTE, project_id=config.project_id, db=db
    )
    if not allowed:
        raise PermissionError("You need permission to run tests in this project to take it over.")
    # Raises the model error that names the model the runs need and the caller can't use.
    plan_run_for_user(db, config, user)
    schedule = schedule_of(config)
    if status_of(config) == SCHEDULED:
        schedule.update(paused_reason=None)
        return set_schedule(db, config, schedule, SCHEDULED, owner_id=user.id)
    return _restart(db, config, schedule, owner_id=user.id)


def delete_schedule(db: Session, config: TestConfiguration) -> TestConfiguration:
    """Remove the schedule. The configuration stays, because its runs point at it."""
    return set_schedule(db, config, None, None)


def run_now(db: Session, config: TestConfiguration, user: User):
    """Start a run as ``user`` now. The schedule's own times don't change."""
    if has_in_flight_run(db, config.id, _now() - IN_FLIGHT_RUN_WINDOW, IN_FLIGHT_STATUSES):
        raise ScheduleConflict("A run of this schedule is still going. Wait for it to finish.")
    return execute_configuration(db, config, user, trigger="manual")
