"""Rewriting a metric from the rejections its reviewers wrote.

This is what the comments were collected for. A reviewer rejects a verdict and
says what is wrong with it; this reads those comments back and asks the
generation model to rewrite the metric so it would judge those cases the way the
reviewer says.

**It never writes.** The proposed fields go back to the caller, the reviewer sees
them beside the current ones, and applying is an ordinary metric update sent
afterwards. An in-place LLM rewrite would silently replace the evaluation prompt
the reviews were made against, with no diff and no undo -- and applying by
calling the model a second time would save a different rewrite than the one on
screen. See domain.local/adr/0006.

**The prompt and the schema live here, not in the SDK.** ``MetricSynthesizer`` is
deliberately not used: this prompt is about reviews, which the SDK has no reason
to know about. What is borrowed is the model client, because it is the only path
to an LLM in this codebase and it is where provider auth, retries and usage
metering live. The consequence is that the naming, field-depth and score-type
rules now exist in two templates -- ``improve_from_reviews.jinja`` here and the
SDK's ``improve_metric.jinja`` -- and nothing keeps them in step. That is known.

**Only rejections go in.** Accepted cases are not sent, which removes the only
counter-pressure in the prompt: the cheapest rewrite satisfying five "this should
have failed" comments is a stricter metric that also breaks cases the reviewer
had accepted. The template's instruction not to move criteria the rejections do
not speak to, and the nudge to re-run afterwards, are what stand in for it.
"""

import logging
import os
from typing import Any, List, Optional

from jinja2 import Template
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud import metric_tuning as crud_metric_tuning
from rhesis.backend.app.schemas.metric import MetricUpdate
from rhesis.backend.app.schemas.metric_tuning import (
    ImprovedMetricFields,
    MetricTuningImprovement,
)
from rhesis.backend.app.schemas.metric_tuning_metadata import (
    ReviewDecision,
    parse_metric_tuning_case_metadata,
)
from rhesis.backend.app.services.metric_tuning.outcome import current_verdict, standing_review
from rhesis.backend.app.services.metric_tuning.payload import parse_payload
from rhesis.backend.app.services.metric_tuning.test_sets import get_tuning_test_set
from rhesis.backend.app.utils.user_model_utils import resolve_model

logger = logging.getLogger(__name__)

# How much of one text field reaches the model. There is no cap on how many
# rejections are sent -- forty comments are forty things the metric got wrong and
# dropping any of them silently is the one thing this must not do -- so the
# generosity is per field, and a field that was cut says so.
TEXT_FIELD_LIMIT = 4000
TRUNCATION_MARKER = " … [truncated]"

# The fields the model may propose. Compared against the metric one by one to
# work out which of them the reviewer is actually being asked to look at.
IMPROVABLE_FIELDS = tuple(ImprovedMetricFields.model_fields)

# Fixed for the metric whatever the model answers. A changed ``score_type``
# invalidates every review the metric has, and the ``categories`` list is what a
# stored categorical verdict is named from -- neither is a thing this button
# moves. See ADR-0006.
PRESERVED_FIELDS = ("score_type", "categories")


class NoStandingRejections(Exception):
    """Nothing to rewrite from: no rejection on this metric currently stands."""


class ImprovementUnavailable(Exception):
    """The generation model could not produce an improvement."""


class Rejection(BaseModel):
    """One rejected case, as the model is shown it.

    The verdict and the metric's own reasoning travel with the reviewer's comment
    because the comment is usually a reply to them -- "it called this harmless"
    means nothing without the verdict it is about.
    """

    input: str
    output: str
    reference_answer: Optional[str] = None
    verdict: Optional[str] = None
    reasoning: Optional[str] = None
    comment: str


def _load_template() -> Template:
    """The prompt, loaded from beside this module -- as ``llm_mapper`` does."""
    path = os.path.join(os.path.dirname(__file__), "improve_from_reviews.jinja")
    with open(path, "r") as handle:
        return Template(handle.read())


def _clip(text: Optional[str]) -> Optional[str]:
    """One text field, cut at the cap and marked where it was cut."""
    if text is None:
        return None
    if len(text) <= TEXT_FIELD_LIMIT:
        return text
    return text[:TEXT_FIELD_LIMIT] + TRUNCATION_MARKER


