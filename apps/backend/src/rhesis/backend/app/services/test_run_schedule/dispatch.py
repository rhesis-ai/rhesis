"""Start the runs that are due. Called every minute by the Beat job in ``jobs/test_run_schedules``.

Each due schedule is claimed and fired in its own session, bound to its organization, its
project and its owner, so the run is created and billed exactly as if the owner had started it.
A schedule fires at most once per run time: its next run time is committed before the run is
submitted, so a crash in between loses that run rather than starting it twice.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.auth.principal import resolve_principal
from rhesis.backend.app.auth.rbac import authorize
from rhesis.backend.app.crud.organization import list_organization_ids
from rhesis.backend.app.crud.project import list_org_project_ids
from rhesis.backend.app.crud.test_configuration import (
    find_due_schedule_ids,
    get_schedule,
    has_in_flight_run,
    lock_schedule,
    set_schedule,
)
from rhesis.backend.app.database import (
    SessionLocal,
    bind_scope_to_session,
    get_db_with_tenant_variables,
    temporary_project_scope,
)
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.provenance import bind_job_provenance
from rhesis.backend.app.quota.enforcement import QuotaExceededError
from rhesis.backend.app.services.test_configuration_execution import execute_configuration
from rhesis.backend.app.services.test_run_schedule import outcomes, timing
from rhesis.backend.app.services.test_run_schedule.service import (
    CREATOR_ACCESS,
    IN_FLIGHT_RUN_WINDOW,
    IN_FLIGHT_STATUSES,
    PAUSED,
    SCHEDULED,
    plan_next_run,
    schedule_of,
    status_of,
)
from rhesis.backend.app.utils.model_errors import ModelConfigurationError, ModelNotConfiguredError

logger = logging.getLogger(__name__)

# A run more than this late (the scheduler was down) is recorded as missed, not started.
MISSED_GRACE = timedelta(hours=1)


class FireResult(str, Enum):
    FIRED = "fired"
    RACE = "race"  # another worker had it, or it changed since it was found
    MISSED = "missed"
    OVERLAP = "overlap"
    QUOTA = "quota"
    PAUSED = "paused"
    ERROR = "error"


class TargetMissing(Exception):
    """Something the run needs is gone; the schedule pauses with ``reason``."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def all_organization_ids() -> list[str]:
    """Read before any tenant is bound, like auth lookups."""
    db = SessionLocal()
    try:
        return list_organization_ids(db)
    finally:
        db.close()


def due_in_org(organization_id: str, now: datetime) -> list[tuple[UUID, str | None]]:
    """Due schedules in one organization, as (configuration id, project id)."""
    with get_db_with_tenant_variables(organization_id) as db:
        # With no project bound, project RLS shows only project-less rows; walk each project.
        due = [(config_id, None) for config_id in find_due_schedule_ids(db, now, SCHEDULED, None)]
        for project_id in list_org_project_ids(db, organization_id):
            with temporary_project_scope(db, organization_id, "", str(project_id)):
                due += [
                    (config_id, str(project_id))
                    for config_id in find_due_schedule_ids(db, now, SCHEDULED, project_id)
                ]
        return due


def fire_due_schedule(
    config_id: UUID, organization_id: str, project_id: str | None, now: datetime
) -> FireResult:
    """Claim one due schedule and start its run, or record why it didn't run."""
    with get_db_with_tenant_variables(organization_id, "", project_id or "") as db:
        bind_job_provenance(db, user_id=None, job_id=None, request_id=None)
        if not lock_schedule(db, config_id):
            return FireResult.RACE
        config = get_schedule(db, config_id)
        if config is None or status_of(config) != SCHEDULED:
            return FireResult.RACE
        schedule = schedule_of(config)
        next_run_at = timing.parse_instant(schedule.get("next_run_at"))
        if next_run_at is None or next_run_at > now:
            return FireResult.RACE
        bind_scope_to_session(db, organization_id, str(config.user_id or ""), project_id or "")
        occurrence = timing.current_occurrence(next_run_at, schedule.get("exceptions") or [])
        return _fire(db, config, schedule, occurrence, now)


