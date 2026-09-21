"""Rewriting a metric from the rejections its reviewers wrote.

This is what the comments were collected for. A reviewer rejects a verdict and
says what is wrong with it; this reads those comments back and asks the
generation model to rewrite the metric so it would judge those cases the way the
reviewer says.

**It never writes.** The proposed fields go back to the caller, the reviewer sees
them beside the current ones, and applying is an ordinary metric update sent
afterwards. An in-place LLM rewrite would silently replace the evaluation prompt
the annotations were made against, with no diff and no undo -- and applying by
calling the model a second time would save a different rewrite than the one on
screen. See domain.local/adr/0006.

**The prompt and the schema live here, not in the SDK.** ``MetricSynthesizer`` is
deliberately not used: this prompt is about annotations, which the SDK has no
reason to know about. What is borrowed is the model client, because it is the only
path to an LLM in this codebase and it is where provider auth, retries and usage
metering live. The consequence is that the naming, field-depth and score-type
rules now exist in two templates -- ``improve_from_annotations.jinja`` here and
the SDK's ``improve_metric.jinja`` -- and nothing keeps them in step. That is
known.

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
from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models
from rhesis.backend.app.constants import AnnotationTarget, EntityType
from rhesis.backend.app.crud import metric_tuning as crud_metric_tuning
from rhesis.backend.app.crud.annotation import get_annotations_for_tests
from rhesis.backend.app.schemas.metric import MetricUpdate
from rhesis.backend.app.schemas.metric_tuning import (
    ImprovedMetricFields,
    MetricTuningImprovement,
    TuningDecision,
)
from rhesis.backend.app.schemas.metric_tuning_metadata import parse_metric_tuning_case_metadata
from rhesis.backend.app.services.annotation_override.common import (
    annotation_passed,
    find_metric_key,
    normalize_metric_name,
)
from rhesis.backend.app.services.metric_tuning.judgement import decision_of
from rhesis.backend.app.services.metric_tuning.outcome import current_verdict, standing_annotation
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
# invalidates every annotation the metric has, and the ``categories`` list is what a
# stored categorical verdict is named from -- neither is a thing this button
# moves. See ADR-0006.
PRESERVED_FIELDS = ("score_type", "categories")


# How many run-sourced rejections reach the prompt. Tuning cases are deliberately
# uncapped -- see the module docstring -- but they are a set someone curated one
# case at a time, while this is every annotation anyone left on any run of this
# metric, which is unbounded. The cap is reported back rather than applied
# quietly: the count says how many were found and how many were sent, so a
# dropped rejection is a number on screen rather than a silent omission.
RUN_REJECTION_LIMIT = 20


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
    path = os.path.join(os.path.dirname(__file__), "improve_from_annotations.jinja")
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

    Two filters, both of them the point. A case whose standing judgement is an
    accept is left out -- only rejections are sent. And the *standing* one is the
    one read, not the whole history: a rejection a material change invalidated
    objects to a verdict the metric no longer gives, so feeding it back would ask
    for a rewrite nobody wants any more.

    Whoever wrote the rejection does not matter. A metric is tuned by everyone
    who annotated it, not only by whoever pressed the button.
    """
    test_set = get_tuning_test_set(db, metric.id, organization_id)
    if not test_set:
        return []

    cases = crud_metric_tuning.get_tuning_cases(db, test_set.id, organization_id)
    case_annotations = get_annotations_for_tests(db, [case.id for case in cases])

    rejections = []
    for db_test in cases:
        metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
        annotation = standing_annotation(metric, metadata, case_annotations.get(db_test.id, ()))
        if annotation is None or decision_of(annotation) != TuningDecision.REJECTED:
            continue
        comment = (annotation.comments or "").strip()
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
                # Both from the latest run, not the verdict the annotation
                # recorded: a judgement survives drift that did not cross the
                # threshold, so the stored verdict and the current reasoning can
                # be one run apart. Showing the model a number beside an
                # explanation of a different number is worse than either alone.
                verdict=current_verdict(metadata),
                reasoning=_clip(result.reasoning if result else None),
                comment=_clip(comment),
            )
        )
    return rejections


