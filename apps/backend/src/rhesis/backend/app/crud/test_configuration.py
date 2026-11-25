"""CRUD operations for test configurations."""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import DateTime, cast, func
from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item_detail,
    get_or_create_status,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder


def get_test_configuration(
    db: Session,
    test_configuration_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestConfiguration]:
    return get_item_detail(
        db,
        models.TestConfiguration,
        test_configuration_id,
        organization_id=organization_id,
        user_id=user_id,
    )


def get_test_configurations(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.TestConfiguration]:
    return (
        QueryBuilder(db, models.TestConfiguration)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )


def create_test_configuration(
    db: Session,
    test_configuration: schemas.TestConfigurationCreate,
    organization_id: str | None = None,
    user_id: str | None = None,
    commit: bool = True,
) -> models.TestConfiguration:
    return create_item(
        db,
        models.TestConfiguration,
        test_configuration,
        organization_id=organization_id,
        user_id=user_id,
        commit=commit,
    )


class ScheduleManagedElsewhere(ValueError):
    """A plain configuration update tried to change the schedule it carries."""


def update_test_configuration(
    db: Session,
    test_configuration_id: uuid.UUID,
    test_configuration: schemas.TestConfigurationUpdate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestConfiguration]:
    """Update test_configuration. A schedule on it survives; it changes only through its API."""
    stored = get_test_configuration(db, test_configuration_id, organization_id, user_id)
    if stored is not None:
        test_configuration = _keep_schedule(stored, test_configuration)
    return update_item(
        db,
        models.TestConfiguration,
        test_configuration_id,
        test_configuration,
        organization_id,
        user_id,
    )


def _keep_schedule(
    stored: models.TestConfiguration, update: schemas.TestConfigurationUpdate
) -> schemas.TestConfigurationUpdate:
    schedule = (stored.attributes or {}).get("schedule")
    if schedule is None:
        return update
    changed = update.model_fields_set
    incoming = update.attributes or {}
    if "attributes" in changed and incoming.get("schedule", schedule) != schedule:
        raise ScheduleManagedElsewhere("Change schedules through /test_run_schedules")
    if "status_id" in changed and update.status_id != stored.status_id:
        raise ScheduleManagedElsewhere("Change schedules through /test_run_schedules")
    if "attributes" not in changed:
        return update
    return update.model_copy(update={"attributes": incoming | {"schedule": schedule}})


def delete_test_configuration(
    db: Session,
    test_configuration_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestConfiguration]:
    """Delete test_configuration. Its schedule goes first, so a restore brings none back."""
    config = get_test_configuration(db, test_configuration_id, organization_id, user_id)
    if config is not None and (config.attributes or {}).get("schedule") is not None:
        set_schedule(db, config, None, None)
    return delete_item(
        db,
        models.TestConfiguration,
        test_configuration_id,
        organization_id=organization_id,
        user_id=user_id,
    )


# --- test run schedules -----------------------------------------------------------------------
# A schedule is ``attributes["schedule"]`` on a configuration; its state is the status.

SCHEDULE_STATUS_ENTITY = "TestConfiguration"


def _scheduled_configurations(db: Session):
    # Soft-deleted rows aren't filtered automatically outside QueryBuilder.
    return (
        db.query(models.TestConfiguration)
        .options(
            joinedload(models.TestConfiguration.status),
            joinedload(models.TestConfiguration.test_set),
            joinedload(models.TestConfiguration.endpoint),
            joinedload(models.TestConfiguration.user),
        )
        .filter(
            models.TestConfiguration.attributes.has_key("schedule"),
            models.TestConfiguration.deleted_at.is_(None),
        )
    )


def set_schedule(
    db: Session,
    config: models.TestConfiguration,
    schedule: dict[str, Any] | None,
    status_name: str | None,
    owner_id: uuid.UUID | None = None,
) -> models.TestConfiguration:
    """Write a configuration's schedule and state. ``None`` removes both. Flushes, no commit."""
    attributes = dict(config.attributes or {})
    if schedule is None:
        attributes.pop("schedule", None)
    else:
        attributes["schedule"] = schedule
    config.attributes = attributes
    # The relationship, not status_id, so config.status reads the new state at once.
    config.status = (
        None
        if status_name is None
        else get_or_create_status(
            db,
            status_name,
            SCHEDULE_STATUS_ENTITY,
            organization_id=str(config.organization_id),
            commit=False,
        )
    )
    if owner_id is not None:
        config.user_id = owner_id
    db.flush()
    return config