def _fire(
    db: Session,
    config: TestConfiguration,
    schedule: dict,
    occurrence: timing.Occurrence,
    now: datetime,
) -> FireResult:
    if now - occurrence.at > MISSED_GRACE:
        _skip_and_advance(db, config, schedule, occurrence, "missed", now)
        outcomes.notify_missed(db, config, occurrence.at)
        db.commit()
        return FireResult.MISSED
    since = now - IN_FLIGHT_RUN_WINDOW
    if has_in_flight_run(db, config.id, since, IN_FLIGHT_STATUSES):
        _skip_and_advance(db, config, schedule, occurrence, "overlap", now)
        return FireResult.OVERLAP

    # At most once: the next run time is saved before this one is submitted.
    _advance(db, config, schedule, now, starting=1)
    db.commit()

    creator = config.user
    if not _creator_can_run(db, creator, config):
        _pause(db, config, CREATOR_ACCESS)
        outcomes.notify_needs_owner(db, config, creator.display_name if creator else "Its owner")
        db.commit()
        return FireResult.PAUSED
    return _submit(db, config, creator, occurrence)


def _submit(db: Session, config: TestConfiguration, creator, occurrence) -> FireResult:
    config_id = config.id
    try:
        _check_targets(db, config)
        execute_configuration(
            db, config, creator, trigger="schedule", scheduled_for=occurrence.original
        )
        return FireResult.FIRED
    except QuotaExceededError:
        db.rollback()
        config = get_schedule(db, config_id)
        schedule = _record_skip(schedule_of(config), occurrence, "quota")
        outcomes.notify_quota_once(db, config, schedule)
        set_schedule(db, config, schedule, status_of(config))
        db.commit()
        return FireResult.QUOTA
    except (TargetMissing, ModelNotConfiguredError, ModelConfigurationError) as exc:
        db.rollback()
        reason = exc.reason if isinstance(exc, TargetMissing) else "model_unavailable"
        config = get_schedule(db, config_id)
        _pause(db, config, reason)
        outcomes.notify_paused(db, config, reason)
        db.commit()
        return FireResult.PAUSED
    except Exception:
        logger.exception("Scheduled run of %s could not start", config_id)
        db.rollback()
        config = get_schedule(db, config_id)
        if config is not None:
            schedule = _record_skip(schedule_of(config), occurrence, "error")
            set_schedule(db, config, schedule, status_of(config))
            db.commit()
        return FireResult.ERROR


def _check_targets(db: Session, config: TestConfiguration) -> None:
    from rhesis.backend.app.services.test_set import count_test_set_tests

    if config.endpoint is None or config.endpoint.deleted_at is not None:
        raise TargetMissing("endpoint_missing")
    if config.test_set is None or config.test_set.deleted_at is not None:
        raise TargetMissing("test_set_missing")
    if count_test_set_tests(db, config.test_set_id) == 0:
        raise TargetMissing("test_set_empty")


def _creator_can_run(db: Session, creator, config: TestConfiguration) -> bool:
    if creator is None or not creator.is_active:
        return False
    if str(creator.organization_id) != str(config.organization_id):
        return False
    return authorize(
        resolve_principal(creator), Permission.TestRun.EXECUTE, project_id=config.project_id, db=db
    )


def _record_skip(schedule: dict, occurrence: timing.Occurrence, reason: str) -> dict:
    schedule["last_skip"] = {"at": timing.format_instant(occurrence.at), "reason": reason}
    return schedule


def _advance(
    db: Session, config: TestConfiguration, schedule: dict, now: datetime, starting: int = 0
) -> None:
    """Move past the run that was due: next time, or Finished when none is left.

    Planned from now, so runs that fell inside an outage are passed over in one step.
    """
    schedule["last_run_at"] = timing.format_instant(now)
    schedule["exceptions"] = timing.prune_exceptions(schedule.get("exceptions") or [], now)
    state = plan_next_run(db, config, schedule, now, starting=starting)
    set_schedule(db, config, schedule, state)


def _skip_and_advance(db, config, schedule, occurrence, reason: str, now: datetime) -> None:
    _record_skip(schedule, occurrence, reason)
    _advance(db, config, schedule, now)
    db.commit()


def _pause(db: Session, config: TestConfiguration, reason: str) -> None:
    schedule = schedule_of(config)
    schedule["paused_reason"] = reason
    set_schedule(db, config, schedule, PAUSED)