def _output_text(test_output: Any) -> str:
    """What the system under test answered, out of the stored output blob."""
    if isinstance(test_output, dict):
        for key in ("response", "output"):
            value = test_output.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return ""
    return test_output if isinstance(test_output, str) else ""


def _overriding_metric_entry(
    test_result: models.TestResult, metric_name: str, annotation_id: str
) -> Optional[dict]:
    """The metric's entry on this result, if this annotation is overriding it.

    The override marker is the disagreement: ``apply_override`` writes one only
    when the human verdict differs from the automated value, and removes it when
    they agree. So its presence means the person contradicted the metric, and its
    ``annotation_id`` means this annotation is the one currently doing so rather
    than a superseded one. Re-deriving either from the verdicts would be a second
    implementation of a rule that already has one.
    """
    test_metrics = test_result.test_metrics
    if not isinstance(test_metrics, dict):
        return None
    metrics = test_metrics.get("metrics")
    if not isinstance(metrics, dict):
        return None
    key = find_metric_key(metrics, metric_name)
    if key is None:
        return None
    entry = metrics[key]
    if not isinstance(entry, dict):
        return None
    override = entry.get("override")
    if not isinstance(override, dict):
        return None
    if str(override.get("annotation_id")) != str(annotation_id):
        return None
    return entry


def _annotations_naming_metric(db: Session, metric: models.Metric) -> List[models.Annotation]:
    """Unresolved, commented metric annotations on test results naming this metric.

    The name match is done in Python rather than SQL because an annotation names
    the metric as a person sees it while the result's blob is keyed by whatever
    the run wrote, and the two differ by punctuation and case often enough that
    an exact SQL match loses real annotations.
    """
    candidates = (
        db.query(models.Annotation)
        .filter(
            models.Annotation.entity_type == EntityType.TEST_RESULT.value,
            models.Annotation.target_type == AnnotationTarget.METRIC.value,
            models.Annotation.resolved.is_(False),
            models.Annotation.comments.isnot(None),
        )
        .order_by(models.Annotation.updated_at.desc())
        .all()
    )
    normalized = normalize_metric_name(metric.name or "")
    return [
        annotation
        for annotation in candidates
        if normalize_metric_name(annotation.target_reference or "") == normalized
    ]


def count_run_disagreements(db: Session, metric: models.Metric) -> int:
    """How many test results carry a standing human verdict against this metric.

    The same rule ``run_rejections`` applies, counted without building the cases:
    two narrow queries, the second reading only the ids and the metrics blob. The
    agreement endpoint is polled, so this stays next to the two queries that
    function already makes rather than loading prompts and outputs nobody shows.

    The override marker cannot be tested in SQL -- the metric's key inside the
    blob is matched case- and punctuation-insensitively, so there is no fixed
    path to query -- which is why this is a count over rows rather than a
    ``COUNT(*)``.
    """
    annotations = _annotations_naming_metric(db, metric)
    if not annotations:
        return 0

    blobs = dict(
        db.query(models.TestResult.id, models.TestResult.test_metrics)
        .filter(models.TestResult.id.in_([a.entity_id for a in annotations]))
        .all()
    )
    metric_name = metric.name or ""
    return sum(
        1
        for annotation in annotations
        if _overrides_metric(blobs.get(annotation.entity_id), metric_name, annotation.id)
    )


def _overrides_metric(test_metrics: Any, metric_name: str, annotation_id: Any) -> bool:
    """Whether this annotation is the one currently overriding the metric."""
    if not isinstance(test_metrics, dict):
        return False
    metrics = test_metrics.get("metrics")
    if not isinstance(metrics, dict):
        return False
    key = find_metric_key(metrics, metric_name)
    if key is None or not isinstance(metrics[key], dict):
        return False
    override = metrics[key].get("override")
    return isinstance(override, dict) and str(override.get("annotation_id")) == str(annotation_id)


