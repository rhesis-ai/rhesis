"""
Service layer for review override logic.

Handles applying, reverting, and recalculating overrides on test_metrics
(metric-level) and test_output (turn-level) whenever a human review is
created, updated, or deleted.

All functions operate on already-loaded ORM instances and obtain the DB
session via Session.object_session() rather than accepting it as a parameter.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app import models
from rhesis.backend.app.constants import (
    REVIEW_TARGET_METRIC,
    REVIEW_TARGET_TEST_RESULT,
    REVIEW_TARGET_TURN,
    OverallTestResult,
    categorize_test_result_status,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.outcomes import (
    Execution,
    Verdict,
    classify_metrics,
    outcome_of,
    outcome_to_test_result_status_name,
)


def _normalize_metric_name(name: str) -> str:
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", name.lower()))


def _find_metric_key(metrics: Dict[str, Any], metric_name: str) -> Optional[str]:
    """Resolve a metric reference to its stored key (exact or slug-normalized)."""
    if metric_name in metrics:
        return metric_name
    normalized_target = _normalize_metric_name(metric_name)
    for key in metrics:
        if isinstance(key, str) and _normalize_metric_name(key) == normalized_target:
            return key
    return None


def is_passed_status(status_name: str) -> bool:
    """Determine if a status name represents a passed/successful outcome."""
    return categorize_test_result_status(status_name) == OverallTestResult.PASSED


def _parse_turn_number(reference: str) -> Optional[int]:
    """Extract the turn number from a reference like 'Turn 2'."""
    digits = re.sub(r"\D", "", reference)
    return int(digits) if digits else None


def _apply_outcome(
    db_test_result: models.TestResult, execution: Execution, verdict: Optional[Verdict]
) -> None:
    """Write execution/verdict (the source of truth -- see app/outcomes.py)
    and status_id (the legacy display artefact) together, from one
    outcome, so a review can never update one without the other.
    """
    from rhesis.backend.app.utils.crud_utils import get_or_create_status

    db = Session.object_session(db_test_result)
    if db is None:
        return
    status_name = outcome_to_test_result_status_name(outcome_of(execution, verdict))
    status = get_or_create_status(
        db,
        status_name,
        "TestResult",
        organization_id=str(db_test_result.organization_id),
    )
    db_test_result.status_id = status.id
    db_test_result.execution = execution.value
    db_test_result.verdict = verdict.value if verdict else None


def _set_pass_fail_status(
    db_test_result: models.TestResult,
    passed: bool,
) -> None:
    """Apply a plain Pass/Fail outcome -- what a review targeting the whole
    test result (rather than a specific metric or turn) can express, since
    that review flow only ever offers a pass/fail choice.
    """
    _apply_outcome(db_test_result, Execution.OK, Verdict.PASS if passed else Verdict.FAIL)


def _has_evaluable_content(db_test_result: models.TestResult) -> bool:
    """Whether this result has anything a verdict could be about.

    A test-result-level review can correct a verdict, but it can't
    fabricate one out of nothing: a result with no metrics and no goal
    evaluation never produced evaluable output, so it stays Error
    regardless of what a reviewer picks. Mirrors the frontend's guard in
    getEffectiveTestResultStatus (test-result-status.ts) -- moving here so
    the persisted outcome agrees with what the review UI has always shown.
    """
    metrics = (db_test_result.test_metrics or {}).get("metrics")
    has_metrics = isinstance(metrics, dict) and bool(metrics)
    test_output = db_test_result.test_output
    has_goal_eval = isinstance(test_output, dict) and bool(test_output.get("goal_evaluation"))
    return has_metrics or has_goal_eval


def apply_review_override(
    db_test_result: models.TestResult,
    target_type: str,
    target_reference: Optional[str],
    status_details: Dict[str, Any],
    current_user: User,
    review_id: str,
) -> None:
    """
    Apply a review override to the source data (test_metrics or test_output).

    Mutates is_successful / success to match the review verdict and adds an
    ``override`` marker preserving the original automated value.
    Recalculates the overall Pass/Fail status for metric- and turn-level overrides.
    """
    review_passed = is_passed_status(status_details.get("name", ""))
    now = datetime.now(timezone.utc).isoformat()

    if target_type == REVIEW_TARGET_METRIC and target_reference:
        _apply_metric_override(
            db_test_result,
            target_reference,
            review_passed,
            review_id,
            current_user,
            now,
        )
        recalculate_overall_status(db_test_result)
    elif target_type == REVIEW_TARGET_TURN and target_reference:
        _apply_turn_override(
            db_test_result,
            target_reference,
            review_passed,
            review_id,
            current_user,
            now,
        )
        recalculate_overall_status(db_test_result)
    elif target_type == REVIEW_TARGET_TEST_RESULT:
        if _has_evaluable_content(db_test_result):
            _set_pass_fail_status(db_test_result, review_passed)
        else:
            _apply_outcome(db_test_result, Execution.ERROR, None)


def _apply_metric_override(
    db_test_result: models.TestResult,
    metric_name: str,
    review_passed: bool,
    review_id: str,
    current_user: User,
    now: str,
) -> None:
    """Override a single metric's is_successful value."""
    test_metrics = db_test_result.test_metrics
    if not test_metrics or not isinstance(test_metrics, dict):
        return
    metrics = test_metrics.get("metrics")
    if not metrics or not isinstance(metrics, dict):
        return
    metric_key = _find_metric_key(metrics, metric_name)
    if metric_key is None:
        return
    metric = metrics[metric_key]

    current_val = metric.get("is_successful", False)
    existing_override = metric.get("override")
    original_val = existing_override["original_value"] if existing_override else current_val

    if review_passed == original_val:
        metric["is_successful"] = original_val
        metric.pop("override", None)
    else:
        metric["is_successful"] = review_passed
        override_data = {
            "original_value": original_val,
            "review_id": review_id,
            "overridden_by": str(current_user.id),
            "overridden_at": now,
        }
        # A metric that crashed while evaluating (carries an `error` key --
        # see MetricResultBuilder.error()/.timeout()) must stop reading as
        # Execution.ERROR once a human actively overrides it to pass/fail:
        # that verdict is real information now, not a gap the platform
        # couldn't fill. Without this a reviewed result could never leave
        # Error (inventory.md bug 4) -- classify_metrics would keep seeing
        # the `error` key and re-derive ERROR regardless of is_successful.
        # Stashed for revert_override to restore.
        stashed_error = metric.pop("error", None)
        if stashed_error is not None:
            override_data["original_error"] = stashed_error
        metric["override"] = override_data

    flag_modified(db_test_result, "test_metrics")