def replace_run_settings(
    db: Session,
    config: models.TestConfiguration,
    *,
    attributes: dict[str, Any] | None = None,
    endpoint_id: uuid.UUID | None = None,
) -> models.TestConfiguration:
    """Change what a configuration runs with. ``attributes`` replaces all but the schedule."""
    if attributes is not None:
        schedule = (config.attributes or {}).get("schedule")
        config.attributes = attributes | ({"schedule": schedule} if schedule else {})
    if endpoint_id is not None:
        config.endpoint_id = endpoint_id
    db.flush()
    return config


def find_due_schedule_ids(
    db: Session, now: datetime, status_name: str, project_id: uuid.UUID | None
) -> List[uuid.UUID]:
    """Schedules in ``project_id`` (``None``: project-less) whose next run is due by ``now``.

    Project RLS shows project-less rows in every project's scope too, hence the explicit filter.
    """
    project_filter = (
        models.TestConfiguration.project_id.is_(None)
        if project_id is None
        else models.TestConfiguration.project_id == project_id
    )
    next_run_at = models.TestConfiguration.attributes["schedule"]["next_run_at"].astext
    rows = (
        db.query(models.TestConfiguration.id)
        .join(models.Status, models.TestConfiguration.status_id == models.Status.id)
        .filter(
            models.TestConfiguration.attributes.has_key("schedule"),
            models.TestConfiguration.deleted_at.is_(None),
            models.Status.name == status_name,
            project_filter,
            next_run_at.isnot(None),
            cast(next_run_at, DateTime(timezone=True)) <= now,
        )
        .all()
    )
    return [row.id for row in rows]


def lock_schedule(db: Session, config_id: uuid.UUID) -> bool:
    """Lock the schedule's row for this transaction, or ``False`` if another worker has it."""
    row = (
        db.query(models.TestConfiguration.id)
        .filter(models.TestConfiguration.id == config_id)
        .with_for_update(skip_locked=True)
        .first()
    )
    return row is not None


def get_schedule(db: Session, config_id: uuid.UUID) -> Optional[models.TestConfiguration]:
    """A configuration that has a schedule, or ``None``."""
    return _scheduled_configurations(db).filter(models.TestConfiguration.id == config_id).first()


def list_schedules(
    db: Session,
    *,
    test_set_id: uuid.UUID | None = None,
    status_names: list[str] | None = None,
) -> List[models.TestConfiguration]:
    query = _scheduled_configurations(db)
    if test_set_id is not None:
        query = query.filter(models.TestConfiguration.test_set_id == test_set_id)
    if status_names:
        query = query.join(
            models.Status, models.TestConfiguration.status_id == models.Status.id
        ).filter(models.Status.name.in_(status_names))
    return query.order_by(models.TestConfiguration.created_at).all()


def _runs_of(db: Session, config_id: uuid.UUID):
    return db.query(models.TestRun).filter(
        models.TestRun.test_configuration_id == config_id,
        models.TestRun.deleted_at.is_(None),
    )


def has_in_flight_run(
    db: Session, config_id: uuid.UUID, since: datetime, status_names: list[str]
) -> bool:
    """Whether the configuration has a run in ``status_names`` created after ``since``."""
    query = (
        _runs_of(db, config_id)
        .join(models.Status, models.TestRun.status_id == models.Status.id)
        .filter(models.Status.name.in_(status_names), models.TestRun.created_at >= since)
    )
    return db.query(query.exists()).scalar()


def count_schedule_runs(db: Session, config_id: uuid.UUID) -> int:
    """Runs this configuration's schedule started, for ``max_runs``."""
    return (
        _runs_of(db, config_id)
        .filter(models.TestRun.attributes["trigger"].astext == "schedule")
        .with_entities(func.count(models.TestRun.id))
        .scalar()
    ) or 0


def list_configuration_run_ids(db: Session, config_id: uuid.UUID) -> List[uuid.UUID]:
    return [row.id for row in _runs_of(db, config_id).with_entities(models.TestRun.id)]


def recent_configuration_runs(
    db: Session, config_id: uuid.UUID, limit: int = 10, offset: int = 0
) -> List[models.TestRun]:
    return (
        _runs_of(db, config_id)
        .options(joinedload(models.TestRun.status))
        .order_by(models.TestRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
