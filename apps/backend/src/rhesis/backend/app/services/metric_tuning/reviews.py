"""Reviewing what a metric said about its own tuning cases.

Reviewing is by exception: the reviewer marks the cases the metric got wrong,
with a comment saying what is wrong, and accepts everything left in one action.
The comments are the point of the feature -- they are what someone reads when
rewriting an evaluation prompt -- so everything here is in service of not losing
them (domain.local/adr/0005).

Three rules do the work:

* **Replace, do not append.** Re-judging a case whose verdict has not materially
  moved overwrites that reviewer's last review. A mis-click corrected a second
  later must not spend two of the ten slots.
* **Accumulate across runs.** Reviews are human-authored and are not run output,
  so a run never clears them -- it only overwrites the machine's ``result``.
* **Evict accepts, never comments.** At the cap the oldest review carrying no
  comment goes. A case reviewed with a comment ten times keeps all ten rather
  than dropping what a human wrote.

The verdict a review is about is read here from the stored result, never taken
from the caller, so a review cannot claim to be about something the metric did
not say.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud import metric_tuning as crud_metric_tuning
from rhesis.backend.app.schemas.metric_tuning import (
    MetricTuningCase,
    MetricTuningReviewCreate,
    TuningCaseOutcome,
)
from rhesis.backend.app.schemas.metric_tuning_metadata import (
    REVIEW_HISTORY_LIMIT,
    MetricTuningCaseMetadata,
    MetricTuningReview,
    ReviewDecision,
    parse_metric_tuning_case_metadata,
)
from rhesis.backend.app.services.metric_tuning.cases import to_api
from rhesis.backend.app.services.metric_tuning.material_change import review_still_stands
from rhesis.backend.app.services.metric_tuning.outcome import case_outcome, current_verdict
from rhesis.backend.app.services.metric_tuning.test_sets import get_tuning_test_set

logger = logging.getLogger(__name__)


class NothingToReview(Exception):
    """A review was offered for a case that carries no verdict to judge."""


class ReviewCommentRequired(Exception):
    """A rejection arrived without the comment that says what is wrong."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_review(
    metric: models.Metric,
    verdict: str,
    body: MetricTuningReviewCreate,
    reviewer_id: Optional[str],
) -> MetricTuningReview:
    """Turn a judgement into the record to store, or refuse it.

    The score type is stored with the verdict because a review is only valid
    under the score type it was made against: change a metric from numeric to
    categorical and every stored verdict means something else.
    """
    comment = (body.comment or "").strip()
    if body.decision == ReviewDecision.REJECTED and not comment:
        raise ReviewCommentRequired("A rejection needs a comment saying what the metric got wrong.")

    return MetricTuningReview(
        decision=body.decision,
        # An accept carries no comment, which is also what makes it the review
        # the history cap is allowed to drop.
        comment=comment or None,
        verdict=verdict,
        score_type=metric.score_type,
        reviewer_id=str(reviewer_id) if reviewer_id else None,
        reviewed_at=_now(),
    )


def _store(
    metric: models.Metric,
    reviews: List[MetricTuningReview],
    review: MetricTuningReview,
) -> List[MetricTuningReview]:
    """Place a new review in the history, replacing or appending as the rules say."""
    for index in range(len(reviews) - 1, -1, -1):
        existing = reviews[index]
        if existing.reviewer_id != review.reviewer_id:
            continue
        # Only this reviewer's most recent review is a candidate: an older one is
        # history even when it happens to be about the same verdict.
        if review_still_stands(metric, existing.verdict, existing.score_type, review.verdict):
            reviews[index] = review
            return reviews
        break

    if len(reviews) >= REVIEW_HISTORY_LIMIT:
        oldest_accept = next((i for i, r in enumerate(reviews) if r.evictable), None)
        if oldest_accept is None:
            # Every review here carries a comment, so the cap gives way instead.
            logger.info(
                "Tuning case review history is at the cap with no accept to evict; keeping all %s",
                len(reviews),
            )
        else:
            del reviews[oldest_accept]

    reviews.append(review)
    return reviews


def _record(
    db: Session,
    metric: models.Metric,
    db_test: models.Test,
    metadata: MetricTuningCaseMetadata,
    body: MetricTuningReviewCreate,
    reviewer_id: Optional[str],
) -> models.Test:
    """Write one review onto one case. The caller has already read the metadata."""
    verdict = current_verdict(metadata)
    if not verdict:
        raise NothingToReview(
            "This case has no verdict to judge yet. Run the metric over its cases first."
        )

    review = _build_review(metric, verdict, body, reviewer_id)
    reviews = _store(metric, list(metadata.reviews), review)
    return crud_metric_tuning.set_case_reviews(db, db_test, reviews)


def review_case(
    db: Session,
    metric: models.Metric,
    db_test: models.Test,
    body: MetricTuningReviewCreate,
    reviewer_id: Optional[str],
) -> MetricTuningCase:
    """Record one reviewer's judgement of what the metric said about one case."""
    metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
    db_test = _record(db, metric, db_test, metadata, body, reviewer_id)
    return to_api(db_test, metric)


def accept_remaining(
    db: Session,
    metric: models.Metric,
    organization_id: str,
    reviewer_id: Optional[str],
) -> List[MetricTuningCase]:
    """Accept every case still unreviewed, and return the whole set.

    This is what stops forty cases becoming forty decisions. A case with no
    verdict to judge -- never run, or one the metric call failed on -- is left
    alone: there is nothing there to agree with.
    """
    test_set = get_tuning_test_set(db, metric.id, organization_id)
    if not test_set:
        return []

    accept = MetricTuningReviewCreate(decision=ReviewDecision.ACCEPTED)
    cases = crud_metric_tuning.get_tuning_cases(db, test_set.id, organization_id)

    accepted = 0
    for db_test in cases:
        metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
        outcome, _, _ = case_outcome(metric, metadata)
        if outcome != TuningCaseOutcome.UNREVIEWED or not current_verdict(metadata):
            continue
        _record(db, metric, db_test, metadata, accept, reviewer_id)
        accepted += 1

    logger.info("Accepted %s unreviewed tuning cases for metric %s", accepted, metric.id)
    return [to_api(db_test, metric) for db_test in cases]
