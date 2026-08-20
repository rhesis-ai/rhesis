"""CRUD operations for metric tuning.

Part of the incremental split of the ``crud`` monolith: per-entity modules like
this one take over as the code around them is touched, and nothing new is added
to ``crud/__init__.py``.

Every function here flushes and never commits -- the request session owns the
commit (see ``get_db_with_tenant_variables`` in ``database.py``).

Tuning cases are written as a ``Prompt`` + ``Test`` pair directly, the way
``crud/explorer.py::create_explorer_test`` does, rather than through
``services/test.py::bulk_create_tests``. That service requires a requirement, a
category and a topic and ``get_or_create``s each one, which would file rows like
"Metric Tuning" into the organization's real taxonomy.
"""

import logging
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningCaseMetadata,
    MetricTuningCaseResult,
    MetricTuningReview,
    MetricTuningRunSummary,
    parse_metric_tuning_case_metadata,
    parse_metric_tuning_run_summary,
)

logger = logging.getLogger(__name__)

# Where the latest run's summary lives inside ``TestSet.attributes``. Nothing
# else writes a tuning set's attributes -- attribute regeneration early-returns
# for metric-owned sets -- but the key keeps it out of the way regardless.
RUN_SUMMARY_KEY = "tuning_run"


# --- Test sets ---------------------------------------------------------------------


def get_tuning_test_set(
    db: Session, metric_id: uuid.UUID, organization_id: str
) -> Optional[models.TestSet]:
    """The test set owned by this metric, or None if it has no tuning set yet.

    A metric owns at most one tuning set -- ``services/metric_tuning/test_sets.py``
    is the only writer of ``TestSet.metric_id`` and creates it once, lazily.
    """
    return (
        db.query(models.TestSet)
        .filter(
            models.TestSet.metric_id == metric_id,
            models.TestSet.organization_id == organization_id,
        )
        .first()
    )


def mark_test_set_as_tuning(
    db: Session, test_set: models.TestSet, metric_id: uuid.UUID
) -> models.TestSet:
    """Flag a test set as owned by ``metric_id`` via the ``metric_id`` column.

    Kept off ``TestSetCreate`` deliberately: a client-settable ``metric_id``
    would let anyone hide a test set from the list, so the column is written
    server-side only (mirrors ``mark_test_set_as_explorer``).
    """
    test_set.metric_id = metric_id
    db.flush()
    db.refresh(test_set)
    return test_set


def get_run_summary(test_set: models.TestSet) -> MetricTuningRunSummary:
    """The latest run's summary. A set nobody has run reads as ``never_run``."""
    attributes = test_set.attributes or {}
    return parse_metric_tuning_run_summary(attributes.get(RUN_SUMMARY_KEY))


def set_run_summary(
    db: Session, test_set: models.TestSet, summary: MetricTuningRunSummary
) -> models.TestSet:
    """Overwrite the latest run's summary. Only the latest is ever kept.

    The whole ``attributes`` dict is reassigned rather than mutated in place:
    SQLAlchemy does not track mutation inside a plain JSONB column, so an
    in-place edit would flush nothing.
    """
    attributes = dict(test_set.attributes or {})
    attributes[RUN_SUMMARY_KEY] = summary.model_dump(mode="json", exclude_none=True)
    test_set.attributes = attributes
    db.flush()
    return test_set


# --- Tuning cases --------------------------------------------------------------------


def get_tuning_cases(
    db: Session, test_set_id: uuid.UUID, organization_id: str
) -> List[models.Test]:
    """Every tuning case in a tuning test set, oldest first.

    The prompt is eager-loaded because callers always serialize it -- it holds
    the case payload the metric is shown.

    ``id`` breaks ties on ``created_at``: two cases added in the same instant
    would otherwise come back in whatever order the planner chose, and the grid
    would reshuffle between polls.
    """
    return (
        db.query(models.Test)
        .options(joinedload(models.Test.prompt))
        .join(
            test_test_set_association,
            models.Test.id == test_test_set_association.c.test_id,
        )
        .filter(
            test_test_set_association.c.test_set_id == test_set_id,
            models.Test.organization_id == organization_id,
        )
        .order_by(models.Test.created_at.asc(), models.Test.id.asc())
        .all()
    )


