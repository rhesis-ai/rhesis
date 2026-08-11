"""Metric tuning cases: list, create, update, delete.

Column mapping for one case -- the point of the whole feature:

===========================  =============================================
API field                    Storage
===========================  =============================================
``input``                    ``prompt.content``
``expected``                 ``prompt.expected_response``
``output``                   ``test.test_metadata["output"]``
``rationale``                ``test.test_metadata["rationale"]``
(ownership)                  ``test.metric_id`` / ``test_set.metric_id``
===========================  =============================================

``expected`` sits on ``prompt.expected_response`` rather than in the JSONB
because that column already reaches metric evaluation as ``expected_output``
via ``tasks/execution/executors/data.py::get_test_and_prompt`` -- so scoring a
tuning set later needs no new plumbing to see the human's verdict. See
domain.local/adr/0002.
"""

import logging
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.crud import metric_tuning as crud_metric_tuning
from rhesis.backend.app.schemas.metric_tuning import (
    MetricTuningCase,
    MetricTuningCaseCreate,
    MetricTuningCaseUpdate,
)
from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningCaseMetadata,
    parse_metric_tuning_case_metadata,
)
from rhesis.backend.app.services.metric_tuning.test_sets import (
    get_or_create_tuning_test_set,
    get_tuning_test_set,
)
from rhesis.backend.app.services.metric_tuning.verdict import is_stale, normalize_verdict
from rhesis.backend.app.services.test import create_test_set_associations

logger = logging.getLogger(__name__)


def to_api(db_test: models.Test, metric: models.Metric) -> MetricTuningCase:
    """Project a stored case onto the API shape.

    Takes the metric because staleness is derived here rather than stored: the
    verdict is re-checked against the metric's current score type on every read.
    """
    metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
    prompt = db_test.prompt
    expected = (prompt.expected_response if prompt else None) or ""
    return MetricTuningCase(
        id=db_test.id,
        input=prompt.content if prompt else "",
        output=metadata.output or "",
        expected=expected,
        rationale=metadata.rationale,
        is_stale=is_stale(metric, expected),
        created_at=db_test.created_at,
        updated_at=db_test.updated_at,
    )


def list_tuning_cases(
    db: Session, metric: models.Metric, organization_id: str
) -> List[MetricTuningCase]:
    """Every case for a metric. Empty when the metric has no tuning set yet."""
    test_set = get_tuning_test_set(db, metric.id, organization_id)
    if not test_set:
        return []

    db_tests = crud_metric_tuning.get_tuning_cases(db, test_set.id, organization_id)
    return [to_api(db_test, metric) for db_test in db_tests]


def create_tuning_case(
    db: Session,
    metric: models.Metric,
    payload: MetricTuningCaseCreate,
    organization_id: str,
    user_id: str,
) -> MetricTuningCase:
    """Add a case, creating the metric's tuning test set if this is the first one.

    The verdict is validated against the metric before anything is written, so a
    rejected case leaves no test set behind.
    """
    expected = normalize_verdict(metric, payload.expected)

    test_set = get_or_create_tuning_test_set(db, metric, organization_id, user_id)

    db_test = crud_metric_tuning.create_tuning_case(
        db,
        organization_id=organization_id,
        user_id=user_id,
        metric_id=metric.id,
        input_text=payload.input,
        expected=expected,
        metadata=MetricTuningCaseMetadata(
            output=payload.output,
            rationale=payload.rationale,
        ),
    )

    # Goes through the shared service rather than a direct association insert, so
    # ownership is verified and the test-set counts stay consistent. Attribute
    # regeneration early-returns for metric-owned sets (services/test_set.py).
    result = create_test_set_associations(
        db=db,
        test_set_id=str(test_set.id),
        test_ids=[str(db_test.id)],
        organization_id=organization_id,
        user_id=user_id,
    )
    if not result.get("success"):
        raise ValueError(f"Failed to add case to tuning test set: {result.get('message')}")

    # Re-read through the membership join so the returned row is the one the
    # per-case endpoints will find.
    db_test = crud_metric_tuning.get_tuning_case(db, test_set.id, db_test.id, organization_id)
    return to_api(db_test, metric)


def get_tuning_case(
    db: Session, metric_id: uuid.UUID, case_id: uuid.UUID, organization_id: str
) -> Optional[models.Test]:
    """One case, or None when the metric has no tuning set or does not own it."""
    test_set = get_tuning_test_set(db, metric_id, organization_id)
    if not test_set:
        return None
    return crud_metric_tuning.get_tuning_case(db, test_set.id, case_id, organization_id)


def update_tuning_case(
    db: Session,
    metric: models.Metric,
    db_test: models.Test,
    payload: MetricTuningCaseUpdate,
) -> MetricTuningCase:
    """Apply a partial update. Fields the payload omits are left alone.

    A verdict included in the payload is validated the same way it is on create.
    An update that does not touch the verdict leaves a stale one stale rather
    than rejecting the edit -- otherwise fixing the rest of a stale case would be
    impossible.
    """
    expected = None
    if payload.expected is not None:
        expected = normalize_verdict(metric, payload.expected)

    metadata = None
    if payload.output is not None or payload.rationale is not None:
        metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
        if payload.output is not None:
            metadata.output = payload.output
        if payload.rationale is not None:
            metadata.rationale = payload.rationale

    db_test = crud_metric_tuning.update_tuning_case(
        db,
        db_test,
        input_text=payload.input,
        expected=expected,
        metadata=metadata,
    )
    return to_api(db_test, metric)


def delete_tuning_case(
    db: Session,
    metric_id: uuid.UUID,
    db_test: models.Test,
    organization_id: str,
    user_id: str,
) -> None:
    """Soft-delete a case and detach it from the tuning set.

    The association row goes first: ``crud.delete_test`` reads that table to
    decide which test sets to recalculate, so detaching up front keeps the
    metric-owned set out of it. Same ordering as
    ``crud/explorer.py::remove_tests_from_test_set``.
    """
    test_set = get_tuning_test_set(db, metric_id, organization_id)
    if test_set:
        crud_metric_tuning.remove_case_from_test_set(db, test_set.id, db_test.id)
    crud.delete_test(db, db_test.id, organization_id=organization_id, user_id=user_id)
