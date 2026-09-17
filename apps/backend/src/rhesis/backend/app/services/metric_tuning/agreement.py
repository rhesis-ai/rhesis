"""Agreement: the share of judged cases the reviewer accepted.

One number for a whole tuning test set, and the only one an author watches while
editing an evaluation prompt -- change the wording, run again, see whether it
went up.

It was originally the share of cases where the metric's verdict equalled a stored
expected verdict. There is no stored verdict any more (domain.local/adr/0005), so
it means the same thing to its reader and is computed completely differently:
accepted over accepted plus rejected, both of them a human's judgement.

**The denominator is the whole design.** Every shortcut here inflates it. An
unannotated case counted as accepted makes a set nobody looked at report itself
perfect; an errored case counted as rejected makes a flaky provider read as a bad
metric. Both are left out of the ratio and reported beside it instead.

Nothing is stored. The outcomes this folds over are themselves derived from the
metric's current threshold on every read (``outcome.py``), so an annotation a run
has just invalidated stops counting immediately rather than at the next write.
"""

import logging
from collections import Counter
from typing import Iterable

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud import metric_tuning as crud_metric_tuning
from rhesis.backend.app.crud.annotation import get_annotations_for_tests
from rhesis.backend.app.schemas.metric_tuning import TuningAgreement, TuningCaseOutcome
from rhesis.backend.app.schemas.metric_tuning_metadata import parse_metric_tuning_case_metadata
from rhesis.backend.app.services.metric_tuning.outcome import case_outcome
from rhesis.backend.app.services.metric_tuning.test_sets import get_tuning_test_set

logger = logging.getLogger(__name__)

# Places to round the ratio to. Enough for any display, and it keeps two out of
# three off the wire as 0.6667 rather than 0.6666666666666666.
RATIO_PRECISION = 4


def agreement_over(outcomes: Iterable[TuningCaseOutcome]) -> TuningAgreement:
    """Fold case outcomes into the ratio and the counts that qualify it."""
    counts = Counter(outcomes)
    accepted = counts[TuningCaseOutcome.ACCEPTED]
    rejected = counts[TuningCaseOutcome.REJECTED]
    judged = accepted + rejected

    return TuningAgreement(
        # Nothing judged is no agreement, not perfect agreement.
        ratio=round(accepted / judged, RATIO_PRECISION) if judged else None,
        judged=judged,
        accepted=accepted,
        rejected=rejected,
        unannotated=counts[TuningCaseOutcome.UNANNOTATED],
        errored=counts[TuningCaseOutcome.ERRORED],
    )


def get_agreement(db: Session, metric: models.Metric, organization_id: str) -> TuningAgreement:
    """The metric's agreement as its stored annotations stand right now.

    A metric with no tuning set has nothing to agree about, which is the same
    all-zero, no-ratio answer as a set nobody has annotated.
    """
    test_set = get_tuning_test_set(db, metric.id, organization_id)
    if not test_set:
        return TuningAgreement()

    # Ids, metadata and annotations -- two queries, whatever the case count. The
    # fold reads nothing else, and this endpoint is polled.
    stored = crud_metric_tuning.get_tuning_case_metadata(db, test_set.id, organization_id)
    annotations = get_annotations_for_tests(db, [case_id for case_id, _ in stored])

    def outcome_of(case_id, raw) -> TuningCaseOutcome:
        metadata = parse_metric_tuning_case_metadata(raw)
        return case_outcome(metric, metadata, annotations.get(case_id, ()))[0]

    return agreement_over(outcome_of(case_id, raw) for case_id, raw in stored)
