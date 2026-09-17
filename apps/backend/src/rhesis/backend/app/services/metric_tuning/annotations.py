"""Judging what a metric said about its own tuning cases.

Judging is by exception: the reviewer marks the cases the metric got wrong, with
a comment saying what is wrong, and accepts everything left in one action. The
comments are the point of the feature -- they are what someone reads when
rewriting an evaluation prompt -- so everything here is in service of not losing
them (domain.local/adr/0005).

Two rules do the work:

* **Append, never replace.** Re-judging a case adds a row and the newest one
  stands (``outcome.standing_annotation``). The ten-slot cap and the
  evict-accepts-never-comments rule the JSONB history needed are gone with it: a
  table has no budget to spend, so a mis-click costs nothing and no comment can
  ever be dropped to make room for one.
* **Accumulate across runs.** Judgements are human-authored and are not run
  output, so a run never clears them -- it only overwrites the machine's
  ``result``.

The verdict a judgement is about is read here from the stored result, never taken
from the caller, so it cannot claim to be about something the metric did not say.

Rows are written through ``crud.annotation`` rather than ``services.annotation``
because that service exists for the status override an annotation implies on its
parent, and a ``Test`` parent has none -- a tuning case carries no status for a
judgement to overrule. Writing straight to CRUD is also what lets accept-rest
leave the commit to the request session instead of committing once per case.
"""

import logging
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import AnnotationTarget, EntityType
from rhesis.backend.app.crud import metric_tuning as crud_metric_tuning
from rhesis.backend.app.crud.annotation import create_annotation, get_annotations_for_tests
from rhesis.backend.app.schemas.metric_tuning import (
    MetricTuningAnnotationCreate,
    MetricTuningCase,
    TuningCaseOutcome,
    TuningDecision,
)
from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningCaseMetadata,
    parse_metric_tuning_case_metadata,
)
from rhesis.backend.app.services.metric_tuning.cases import to_api
from rhesis.backend.app.services.metric_tuning.judgement import STATUS_NAMES
from rhesis.backend.app.services.metric_tuning.outcome import case_outcome, current_verdict
from rhesis.backend.app.services.metric_tuning.test_sets import get_tuning_test_set
from rhesis.backend.app.utils.crud_utils import get_or_create_status

logger = logging.getLogger(__name__)

_STATUS_DESCRIPTIONS = {
    TuningDecision.ACCEPTED: "The reviewer agreed with what the metric said",
    TuningDecision.REJECTED: "The reviewer disagreed with what the metric said",
}


class NothingToAnnotate(Exception):
    """A judgement was offered for a case that carries no verdict to judge."""


class AnnotationCommentRequired(Exception):
    """A rejection arrived without the comment that says what is wrong."""


def _resolve_status(
    db: Session,
    decision: TuningDecision,
    organization_id: str,
    user_id: Optional[str],
) -> models.Status:
    """The organization's status row for this decision, created if it is missing.

    Seeded per organization by the tuning migration and by ``initial_data.json``
    for new ones, so this normally reads. The lazy create covers an organization
    that predates both.
    """
    return get_or_create_status(
        db,
        name=STATUS_NAMES[decision],
        entity_type=EntityType.ANNOTATION,
        description=_STATUS_DESCRIPTIONS[decision],
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )


def _record(
    db: Session,
    metric: models.Metric,
    db_test: models.Test,
    metadata: MetricTuningCaseMetadata,
    body: MetricTuningAnnotationCreate,
    status_id: uuid.UUID,
    organization_id: str,
    user_id: Optional[str],
) -> models.Annotation:
    """Write one judgement onto one case. The caller has already read the metadata."""
    verdict = current_verdict(metadata)
    if not verdict:
        raise NothingToAnnotate(
            "This case has no verdict to judge yet. Run the metric over its cases first."
        )

    comment = (body.comment or "").strip()
    if body.decision == TuningDecision.REJECTED and not comment:
        raise AnnotationCommentRequired(
            "A rejection needs a comment saying what the metric got wrong."
        )

    return create_annotation(
        db,
        {
            "entity_type": EntityType.TEST.value,
            "entity_id": db_test.id,
            # The metric's id, not its name, so a renamed metric keeps its
            # judgements. Unlike a metric annotation on a test result, which
            # names the metric and has only the name to go on.
            "target_type": AnnotationTarget.METRIC.value,
            "target_reference": str(metric.id),
            "status_id": status_id,
            "comments": comment or None,
            # The verdict is stored with the score type because a judgement is
            # only valid under the score type it was made against: change a metric
            # from numeric to categorical and every stored verdict means something
            # else.
            "attributes": {"verdict": verdict, "score_type": metric.score_type},
        },
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )


def annotate_case(
    db: Session,
    metric: models.Metric,
    db_test: models.Test,
    body: MetricTuningAnnotationCreate,
    organization_id: str,
    user_id: Optional[str],
) -> MetricTuningCase:
    """Record one reviewer's judgement of what the metric said about one case."""
    metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
    status = _resolve_status(db, body.decision, organization_id, user_id)
    _record(db, metric, db_test, metadata, body, status.id, organization_id, user_id)

    # Read back rather than reusing the row just written: ``to_api`` reads the
    # decision off the status relationship, which a freshly built row has not
    # loaded.
    db.flush()
    annotations = get_annotations_for_tests(db, [db_test.id])
    return to_api(db_test, metric, annotations.get(db_test.id, ()))


def accept_remaining(
    db: Session,
    metric: models.Metric,
    organization_id: str,
    user_id: Optional[str],
) -> List[MetricTuningCase]:
    """Accept every case still unannotated, and return the whole set.

    This is what stops forty cases becoming forty decisions. A case with no
    verdict to judge -- never run, or one the metric call failed on -- is left
    alone: there is nothing there to agree with.
    """
    test_set = get_tuning_test_set(db, metric.id, organization_id)
    if not test_set:
        return []

    cases = crud_metric_tuning.get_tuning_cases(db, test_set.id, organization_id)
    annotations = get_annotations_for_tests(db, [case.id for case in cases])
    accept = MetricTuningAnnotationCreate(decision=TuningDecision.ACCEPTED)
    status = _resolve_status(db, TuningDecision.ACCEPTED, organization_id, user_id)

    accepted = 0
    for db_test in cases:
        metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
        outcome, _, _ = case_outcome(metric, metadata, annotations.get(db_test.id, ()))
        if outcome != TuningCaseOutcome.UNANNOTATED or not current_verdict(metadata):
            continue
        _record(db, metric, db_test, metadata, accept, status.id, organization_id, user_id)
        accepted += 1

    logger.info("Accepted %s unannotated tuning cases for metric %s", accepted, metric.id)

    if accepted:
        # One read for the whole set rather than one per row written, and it has
        # to come after the writes so the accepts are in it.
        db.flush()
        annotations = get_annotations_for_tests(db, [case.id for case in cases])
    return [to_api(db_test, metric, annotations.get(db_test.id, ())) for db_test in cases]