def _apply_turn_override(
    db_test_result: models.TestResult,
    reference: str,
    review_passed: bool,
    review_id: str,
    current_user: User,
    now: str,
) -> None:
    """Override a single turn's success value."""
    turn_num = _parse_turn_number(reference)
    if turn_num is None:
        return
    test_output = db_test_result.test_output
    if not test_output or not isinstance(test_output, dict):
        return
    summary = test_output.get("conversation_summary")
    if not summary or not isinstance(summary, list):
        return

    for turn in summary:
        if turn.get("turn") == turn_num:
            current_val = turn.get("success", False)
            existing_override = turn.get("override")
            original_val = existing_override["original_value"] if existing_override else current_val

            if review_passed == original_val:
                turn["success"] = original_val
                turn.pop("override", None)
            else:
                turn["success"] = review_passed
                turn["override"] = {
                    "original_value": original_val,
                    "review_id": review_id,
                    "overridden_by": str(current_user.id),
                    "overridden_at": now,
                }
            break

    flag_modified(db_test_result, "test_output")


def revert_override(
    db_test_result: models.TestResult,
    target_type: str,
    target_reference: Optional[str],
    deleted_review_id: str,
    remaining_reviews: List[Dict[str, Any]],
) -> None:
    """
    Revert an override when a review is deleted.

    If another review exists for the same target, that replacement is applied
    instead. Otherwise the original automated value is restored.
    """
    if target_type == REVIEW_TARGET_TEST_RESULT:
        same_target = [
            r
            for r in remaining_reviews
            if r.get("target", {}).get("type") == REVIEW_TARGET_TEST_RESULT
        ]
        if same_target:
            latest = max(
                same_target,
                key=lambda r: r.get("updated_at") or r.get("created_at") or "",
            )
            review_passed = is_passed_status(latest.get("status", {}).get("name", ""))
            _set_pass_fail_status(db_test_result, review_passed)
        else:
            recalculate_overall_status(db_test_result)
        return

    if not target_reference:
        return

    same_target = [
        r
        for r in remaining_reviews
        if r.get("target", {}).get("type") == target_type
        and r.get("target", {}).get("reference") == target_reference
    ]
    replacement = (
        max(same_target, key=lambda r: r.get("updated_at") or r.get("created_at") or "")
        if same_target
        else None
    )

    if target_type == REVIEW_TARGET_METRIC:
        _revert_metric_override(db_test_result, target_reference, deleted_review_id, replacement)
    elif target_type == REVIEW_TARGET_TURN:
        _revert_turn_override(db_test_result, target_reference, deleted_review_id, replacement)

    recalculate_overall_status(db_test_result)


