"""Attach deep-link context to annotations.

The annotations list and the hub grid show rows from every entity type at once,
so each row carries enough of its parent's identity to link back to it. Loaded in
a handful of batched queries rather than per row.
"""

import uuid
from typing import Dict, List, Sequence

from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models, schemas
from rhesis.backend.app.constants import EntityType


def attach_context(
    db: Session,
    annotations: Sequence[models.Annotation],
) -> List[schemas.AnnotationDetail]:
    if not annotations:
        return []

    result_ids = {a.entity_id for a in annotations if a.entity_type == EntityType.TEST_RESULT.value}
    trace_ids = {a.entity_id for a in annotations if a.entity_type == EntityType.TRACE.value}

    test_results: Dict[uuid.UUID, models.TestResult] = {}
    if result_ids:
        rows = (
            db.query(models.TestResult)
            .options(joinedload(models.TestResult.test).joinedload(models.Test.requirement))
            .filter(models.TestResult.id.in_(result_ids))
            .all()
        )
        test_results = {r.id: r for r in rows}

    traces: Dict[uuid.UUID, models.Trace] = {}
    if trace_ids:
        rows = db.query(models.Trace).filter(models.Trace.id.in_(trace_ids)).all()
        traces = {t.id: t for t in rows}

    run_ids = {
        parent.test_run_id
        for parent in (*test_results.values(), *traces.values())
        if parent.test_run_id
    }
    runs: Dict[uuid.UUID, models.TestRun] = {}
    if run_ids:
        rows = (
            db.query(models.TestRun)
            .options(joinedload(models.TestRun.test_configuration))
            .filter(models.TestRun.id.in_(run_ids))
            .all()
        )
        runs = {r.id: r for r in rows}

    details = []
    for annotation in annotations:
        detail = schemas.AnnotationDetail.model_validate(annotation, from_attributes=True)
        if annotation.entity_type == EntityType.TEST_RESULT.value:
            detail.context = _test_result_context(test_results.get(annotation.entity_id), runs)
        elif annotation.entity_type == EntityType.TRACE.value:
            detail.context = _trace_context(traces.get(annotation.entity_id), runs)
        details.append(detail)
    return details


def _run_context(parent, runs: Dict[uuid.UUID, models.TestRun]) -> schemas.AnnotationContext:
    """The run half of the context, shared by test results and traces."""
    ctx = schemas.AnnotationContext(project_id=parent.project_id)
    run = runs.get(parent.test_run_id) if parent.test_run_id else None
    if run is None:
        return ctx
    ctx.test_run_id = run.id
    ctx.test_run_name = run.name
    if run.test_configuration:
        ctx.test_set_id = run.test_configuration.test_set_id
    return ctx


def _test_result_context(result, runs) -> schemas.AnnotationContext | None:
    if result is None:
        return None
    ctx = _run_context(result, runs)
    ctx.test_result_id = result.id
    if result.test and result.test.requirement:
        ctx.requirement_id = result.test.requirement.id
        ctx.requirement_name = result.test.requirement.name
    return ctx


def _trace_context(trace, runs) -> schemas.AnnotationContext | None:
    if trace is None:
        return None
    ctx = _run_context(trace, runs)
    ctx.trace_db_id = trace.id
    ctx.trace_id = trace.trace_id
    ctx.span_name = trace.span_name
    return ctx
