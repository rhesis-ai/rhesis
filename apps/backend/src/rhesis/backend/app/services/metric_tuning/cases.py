"""Metric tuning cases: list, create, update, delete.

Column mapping for one case -- the point of the whole feature:

===========================  =============================================
API field                    Storage
===========================  =============================================
``input``                    ``prompt.content`` (case payload)
``output``                   ``prompt.content`` (case payload)
``reference_answer``         ``prompt.content`` (case payload)
``result``                   ``test.test_metadata["result"]``
``outcome`` / ``review``     derived from ``test.test_metadata["reviews"]``
(ownership)                  ``test.metric_id`` / ``test_set.metric_id``
===========================  =============================================

The split is not arbitrary. A tuning case puts the **metric** in the
system-under-test role: ``prompt.content`` is what that system is shown, so the
three fields it judges travel together there as the case payload (ADR-0003).
Everything a human wrote -- the reviews and their comments -- stays in the JSONB
and is shown to nobody at scoring time.

``prompt.expected_response`` is not written at all. It held the expected verdict
until ADR-0005 retired that model: a case records the situation, and the
judgement happens afterwards, on what the metric actually said.
"""

import logging
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud import metric_tuning as crud_metric_tuning
from rhesis.backend.app.crud.test import delete_test
from rhesis.backend.app.schemas.metric_tuning import (
    MetricTuningCase,
    MetricTuningCaseCreate,
    MetricTuningCaseResult,
    MetricTuningCaseUpdate,
    MetricTuningReview,
)
from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningCaseMetadata,
    parse_metric_tuning_case_metadata,
)
from rhesis.backend.app.services.metric_tuning.outcome import case_outcome
from rhesis.backend.app.services.metric_tuning.payload import (
    CasePayload,
    parse_payload,
    serialize_payload,
)
from rhesis.backend.app.services.metric_tuning.test_sets import (
    get_or_create_tuning_test_set,
    get_tuning_test_set,
)
from rhesis.backend.app.services.test import create_test_set_associations

logger = logging.getLogger(__name__)


def to_api(db_test: models.Test, metric: models.Metric) -> MetricTuningCase:
    """Project a stored case onto the API shape.

    Takes the metric because the outcome is derived here rather than stored: a
    review only stands while the metric's verdict has not materially moved under
    the metric's *current* threshold, so the question is re-answered on every
    read (ADR-0005).
    """
    metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
    prompt = db_test.prompt
    payload = parse_payload(prompt.content if prompt else None)

    # A result the run cleared but never refilled carries nothing worth showing,
    # so it reads the same as never having been run.
    result = None
    stored = metadata.result
    if stored and (stored.verdict is not None or stored.error):
        result = MetricTuningCaseResult(
            verdict=stored.verdict,
            reasoning=stored.reasoning,
            error=stored.error,
            evaluated_at=stored.evaluated_at,
        )

    outcome, review, unreviewed_reason = case_outcome(metric, metadata)

    return MetricTuningCase(
        id=db_test.id,
        input=payload.input,
        output=payload.output,
        reference_answer=payload.reference_answer,
        result=result,
        outcome=outcome,
        review=_review_to_api(review),
        unreviewed_reason=unreviewed_reason,
        created_at=db_test.created_at,
        updated_at=db_test.updated_at,
    )


def _review_to_api(review) -> Optional[MetricTuningReview]:
    """The standing review, without the bookkeeping the interface has no use for."""
    if review is None:
        return None
    return MetricTuningReview(
        decision=review.decision,
        comment=review.comment,
        verdict=review.verdict,
        reviewed_at=review.reviewed_at,
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
    body: MetricTuningCaseCreate,
    organization_id: str,
    user_id: str,
) -> MetricTuningCase:
    """Add a case, creating the metric's tuning test set if this is the first one."""
    test_set = get_or_create_tuning_test_set(db, metric, organization_id, user_id)

    case_payload = CasePayload(
        input=body.input,
        output=body.output,
        # Blank means the metric judges this case without a reference, which is
        # an absent field rather than an empty one.
        reference_answer=(body.reference_answer or "").strip() or None,
    )

    db_test = crud_metric_tuning.create_tuning_case(
        db,
        organization_id=organization_id,
        user_id=user_id,
        metric_id=metric.id,
        content=serialize_payload(case_payload),
        metadata=MetricTuningCaseMetadata(),
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
    body: MetricTuningCaseUpdate,
) -> MetricTuningCase:
    """Apply a partial update. Fields the payload omits are left alone.

    Reviews are untouched: editing the case is not judging it, and a review that
    no longer fits what the case now says is invalidated by the material-change
    rule on the next run rather than deleted here.
    """
    # Touching any payload field means re-serializing the whole payload, so the
    # parts the caller left alone have to be read back out first.
    content = None
    if body.input is not None or body.output is not None or body.reference_answer is not None:
        case_payload = parse_payload(db_test.prompt.content if db_test.prompt else None)
        if body.input is not None:
            case_payload.input = body.input
        if body.output is not None:
            case_payload.output = body.output
        if body.reference_answer is not None:
            # Blank is how the form says the reference answer was taken back.
            # Omitting the field is what leaves the stored one alone.
            case_payload.reference_answer = body.reference_answer.strip() or None
        content = serialize_payload(case_payload)

    db_test = crud_metric_tuning.update_tuning_case(db, db_test, content=content)
    return to_api(db_test, metric)


def delete_tuning_case(
    db: Session,
    metric_id: uuid.UUID,
    db_test: models.Test,
    organization_id: str,
    user_id: str,
) -> None:
    """Soft-delete a case and detach it from the tuning set.

    The association row goes first: ``delete_test`` reads that table to decide
    which test sets to recalculate, so detaching up front keeps the metric-owned
    set out of it. Same ordering as
    ``crud/explorer.py::remove_tests_from_test_set``.
    """
    test_set = get_tuning_test_set(db, metric_id, organization_id)
    if test_set:
        crud_metric_tuning.remove_case_from_test_set(db, test_set.id, db_test.id)
    delete_test(db, db_test.id, organization_id=organization_id, user_id=user_id)