def run_rejections(
    db: Session, metric: models.Metric, organization_id: str
) -> tuple[List[Rejection], int]:
    """Rejections read off real test results rather than tuning cases.

    A person who overrules this metric on a run has said the same thing a tuning
    rejection says -- that the metric judged a case wrongly -- about a case that
    came out of the system under test rather than one curated for tuning. The
    Architect is already told a human verdict outranks a metric score; this is
    the path for acting on that.

    Only annotations still overriding the metric count. An annotation that agrees
    with it leaves no override marker, and one a later judgement replaced no
    longer owns the marker, so both fall out without a second rule for either.

    Unresolved only: resolving one is how a person says the disagreement has been
    handled, and asking for a rewrite from a settled objection would undo it.

    Returns the rejections to send and how many were found, which differ when the
    cap bites.
    """
    metric_name = metric.name or ""
    named_this_metric = _annotations_naming_metric(db, metric)
    if not named_this_metric:
        return [], 0

    results = {
        str(result.id): result
        for result in db.query(models.TestResult)
        .options(
            joinedload(models.TestResult.test).joinedload(models.Test.prompt),
        )
        .filter(
            models.TestResult.id.in_([annotation.entity_id for annotation in named_this_metric])
        )
        .all()
    }

    found: List[Rejection] = []
    for annotation in named_this_metric:
        result = results.get(str(annotation.entity_id))
        if result is None:
            continue
        entry = _overriding_metric_entry(result, metric_name, annotation.id)
        if entry is None:
            continue
        comment = (annotation.comments or "").strip()
        if not comment:
            continue

        prompt = result.test.prompt if result.test else None
        override = entry["override"]
        found.append(
            Rejection(
                input=_clip(prompt.content if prompt else None) or "",
                output=_clip(_output_text(result.test_output)) or "",
                reference_answer=_clip(prompt.expected_response if prompt else None),
                # What the metric said before the person overruled it. The live
                # is_successful now holds their verdict, so reading that would
                # show the model its own output as the thing to fix.
                verdict=_verdict_text(override.get("original_value")),
                reasoning=_clip(entry.get("reason")),
                comment=_clip(comment),
            )
        )

    return found[:RUN_REJECTION_LIMIT], len(found)


def explorer_rejections(
    db: Session, metric: models.Metric, organization_id: str
) -> tuple[List[Rejection], int]:
    """Rejections read off Explorer tests someone labelled by hand.

    An Explorer label records an opinion without overriding anything, so unlike a
    test result there is no override marker to read and the verdicts are compared
    directly: the person's Pass/Fail against what this metric said about that
    test in ``test_metadata.metrics``.

    Attribution is per metric even though the label is on the test as a whole. If
    the person failed a test that this metric passed, this metric was wrong about
    it, whatever the others said.

    Tuning judgements do not come through here: those are filed against the
    metric by id with a ``metric`` target, while a label is an entity-level
    ``test`` one.
    """
    labels = (
        db.query(models.Annotation)
        # The verdict is read off the status, so it is loaded with the row.
        .options(joinedload(models.Annotation.status))
        .filter(
            models.Annotation.entity_type == EntityType.TEST.value,
            models.Annotation.target_type == AnnotationTarget.TEST.value,
            models.Annotation.resolved.is_(False),
            models.Annotation.comments.isnot(None),
        )
        .order_by(models.Annotation.updated_at.desc())
        .all()
    )
    if not labels:
        return [], 0

    tests = {
        str(test.id): test
        for test in db.query(models.Test)
        .options(joinedload(models.Test.prompt))
        .filter(models.Test.id.in_([label.entity_id for label in labels]))
        .all()
    }

    metric_name = metric.name or ""
    found: List[Rejection] = []
    for label in labels:
        test = tests.get(str(label.entity_id))
        if test is None:
            continue
        metadata = test.test_metadata if isinstance(test.test_metadata, dict) else {}
        metrics = metadata.get("metrics")
        if not isinstance(metrics, dict):
            continue
        key = find_metric_key(metrics, metric_name)
        if key is None:
            continue
        entry = metrics[key]
        if not isinstance(entry, dict) or "is_successful" not in entry:
            continue

        automated_pass = bool(entry.get("is_successful"))
        if annotation_passed(db, label) == automated_pass:
            continue

        comment = (label.comments or "").strip()
        if not comment:
            continue

        found.append(
            Rejection(
                input=_clip(test.prompt.content if test.prompt else None) or "",
                output=_clip(metadata.get("output") if isinstance(metadata, dict) else None) or "",
                reference_answer=_clip(test.prompt.expected_response if test.prompt else None),
                verdict=_verdict_text(automated_pass),
                reasoning=_clip(entry.get("reason")),
                comment=_clip(comment),
            )
        )

    return found[:RUN_REJECTION_LIMIT], len(found)