def _revert_metric_override(
    db_test_result: models.TestResult,
    metric_name: str,
    deleted_review_id: str,
    replacement_review: Optional[Dict[str, Any]],
) -> None:
    """Revert a metric override, optionally re-applying a replacement review."""
    test_metrics = db_test_result.test_metrics
    if not test_metrics or not isinstance(test_metrics, dict):
        return
    metrics = test_metrics.get("metrics")
    if not metrics or not isinstance(metrics, dict):
        return
    metric_key = _find_metric_key(metrics, metric_name)
    if metric_key is None:
        return
    metric = metrics[metric_key]

    override = metric.get("override")
    if not override or override.get("review_id") != deleted_review_id:
        return

    original_val = override["original_value"]
    # Symmetric with _apply_metric_override's stash: a metric that crashed
    # before any review had its `error` key moved into the override so
    # classify_metrics would stop seeing it. Reverting (no review left in
    # effect, or the replacement review agrees with the original value)
    # must put it back, or the metric quietly stays "resolved" forever
    # after its one review is deleted.
    original_error = override.get("original_error")

    if replacement_review:
        review_passed = is_passed_status(replacement_review.get("status", {}).get("name", ""))
        if review_passed == original_val:
            metric["is_successful"] = original_val
            metric.pop("override", None)
            if original_error is not None:
                metric["error"] = original_error
        else:
            now = datetime.now(timezone.utc).isoformat()
            metric["is_successful"] = review_passed
            new_override = {
                "original_value": original_val,
                "review_id": replacement_review["review_id"],
                "overridden_by": replacement_review.get("user", {}).get("user_id", ""),
                "overridden_at": now,
            }
            if original_error is not None:
                new_override["original_error"] = original_error
            metric["override"] = new_override
    else:
        metric["is_successful"] = original_val
        metric.pop("override", None)
        if original_error is not None:
            metric["error"] = original_error

    flag_modified(db_test_result, "test_metrics")