def get_tuning_case(
    db: Session, test_set_id: uuid.UUID, test_id: uuid.UUID, organization_id: str
) -> Optional[models.Test]:
    """Load one tuning case, but only if it belongs to the given tuning set.

    The membership join is the point: it doubles as the authorization check for
    the per-case endpoints, so a case id from another metric's set 404s instead
    of being edited across metrics. Same approach as
    ``crud/explorer.py::get_test_in_test_set``.
    """
    return (
        db.query(models.Test)
        .options(joinedload(models.Test.prompt))
        .join(
            test_test_set_association,
            models.Test.id == test_test_set_association.c.test_id,
        )
        .filter(
            models.Test.id == test_id,
            test_test_set_association.c.test_set_id == test_set_id,
            models.Test.organization_id == organization_id,
        )
        .first()
    )


def create_tuning_case(
    db: Session,
    *,
    organization_id: str,
    user_id: str,
    metric_id: uuid.UUID,
    content: str,
    metadata: MetricTuningCaseMetadata,
) -> models.Test:
    """Insert a tuning case: the prompt holding the case payload, then the test.

    ``content`` is the serialized case payload -- what the metric is shown
    (ADR-0003). ``expected_response`` is deliberately left unset: it held the
    expected verdict until ADR-0005 retired that model, and a tuning case now
    records no answer key at all.

    Associating the test with its test set is the caller's job -- that goes
    through the shared ``create_test_set_associations`` service.
    """
    db_prompt = models.Prompt(
        content=content,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(db_prompt)
    db.flush()

    db_test = models.Test(
        prompt_id=db_prompt.id,
        test_metadata=metadata.model_dump(mode="json", exclude_none=True),
        organization_id=organization_id,
        user_id=user_id,
        metric_id=metric_id,
    )
    db.add(db_test)
    db.flush()
    db.refresh(db_test)
    return db_test


def remove_case_from_test_set(db: Session, test_set_id: uuid.UUID, test_id: uuid.UUID) -> None:
    """Drop the association row linking a tuning case to its test set.

    Detaches only -- soft-deleting the test itself is a separate
    ``crud.delete_test`` call, and the order matters: ``delete_test`` reads the
    association table to decide which test sets to recalculate, so a case
    detached first is deliberately left out of that.
    """
    db.execute(
        test_test_set_association.delete().where(
            test_test_set_association.c.test_id == test_id,
            test_test_set_association.c.test_set_id == test_set_id,
        )
    )
    db.flush()


def set_case_result(
    db: Session, db_test: models.Test, result: MetricTuningCaseResult
) -> models.Test:
    """Record what the metric said about this case, overwriting the last run's.

    Writes only the ``result`` key. The case payload is what is being scored and
    is never touched by scoring it, and the reviews beside it are human-authored
    history -- wiping those on every run would destroy the comments the feature
    exists to produce (ADR-0005).
    """
    metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
    metadata.result = result
    db_test.test_metadata = metadata.model_dump(mode="json", exclude_none=True)
    db.flush()
    return db_test


def set_case_reviews(
    db: Session, db_test: models.Test, reviews: List[MetricTuningReview]
) -> models.Test:
    """Overwrite a case's review history, leaving the run's result alone.

    The whole list goes down at once because the service decides its shape --
    whether a review replaced the last one, and which one the cap evicted.
    """
    metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
    metadata.reviews = reviews
    db_test.test_metadata = metadata.model_dump(mode="json", exclude_none=True)
    db.flush()
    db.refresh(db_test)
    return db_test


def update_tuning_case(
    db: Session,
    db_test: models.Test,
    *,
    content: Optional[str] = None,
    metadata: Optional[MetricTuningCaseMetadata] = None,
) -> models.Test:
    """Apply a partial update to a tuning case.

    Only non-None arguments are written, so a PUT that omits a field leaves it
    alone.
    """
    if db_test.prompt is not None and content is not None:
        db_test.prompt.content = content

    if metadata is not None:
        db_test.test_metadata = metadata.model_dump(mode="json", exclude_none=True)

    db.flush()
    db.refresh(db_test)
    return db_test