def standing_rejections(
    db: Session, metric: models.Metric, organization_id: str
) -> List[Rejection]:
    """Every rejection that still describes what the metric says now.

    Two filters, both of them the point. A case whose standing review is an
    accept is left out -- only rejections are sent. And the *standing* review is
    the one read, not the ten-deep history: a rejection a material change
    invalidated objects to a verdict the metric no longer gives, so feeding it
    back would ask for a rewrite nobody wants any more.

    Whoever wrote the review does not matter. A metric is tuned by everyone who
    reviewed it, not only by whoever pressed the button.
    """
    test_set = get_tuning_test_set(db, metric.id, organization_id)
    if not test_set:
        return []

    rejections = []
    for db_test in crud_metric_tuning.get_tuning_cases(db, test_set.id, organization_id):
        metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
        review = standing_review(metric, metadata)
        if review is None or review.decision != ReviewDecision.REJECTED:
            continue
        comment = (review.comment or "").strip()
        if not comment:
            # A rejection is only stored with a comment, so this is a row written
            # by something older or edited by hand. Nothing to read, so nothing
            # to send.
            logger.warning("Skipping a commentless rejection on tuning case %s", db_test.id)
            continue

        payload = parse_payload(db_test.prompt.content if db_test.prompt else None)
        result = metadata.result
        rejections.append(
            Rejection(
                input=_clip(payload.input) or "",
                output=_clip(payload.output) or "",
                reference_answer=_clip(payload.reference_answer),
                # Both from the latest run, not the verdict the review recorded:
                # a review survives drift that did not cross the threshold, so
                # the stored verdict and the current reasoning can be one run
                # apart. Showing the model a number beside an explanation of a
                # different number is worse than showing it either alone.
                verdict=current_verdict(metadata),
                reasoning=_clip(result.reasoning if result else None),
                comment=_clip(comment),
            )
        )
    return rejections


def _existing_fields(metric: models.Metric) -> dict:
    """The metric as the prompt and the diff both read it."""
    return {field: _unwrap(getattr(metric, field, None)) for field in IMPROVABLE_FIELDS}


def _unwrap(value: Any) -> Any:
    """A stored column with any enum wrapper taken off, ready to render or compare."""
    if isinstance(value, list):
        return [str(getattr(item, "value", item)) for item in value]
    return getattr(value, "value", value)


def _ask_model(db: Session, user: models.User, prompt: str) -> dict:
    """Put the prompt to the user's generation model and take back its answer.

    ``resolve_model(..., "generation")``: writing an evaluation prompt is a
    generation task, so the user's *generation* choice is
    the one that applies, with the system setting as a fallback only. Not
    ``resolve_metric_model`` -- that is the metric's judge, and it refuses to fall
    back because a stored verdict has to name the judge that produced it, which
    an improvement carries no obligation to do.

    Nothing stamps metering here. ``ensure_language_model`` already decides that:
    it stamps what it builds from a bare string, which is the system default,
    while an org running its own key is stamped already and must not be billed
    twice for tokens it paid for directly.
    """
    try:
        model = resolve_model(db, user, "generation")
        answer = model.generate(prompt, schema=ImprovedMetricFields)
    except Exception as e:
        raise ImprovementUnavailable(str(e)) from e

    if not isinstance(answer, dict) or "evaluation_prompt" not in answer:
        # A provider that swallows its own failure hands back something else
        # entirely -- the native client returns `{"error": ...}` rather than
        # raising -- so the shape is checked rather than assumed.
        raise ImprovementUnavailable(f"The generation model answered with {answer!r}")

    try:
        return ImprovedMetricFields.model_validate(answer).model_dump(mode="json")
    except Exception as e:
        # The model's answer did not fit the schema it was given. That is the
        # model failing, not our template, so it reads as a model failure.
        raise ImprovementUnavailable(str(e)) from e