def _revert_turn_override(
    db_test_result: models.TestResult,
    reference: str,
    deleted_review_id: str,
    replacement_review: Optional[Dict[str, Any]],
) -> None:
    """Revert a turn override, optionally re-applying a replacement review."""
    turn_num = _parse_turn_number(reference)
    if turn_num is None:
        return
    test_output = db_test_result.test_output
    if not test_output or not isinstance(test_output, dict):
        return
    summary = test_output.get("conversation_summary")
    if not summary or not isinstance(summary, list):
        return

    for turn in summary:
        if turn.get("turn") != turn_num:
            continue
        override = turn.get("override")
        if not override or override.get("review_id") != deleted_review_id:
            break

        original_val = override["original_value"]

        if replacement_review:
            review_passed = is_passed_status(replacement_review.get("status", {}).get("name", ""))
            if review_passed == original_val:
                turn["success"] = original_val
                turn.pop("override", None)
            else:
                now = datetime.now(timezone.utc).isoformat()
                turn["success"] = review_passed
                turn["override"] = {
                    "original_value": original_val,
                    "review_id": replacement_review["review_id"],
                    "overridden_by": replacement_review.get("user", {}).get("user_id", ""),
                    "overridden_at": now,
                }
        else:
            turn["success"] = original_val
            turn.pop("override", None)
        break

    flag_modified(db_test_result, "test_output")


def _turns_all_passed(test_output: Any) -> Optional[bool]:
    """Whether every turn in test_output.conversation_summary passed.

    None when there is nothing to fold in (no turns, or not a multi-turn
    result) -- distinct from False, which means an active turn failure.
    A turn with no recorded verdict defaults to passed, matching
    trace_review_override.py's identical fold-in rule: a turn is only
    ever a *reason to fail*, never a reason to invent a pass the metrics
    didn't already produce.
    """
    if not isinstance(test_output, dict):
        return None
    summary = test_output.get("conversation_summary")
    if not isinstance(summary, list) or not summary:
        return None
    return all(turn.get("success", True) for turn in summary if isinstance(turn, dict))


def recalculate_overall_status(
    db_test_result: models.TestResult,
) -> None:
    """Recalculate the overall test result outcome after a human review
    changed a metric or a turn.

    Folds in turn-level overrides, not just metric-level ones: previously
    this read only test_metrics, so overriding a turn (via
    _apply_turn_override) wrote the flip to test_output and then this
    function silently ignored it when deciding the test's overall status
    (inventory.md bug 3) -- trace_review_override.py's twin of this
    function already ANDs in ``turns_passed``; this now matches it.

    Writes execution/verdict (the source of truth -- app/outcomes.py) and
    status_id together via _apply_outcome, so a review can produce any of
    Pass/Fail/Error/Inconclusive rather than being limited to Pass/Fail --
    previously an errored result could never become Error again once
    reviewed (bug 4); classify_metrics can still return ERROR post-review
    for a metric with no override at all (e.g. only *some* metrics were
    reviewed and another one is still crashed).
    """
    test_metrics = db_test_result.test_metrics
    metrics = (
        test_metrics.get("metrics")
        if isinstance(test_metrics, dict) and isinstance(test_metrics.get("metrics"), dict)
        else {}
    )
    turns_passed = _turns_all_passed(db_test_result.test_output)

    if not metrics:
        if turns_passed is None:
            # Nothing to recalculate from at all -- e.g. reverting the last
            # entity-level review on a metrics-less/turn-less result. Must
            # still write Error rather than no-op, or the row stays stuck
            # at whatever the just-deleted review set it to.
            _apply_outcome(db_test_result, Execution.ERROR, None)
            return
        # Turn-only multi-turn result (no discrete metrics dict): the
        # turns are the only verdict-shaped signal there is, so they
        # decide execution/verdict directly rather than falling through
        # to classify_metrics({}), which would report ERROR for a result
        # that in fact has a real, reviewed verdict.
        execution, verdict = Execution.OK, (Verdict.PASS if turns_passed else Verdict.FAIL)
    else:
        execution, verdict = classify_metrics(metrics)
        if execution == Execution.OK and turns_passed is False:
            verdict = Verdict.FAIL

    _apply_outcome(db_test_result, execution, verdict)
