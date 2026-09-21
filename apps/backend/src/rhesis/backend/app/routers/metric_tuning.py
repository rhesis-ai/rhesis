"""Metric tuning — a metric's own cases, runs over them, and annotations of the results.

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

Judging is by exception: one case at a time through
``POST .../tuning/cases/{case_id}/annotate``, and everything still unannotated in
one action through ``POST .../tuning/annotations/accept-rest``. The verdict a
judgement is about is read from storage, never sent, so an annotation cannot be
recorded against something the metric did not say.

``POST .../tuning/improve`` reads the rejections back and asks the generation
model to rewrite the metric from them. It never writes: applying an improvement
is an ordinary metric update the frontend sends afterwards with the fields it was
shown (domain.local/adr/0006).

Only custom metrics can be tuned, and that is enforced here rather than only in
the UI. The frontend hides the tab behind a flag, but these routes are live in
every deployment -- a hidden tab is not an access rule.
"""

import logging
from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import MetricBackendType
from rhesis.backend.app.crud.metric import get_metric
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.error_handlers import internal_error
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.metric_tuning import (
    MetricTuningAnnotationCreate,
    MetricTuningCase,
    MetricTuningCaseCreate,
    MetricTuningCaseUpdate,
    MetricTuningImprovement,
    MetricTuningRun,
)
from rhesis.backend.app.schemas.metric_tuning_metadata import MetricTuningRunSummary
from rhesis.backend.app.services import metric_tuning as service
from rhesis.backend.app.services.metric_tuning.annotations import (
    AnnotationCommentRequired,
    NothingToAnnotate,
)
from rhesis.backend.app.services.metric_tuning.improve import (
    ImprovementUnavailable,
    NoStandingRejections,
)
from rhesis.backend.app.services.metric_tuning.invoke import MetricModelNotConfigured
from rhesis.backend.app.services.metric_tuning.runs import NoTuningCases, TuningRunInFlight
from rhesis.backend.jobs import launch_job
from rhesis.backend.jobs.metric_tuning import run_metric_tuning

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


def _run_response(
    db: Session,
    metric: models.Metric,
    organization_id: str,
    summary: MetricTuningRunSummary,
) -> MetricTuningRun:
    """The stored run summary plus the two things about it that are never stored.

    The agreement is read here on every request rather than written when a run
    finishes: a judgement recorded between runs -- or one a run has just invalidated
    -- has to move the number straight away. Whether the run predates the metric
    is derived for the same reason: editing the metric has to change how the run
    reads without touching the run.
    """
    # Set after construction rather than passed in: the stored summary allows
    # extra keys, so spreading it beside a keyword risks colliding with one.
    run = MetricTuningRun(**summary.model_dump(mode="json"))
    run.agreement = service.get_agreement(db, metric, organization_id)
    run.predates_metric = service.run_predates_metric(summary, metric)
    return run


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
    return service.update_tuning_case(db, metric, db_test, body)


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


# Both annotation routes are marked update for the same reason the run is: they
# write onto the metric's own cases, so whoever can edit the metric can judge it.
# Not ``annotation:create``: the row is a judgement of the metric, reachable only
# through the metric, and gating it separately would let someone tune a metric
# they cannot annotate or annotate one they cannot tune.
@router.post(
    "/{metric_id}/tuning/cases/{case_id}/annotate",
    response_model=MetricTuningCase,
    **capability(Permission.Metric.UPDATE),
)
def annotate_tuning_case(
    metric_id: UUID,
    case_id: UUID,
    body: MetricTuningAnnotationCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: models.User = Depends(require_current_user_or_token),
):
    """Accept or reject what the metric said about one case.

    A rejection needs a comment. That comment is what someone reads when
    rewriting the evaluation prompt, so a rejection without one records nothing
    worth keeping.
    """
    organization_id, user_id = tenant_context
    metric = _resolve_metric_or_raise(db, metric_id, organization_id, user_id)
    db_test = _resolve_case_or_raise(db, metric_id, case_id, organization_id)
    try:
        return service.annotate_case(db, metric, db_test, body, organization_id, user_id)
    except (NothingToAnnotate, AnnotationCommentRequired) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{metric_id}/tuning/annotations/accept-rest",
    response_model=List[MetricTuningCase],
    **capability(Permission.Metric.UPDATE),
)
def accept_remaining_tuning_cases(
    metric_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: models.User = Depends(require_current_user_or_token),
):
    """Accept every case still unannotated, and return the whole set.

    This is what stops forty cases becoming forty decisions. Cases with no
    verdict to judge -- never run, or one the metric call failed on -- are left
    unannotated rather than accepted.
    """
    organization_id, user_id = tenant_context
    metric = _resolve_metric_or_raise(db, metric_id, organization_id, user_id)
    return service.accept_remaining(db, metric, organization_id, user_id)


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
    return _run_response(db, metric, organization_id, summary)


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

    try:
        launch_job(run_metric_tuning, str(metric_id), current_user=current_user, db=db)
    except Exception as e:
        # The claim is already committed, so a dispatch that never reaches a
        # worker -- broker down, publish error -- would leave the metric refusing
        # every later run with nothing on its way to clear the claim. Released
        # here rather than left for the staleness window to pick up: this side
        # knows for certain that no run is coming.
        logger.exception("Failed to queue tuning run for metric %s", metric_id)
        service.fail_tuning_run(db, metric, organization_id, "it could not be queued.")
        raise HTTPException(
            status_code=503, detail="The run could not be queued. Please try again."
        ) from e

    return _run_response(db, metric, organization_id, summary)


# Marked update for the same reason the run is: it costs an LLM call, and it is
# the step before an update the same person is about to make. It writes nothing
# itself -- ADR-0006 -- so the write capability guards the cost and the intent,
# not the effect.
@router.post(
    "/{metric_id}/tuning/improve",
    response_model=MetricTuningImprovement,
    **capability(Permission.Metric.UPDATE),
)
def improve_metric_from_annotations(
    metric_id: UUID,
    include_run_annotations: bool = Query(
        True,
        description=(
            "Also learn from people overruling this metric on real test results, "
            "not only from its tuning cases"
        ),
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: models.User = Depends(require_current_user_or_token),
):
    """Propose a rewrite of the metric from the rejections its reviewers wrote.

    Reads both the metric's tuning cases and, unless turned off, annotations
    overruling it on real test results. Both are someone saying the metric
    judged a case wrongly.

    Synchronous, and it saves nothing. The caller is shown the current fields
    beside the proposed ones and applies them with an ordinary metric update, or
    closes the dialog -- rewriting the evaluation prompt in place would replace
    the text the annotations were made against with no diff and no undo.
    """
    organization_id, user_id = tenant_context
    metric = _resolve_metric_or_raise(db, metric_id, organization_id, user_id)

    try:
        return service.improve_from_annotations(
            db,
            metric,
            organization_id,
            current_user,
            include_run_annotations=include_run_annotations,
        )
    except NoStandingRejections as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        # The model's fields did not fit MetricUpdate, so applying them would
        # fail. That is our template or our schema, not the caller's request.
        raise internal_error(e, context=f"improving metric {metric_id} from its annotations") from e
    except ImprovementUnavailable as e:
        # Same public detail as /metrics/{id}/improve: the caller acts on it the
        # same way, and the real reason stays in the log.
        raise internal_error(
            e,
            context=f"improving metric {metric_id} from its annotations",
            status_code=400,
            public_detail=(
                "Failed to improve metric: the generation model could not be "
                "used. Check the model configured for your organization."
            ),
        ) from e
