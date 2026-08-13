"""Metric tuning — a metric's own set of labelled cases, and runs over them.

Mounted under ``/metrics`` with ``resource="metric"``, so the four existing
``metric:read|create|update|delete`` capabilities cover these routes and no
capability catalog migration is needed. Kept in its own file rather than added to
``routers/metric.py`` so the feature can be removed by deleting one file and one
import.

The tuning test set is created on the first case ``POST``: ``GET`` returns an
empty list for a metric nobody has tuned yet rather than creating rows on a read.

A run is started only by ``POST .../tuning/run`` and never as a side effect of
anything else -- one LLM call per case is not something an edit should trigger.
The work happens in a background task; ``GET .../tuning/run`` is what the
interface polls while it goes.

Only custom metrics can be tuned, and that is enforced here rather than only in
the UI. The frontend hides the tab behind a flag, but these routes are live in
every deployment -- a hidden tab is not an access rule.
"""

import logging
from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import MetricBackendType
from rhesis.backend.app.crud.metric import get_metric
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.metric_tuning import (
    MetricTuningCase,
    MetricTuningCaseCreate,
    MetricTuningCaseUpdate,
    MetricTuningRun,
)
from rhesis.backend.app.services import metric_tuning as service
from rhesis.backend.app.services.metric_tuning.invoke import MetricModelNotConfigured
from rhesis.backend.app.services.metric_tuning.runs import NoTuningCases, TuningRunInFlight
from rhesis.backend.app.services.metric_tuning.verdict import InvalidVerdict
from rhesis.backend.tasks import task_launcher
from rhesis.backend.tasks.metric_tuning import run_metric_tuning

logger = logging.getLogger(__name__)

router = RhesisRouter(
    prefix="/metrics",
    tags=["metrics"],
    responses={404: {"description": "Not found"}},
    resource="metric",
)


def _resolve_metric_or_raise(
    db: Session, metric_id: UUID, organization_id: str, user_id: str
) -> models.Metric:
    """Load the metric and refuse it if it is not a custom one.

    A framework-provided metric has a prompt the organization does not own, so
    there is nothing for a tuning case to be tuning.
    """
    metric = get_metric(db, metric_id=metric_id, organization_id=organization_id, user_id=user_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")

    backend_type = getattr(metric.backend_type, "type_value", None)
    if (backend_type or "").lower() != MetricBackendType.CUSTOM:
        raise HTTPException(
            status_code=400,
            detail="Only custom metrics can be tuned.",
        )
    return metric


def _resolve_case_or_raise(
    db: Session, metric_id: UUID, case_id: UUID, organization_id: str
) -> models.Test:
    """Load a case through the membership join, which is also the auth check.

    A case id belonging to another metric's tuning set 404s rather than being
    edited across metrics.
    """
    db_test = service.get_tuning_case(db, metric_id, case_id, organization_id)
    if db_test is None:
        raise HTTPException(status_code=404, detail="Tuning case not found")
    return db_test


@router.get("/{metric_id}/tuning/cases", response_model=List[MetricTuningCase])
def read_tuning_cases(
    metric_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: models.User = Depends(require_current_user_or_token),
):
    """List a metric's tuning cases. Empty when it has no tuning test set yet."""
    organization_id, user_id = tenant_context
    metric = _resolve_metric_or_raise(db, metric_id, organization_id, user_id)
    return service.list_tuning_cases(db, metric, organization_id)


@router.post("/{metric_id}/tuning/cases", response_model=MetricTuningCase, status_code=201)
def create_tuning_case(
    metric_id: UUID,
    body: MetricTuningCaseCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: models.User = Depends(require_current_user_or_token),
):
    """Add a tuning case, creating the metric's tuning test set on first call."""
    organization_id, user_id = tenant_context
    metric = _resolve_metric_or_raise(db, metric_id, organization_id, user_id)
    try:
        return service.create_tuning_case(db, metric, body, organization_id, user_id)
    except InvalidVerdict as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{metric_id}/tuning/cases/{case_id}", response_model=MetricTuningCase)
def update_tuning_case(
    metric_id: UUID,
    case_id: UUID,
    body: MetricTuningCaseUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: models.User = Depends(require_current_user_or_token),
):
    """Update a tuning case. Fields omitted from the body are left unchanged."""
    organization_id, user_id = tenant_context
    metric = _resolve_metric_or_raise(db, metric_id, organization_id, user_id)
    db_test = _resolve_case_or_raise(db, metric_id, case_id, organization_id)
    try:
        return service.update_tuning_case(db, metric, db_test, body)
    except InvalidVerdict as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{metric_id}/tuning/cases/{case_id}")
def delete_tuning_case(
    metric_id: UUID,
    case_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: models.User = Depends(require_current_user_or_token),
):
    """Remove a tuning case from the metric's test set."""
    organization_id, user_id = tenant_context
    _resolve_metric_or_raise(db, metric_id, organization_id, user_id)
    db_test = _resolve_case_or_raise(db, metric_id, case_id, organization_id)
    service.delete_tuning_case(db, metric_id, db_test, organization_id, user_id)
    return {"deleted": True, "case_id": str(case_id)}


@router.get("/{metric_id}/tuning/run", response_model=MetricTuningRun)
def read_tuning_run(
    metric_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: models.User = Depends(require_current_user_or_token),
):
    """The metric's latest run. ``never_run`` when there has not been one."""
    organization_id, user_id = tenant_context
    metric = _resolve_metric_or_raise(db, metric_id, organization_id, user_id)
    summary = service.get_tuning_run(db, metric, organization_id)
    return MetricTuningRun(**summary.model_dump(mode="json"))


# Marked update rather than left to the POST-means-create convention: starting a
# run writes results onto the metric's own cases, so whoever can edit the metric
# can run it. An explicit `metric:execute` would need a capability catalog
# migration for a feature still behind a flag.
@router.post(
    "/{metric_id}/tuning/run",
    response_model=MetricTuningRun,
    status_code=202,
    **capability(Permission.Metric.UPDATE),
)
def start_tuning_run(
    metric_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: models.User = Depends(require_current_user_or_token),
):
    """Start a run over the metric's cases and hand back the in-progress summary.

    Nothing but this route starts a run: every run is one LLM call per case, so
    an edit to a case or an evaluation prompt must never trigger one.
    """
    organization_id, user_id = tenant_context
    metric = _resolve_metric_or_raise(db, metric_id, organization_id, user_id)

    try:
        summary = service.start_tuning_run(db, metric, organization_id, user_id)
    except (NoTuningCases, MetricModelNotConfigured) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TuningRunInFlight as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Committed before dispatch so the worker cannot start on a session that has
    # not yet written the claim it is about to update.
    db.commit()

    task_launcher(run_metric_tuning, str(metric_id), current_user=current_user, db=db)

    return MetricTuningRun(**summary.model_dump(mode="json"))
