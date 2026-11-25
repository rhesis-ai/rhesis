"""Test run schedules: run a test set later, once or on a timetable.

A schedule is a test configuration with ``attributes["schedule"]``; its id is the
configuration's. The logic is in ``services/test_run_schedule``.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request
from pydantic import AwareDatetime, ValidationError
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.quota_gates import require_job_capacity, require_quota
from rhesis.backend.app.auth.rbac import require_object
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
    per_user_rate_limit,
)
from rhesis.backend.app.error_handlers import internal_error
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.user import User
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.test_run_schedule import (
    OccurrenceEdit,
    OccurrencesOut,
    ScheduleCreate,
    SchedulePreview,
    ScheduleSpecIn,
    ScheduleUpdate,
    TestRunScheduleDetail,
    TestRunScheduleOut,
)
from rhesis.backend.app.services.test_configuration_execution import RunSubmissionError
from rhesis.backend.app.services.test_run_schedule import service, views
from rhesis.backend.app.services.test_run_schedule.errors import (
    ScheduleConflict,
    ScheduleNotFound,
    ScheduleValidationError,
)
from rhesis.backend.app.utils.execution_validation import handle_execution_error
from rhesis.backend.app.utils.rate_limit import EXECUTION_RATE_LIMIT

router = RhesisRouter(
    prefix="/test_run_schedules",
    tags=["test_run_schedules"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
    resource="test_run",
)


@contextmanager
def _schedule_errors(operation: str) -> Iterator[None]:
    """Turn service errors into the statuses the API documents."""
    try:
        yield
    except HTTPException:
        raise
    except ScheduleNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScheduleConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ScheduleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValidationError as exc:
        messages = "; ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors())
        raise HTTPException(status_code=422, detail=messages) from exc
    except RunSubmissionError as exc:
        raise internal_error(exc.__cause__ or exc, context=f"failed to {operation}") from exc
    except Exception as exc:
        raise handle_execution_error(exc, operation=operation) from exc


def _org(tenant_context) -> str:
    return str(tenant_context[0])


def _saved(db: Session, config) -> TestRunScheduleOut:
    db.commit()
    db.refresh(config)
    return TestRunScheduleOut.model_validate(views.schedule_item(config))


@router.post("/", response_model=list[TestRunScheduleOut], **capability(Permission.TestRun.EXECUTE))
def create_test_run_schedule(
    body: ScheduleCreate,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Schedule a test set, or several with one schedule each. Nothing runs yet."""
    with _schedule_errors("schedule test set"):
        if body.test_set_ids:
            configs = service.create_schedules_bulk(
                db,
                current_user,
                test_set_ids=body.test_set_ids,
                endpoint_id=body.endpoint_id,
                spec=body.schedule,
                run_settings=body.run_settings,
            )
        else:
            configs = [
                service.create_schedule(
                    db,
                    current_user,
                    test_set_id=body.test_set_id,
                    endpoint_id=body.endpoint_id,
                    spec=body.schedule,
                    run_settings=body.run_settings,
                )
            ]
        db.commit()
        for config in configs:
            db.refresh(config)
        return [TestRunScheduleOut.model_validate(views.schedule_item(c)) for c in configs]


@router.post("/preview", response_model=SchedulePreview, **capability(Permission.TestRun.READ))
def preview_test_run_schedule(body: dict):
    """When a schedule would run, in plain words, with the next three times."""
    with _schedule_errors("preview schedule"):
        return views.preview(ScheduleSpecIn.model_validate(body))