def _preserve_fixed_fields(metric: models.Metric, proposed: dict) -> dict:
    """Put back the two fields the model is not allowed to move."""
    for field in PRESERVED_FIELDS:
        current = _unwrap(getattr(metric, field, None))
        if proposed.get(field) != current:
            logger.warning(
                "Improvement for metric %s tried to change %s from %r to %r; keeping %r",
                metric.id,
                field,
                current,
                proposed.get(field),
                current,
            )
        proposed[field] = current
    return proposed


def _blank(value: Any) -> bool:
    """Whether this proposed value amounts to "the metric has none of this"."""
    if value is None:
        return True
    if isinstance(value, (str, list)):
        return not value
    return False


def _refuse_to_blank(metric: models.Metric, proposed: dict) -> dict:
    """Put back any field the model returned empty that the metric actually has.

    **An improvement can change a field but cannot clear one**, because a metric
    update cannot: ``crud/metric.py`` drops ``None`` from an update so a null
    never overwrites stored data. Left alone, a proposal to blank a field would
    show as "—" in the dialog, the apply would report success, and the old value
    would still be there afterwards -- the gap between what was approved and what
    was saved that ADR-0006 exists to close.

    So the blank is dropped here, where it can be logged, rather than in the
    storage layer where it cannot. Changing a threshold is untouched by this;
    only emptying one is.
    """
    for field in IMPROVABLE_FIELDS:
        if not _blank(proposed.get(field)):
            continue
        current = _unwrap(getattr(metric, field, None))
        if _blank(current):
            continue
        logger.warning(
            "Improvement for metric %s left %s empty; keeping %r, which an update could "
            "not have cleared anyway",
            metric.id,
            field,
            current,
        )
        proposed[field] = current
    return proposed


def _changed_fields(existing: dict, proposed: dict) -> List[str]:
    """Which proposed fields differ from the metric's current ones.

    A set, not a running order: which of these a reviewer reads first is the
    interface's decision, and the dialog already makes it.
    """
    return [
        field
        for field in IMPROVABLE_FIELDS
        if _comparable(proposed.get(field)) != _comparable(existing.get(field))
    ]


def _comparable(value: Any) -> Any:
    """The form two values are compared in. Blank and absent are one thing.

    Deliberately stricter than ``fingerprint._normalize``, which folds category
    order and casing away because neither moves a verdict. Here they are a real
    difference: a reviewer being shown a rewrite has to see that the model
    recased a category, even though the metric would judge exactly the same.
    """
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        return [str(item).strip() for item in value] or None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    return value


def improve_from_reviews(
    db: Session, metric: models.Metric, organization_id: str, user: models.User
) -> MetricTuningImprovement:
    """Propose a rewrite of ``metric`` from the rejections that stand against it.

    Writes nothing, here or anywhere downstream. Raises ``NoStandingRejections``
    when there is nothing to read, and ``ImprovementUnavailable`` when the model
    could not answer.
    """
    rejections = standing_rejections(db, metric, organization_id)
    if not rejections:
        raise NoStandingRejections(
            "This metric has no rejected cases to learn from. Reject a case with a comment "
            "saying what the metric got wrong, then improve it from that."
        )

    existing = _existing_fields(metric)
    prompt = _load_template().render(
        existing_metric=existing,
        rejections=[rejection.model_dump() for rejection in rejections],
    )

    proposed = _refuse_to_blank(
        metric, _preserve_fixed_fields(metric, _ask_model(db, user, prompt))
    )

    # Applying is an ordinary metric update, so what is proposed has to be one.
    # Checked here rather than left to fail on apply, and deliberately outside the
    # model-failure handling above: a field that will not fit ``MetricUpdate`` is
    # our schema or our template, not the caller's request, so the ``ValidationError``
    # escapes for the router to turn into a 500 with a traceback.
    MetricUpdate(**proposed)

    logger.info(
        "Proposed an improvement for metric %s from %s rejection(s)", metric.id, len(rejections)
    )
    return MetricTuningImprovement(
        # Re-validated, so the returned object is the schema rather than the dict
        # the preserved fields were patched into.
        improvement=ImprovedMetricFields.model_validate(proposed),
        changed=_changed_fields(existing, proposed),
        rejections_used=len(rejections),
    )