def _verdict_text(original_value: Any) -> Optional[str]:
    """The metric's own verdict, as the prompt reads it."""
    if original_value is True:
        return "passed"
    if original_value is False:
        return "failed"
    return None


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


def improve_from_annotations(
    db: Session,
    metric: models.Metric,
    organization_id: str,
    user: models.User,
    *,
    include_run_annotations: bool = True,
) -> MetricTuningImprovement:
    """Propose a rewrite of ``metric`` from the rejections that stand against it.

    Reads two sources. Tuning cases are what someone curated for judging this
    metric; run annotations are people overruling it on real results. Both say
    the metric judged a case wrongly, so both are sent, marked by provenance so
    the model knows which is which. ``include_run_annotations=False`` restricts
    it to tuning cases, for a caller who wants only the curated set.

    Writes nothing, here or anywhere downstream. Raises ``NoStandingRejections``
    when there is nothing to read, and ``ImprovementUnavailable`` when the model
    could not answer.
    """
    rejections = standing_rejections(db, metric, organization_id)
    from_runs: List[Rejection] = []
    runs_found = 0
    from_explorer: List[Rejection] = []
    explorer_found = 0
    if include_run_annotations:
        from_runs, runs_found = run_rejections(db, metric, organization_id)
        from_explorer, explorer_found = explorer_rejections(db, metric, organization_id)

    if not rejections and not from_runs and not from_explorer:
        raise NoStandingRejections(
            "This metric has no rejected cases to learn from. Reject a tuning case with a "
            "comment saying what the metric got wrong, or overrule it on a test result, "
            "then improve it from that."
        )

    existing = _existing_fields(metric)
    prompt = _load_template().render(
        existing_metric=existing,
        rejections=[rejection.model_dump() for rejection in rejections],
        run_rejections=[rejection.model_dump() for rejection in from_runs],
        run_rejections_omitted=runs_found - len(from_runs),
        explorer_rejections=[rejection.model_dump() for rejection in from_explorer],
        explorer_rejections_omitted=explorer_found - len(from_explorer),
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
        "Proposed an improvement for metric %s from %s tuning, %s run and %s explorer"
        " rejection(s) (%s and %s found)",
        metric.id,
        len(rejections),
        len(from_runs),
        len(from_explorer),
        runs_found,
        explorer_found,
    )
    return MetricTuningImprovement(
        # Re-validated, so the returned object is the schema rather than the dict
        # the preserved fields were patched into.
        improvement=ImprovedMetricFields.model_validate(proposed),
        changed=_changed_fields(existing, proposed),
        rejections_used=len(rejections) + len(from_runs) + len(from_explorer),
        tuning_rejections_used=len(rejections),
        run_rejections_used=len(from_runs),
        run_rejections_found=runs_found,
        explorer_rejections_used=len(from_explorer),
        explorer_rejections_found=explorer_found,
    )