@router.get("/", response_model=list[TestRunScheduleOut], **capability(Permission.TestRun.READ))
def list_test_run_schedules(
    test_set_id: UUID | None = None,
    status: list[str] | None = Query(None),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    return views.list_items(db, _org(tenant_context), test_set_id=test_set_id, status_names=status)


@router.get("/occurrences", response_model=OccurrencesOut, **capability(Permission.TestRun.READ))
def list_test_run_schedule_occurrences(
    # Aware only: a time without an offset can't be compared with stored UTC times.
    start: AwareDatetime = Query(..., alias="from"),
    end: AwareDatetime = Query(..., alias="to"),
    db: Session = Depends(get_tenant_db_session),
):
    """Upcoming runs of every active schedule in a window of up to 42 days."""
    try:
        return views.occurrence_window(db, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/{schedule_id}", response_model=TestRunScheduleDetail, **capability(Permission.TestRun.READ)
)
def read_test_run_schedule(
    schedule_id: UUID,
    runs_limit: int = Query(10, ge=1, le=100),
    runs_offset: int = Query(0, ge=0),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    with _schedule_errors("read schedule"):
        config = service.load_schedule(db, schedule_id)
        return views.detail(db, config, _org(tenant_context), runs_limit, runs_offset)


@router.patch(
    "/{schedule_id}", response_model=TestRunScheduleOut, **capability(Permission.TestRun.UPDATE)
)
def update_test_run_schedule(
    schedule_id: UUID, body: ScheduleUpdate, db: Session = Depends(get_tenant_db_session)
):
    """Change the schedule from now on. Runs that happened keep their settings."""
    with _schedule_errors("update schedule"):
        config = service.update_schedule(
            db, service.load_schedule(db, schedule_id, for_update=True), body
        )
        return _saved(db, config)


@router.delete("/{schedule_id}", response_model=TestRunScheduleOut)
def delete_test_run_schedule(
    schedule_id: UUID,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Stop the schedule. Its past runs are kept. Same ownership rule as deleting a test run."""
    with _schedule_errors("delete schedule"):
        config = service.load_schedule(db, schedule_id, for_update=True)
        require_object(
            request,
            current_user,
            Permission.TestRun.DELETE_OWN,
            config,
            db=db,
            detail="Not authorized to delete this schedule",
        )
        item = TestRunScheduleOut.model_validate(views.schedule_item(config))
        service.delete_schedule(db, config)
        db.commit()
        return item


@router.post(
    "/{schedule_id}/run_now",
    **capability(Permission.TestRun.EXECUTE),
    dependencies=[per_user_rate_limit(EXECUTION_RATE_LIMIT)],
)
def run_test_run_schedule_now(
    schedule_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    _quota_gate: Organization = Depends(require_quota(QuotaResource.TEST_EXECUTIONS)),
    _job_capacity: None = Depends(require_job_capacity),
):
    """Start a run now, as the caller. The schedule's own times don't change."""
    with _schedule_errors("run schedule now"):
        task, test_run = service.run_now(
            db, service.load_schedule(db, schedule_id, for_update=True), current_user
        )
        return {"test_run_id": str(test_run.id), "task_id": task.id, "status": "submitted"}


@router.post(
    "/{schedule_id}/skip_next",
    response_model=TestRunScheduleOut,
    **capability(Permission.TestRun.UPDATE),
)
def skip_next_test_run_schedule_run(
    schedule_id: UUID, db: Session = Depends(get_tenant_db_session)
):
    with _schedule_errors("skip the next run"):
        return _saved(
            db, service.skip_next(db, service.load_schedule(db, schedule_id, for_update=True))
        )


@router.post(
    "/{schedule_id}/pause",
    response_model=TestRunScheduleOut,
    **capability(Permission.TestRun.UPDATE),
)
def pause_test_run_schedule(schedule_id: UUID, db: Session = Depends(get_tenant_db_session)):
    with _schedule_errors("pause schedule"):
        return _saved(
            db, service.pause(db, service.load_schedule(db, schedule_id, for_update=True))
        )


@router.post(
    "/{schedule_id}/resume",
    response_model=TestRunScheduleOut,
    **capability(Permission.TestRun.UPDATE),
)
def resume_test_run_schedule(schedule_id: UUID, db: Session = Depends(get_tenant_db_session)):
    with _schedule_errors("resume schedule"):
        return _saved(
            db, service.resume(db, service.load_schedule(db, schedule_id, for_update=True))
        )


@router.post(
    "/{schedule_id}/take_over",
    response_model=TestRunScheduleOut,
    **capability(Permission.TestRun.UPDATE),
)
def take_over_test_run_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Become the schedule's owner, so its runs execute as you. Also needs run permission."""
    with _schedule_errors("take over schedule"):
        config = service.take_over(
            db, service.load_schedule(db, schedule_id, for_update=True), current_user
        )
        return _saved(db, config)


@router.patch(
    "/{schedule_id}/occurrences/{occurrence}",
    response_model=TestRunScheduleOut,
    **capability(Permission.TestRun.UPDATE),
)
def edit_test_run_schedule_occurrence(
    schedule_id: UUID,
    occurrence: datetime,
    body: OccurrenceEdit,
    scope: Literal["one", "following"] = "one",
    db: Session = Depends(get_tenant_db_session),
):
    """Change one upcoming run, or that run and the ones after it."""
    with _schedule_errors("change the run"):
        config = service.load_schedule(db, schedule_id, for_update=True)
        return _saved(db, service.edit_occurrence(db, config, occurrence, scope, body))


@router.delete(
    "/{schedule_id}/occurrences/{occurrence}",
    response_model=TestRunScheduleOut,
    **capability(Permission.TestRun.UPDATE),
)
def delete_test_run_schedule_occurrence(
    schedule_id: UUID,
    occurrence: datetime,
    scope: Literal["one", "following"] = "one",
    db: Session = Depends(get_tenant_db_session),
):
    """Skip one upcoming run, or end the schedule just before it."""
    with _schedule_errors("delete the run"):
        config = service.load_schedule(db, schedule_id, for_update=True)
        return _saved(db, service.delete_occurrence(db, config, occurrence, scope))
