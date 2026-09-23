"""Override writer for annotations on a TestResult.

Entity-level annotations set the row's status directly; metric and turn
annotations rewrite the matching entry in ``test_metrics`` / ``test_output`` and
the overall status is recalculated from all of them.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app import models
from rhesis.backend.app.constants import AnnotationTarget
from rhesis.backend.app.outcomes import (
    Execution,
    Verdict,
    classify_metrics,
    outcome_of,
    outcome_to_test_result_status_name,
)
from rhesis.backend.app.services.annotation_override.common import (
    annotation_passed,
    find_metric_key,
    is_passed_status,
    normalize_metric_name,
    parse_turn_number,
)

# Kept as module-level names because the override writers and their tests read
# them from here. The implementations moved to common.py when metric improvement
# started matching annotation names against the same blob.
_normalize_metric_name = normalize_metric_name
_find_metric_key = find_metric_key


def _apply_outcome(
    db_test_result: models.TestResult, execution: Execution, verdict: Optional[Verdict]
) -> None:
    from rhesis.backend.app.utils.crud_utils import get_or_create_status

    db = Session.object_session(db_test_result)
    if db is None:
        return
    status_name = outcome_to_test_result_status_name(outcome_of(execution, verdict))
    status = get_or_create_status(
        db, status_name, "TestResult", organization_id=str(db_test_result.organization_id)
    )
    db_test_result.status_id = status.id
    db_test_result.execution = execution.value
    db_test_result.verdict = verdict.value if verdict else None


def _set_pass_fail_status(db_test_result: models.TestResult, passed: bool) -> None:
    _apply_outcome(db_test_result, Execution.OK, Verdict.PASS if passed else Verdict.FAIL)


def _no_metrics_applied(db_test_result: models.TestResult) -> bool:
    test_metrics = db_test_result.test_metrics
    return isinstance(test_metrics, dict) and bool(test_metrics.get("no_metrics_applied"))


def _has_evaluable_content(db_test_result: models.TestResult) -> bool:
    metrics = (db_test_result.test_metrics or {}).get("metrics")
    has_metrics = isinstance(metrics, dict) and bool(metrics)
    test_output = db_test_result.test_output
    has_goal_eval = isinstance(test_output, dict) and bool(test_output.get("goal_evaluation"))
    # No metric judged it, but the endpoint answered: a reviewer can.
    return has_metrics or has_goal_eval or _no_metrics_applied(db_test_result)


def apply_override(
    db_test_result: models.TestResult,
    annotation: models.Annotation,
    status_details: Dict[str, Any],
) -> None:
    passed = is_passed_status(status_details.get("name", ""))
    now = datetime.now(timezone.utc).isoformat()
    annotation_id = str(annotation.id)
    user_id = str(annotation.user_id)

    target_type = annotation.target_type
    target_reference = annotation.target_reference

    if target_type == AnnotationTarget.METRIC and target_reference:
        _apply_metric_override(
            db_test_result, target_reference, passed, annotation_id, user_id, now
        )
        recalculate_overall_status(db_test_result)
    elif target_type == AnnotationTarget.TURN and target_reference:
        _apply_turn_override(db_test_result, target_reference, passed, annotation_id, user_id, now)
        recalculate_overall_status(db_test_result)
    elif target_type == AnnotationTarget.TEST_RESULT:
        if _has_evaluable_content(db_test_result):
            _set_pass_fail_status(db_test_result, passed)
        else:
            _apply_outcome(db_test_result, Execution.ERROR, None)


def _apply_metric_override(
    db_test_result: models.TestResult,
    metric_name: str,
    passed: bool,
    annotation_id: str,
    user_id: str,
    now: str,
) -> None:
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

    if passed == original_val:
        metric["is_successful"] = original_val
        metric.pop("override", None)
    else:
        metric["is_successful"] = passed
        override_data = {
            "original_value": original_val,
            "annotation_id": annotation_id,
            "overridden_by": user_id,
            "overridden_at": now,
        }
        stashed_error = metric.pop("error", None)
        if stashed_error is not None:
            override_data["original_error"] = stashed_error
        metric["override"] = override_data

    flag_modified(db_test_result, "test_metrics")


def _apply_turn_override(
    db_test_result: models.TestResult,
    reference: str,
    passed: bool,
    annotation_id: str,
    user_id: str,
    now: str,
) -> None:
    turn_num = parse_turn_number(reference)
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

            if passed == original_val:
                turn["success"] = original_val
                turn.pop("override", None)
            else:
                turn["success"] = passed
                turn["override"] = {
                    "original_value": original_val,
                    "annotation_id": annotation_id,
                    "overridden_by": user_id,
                    "overridden_at": now,
                }
            break

    flag_modified(db_test_result, "test_output")


def revert_override(
    db: Session,
    db_test_result: models.TestResult,
    target_type: str,
    target_reference: Optional[str],
    deleted_annotation_id: str,
    replacement: Optional[models.Annotation],
) -> None:
    if target_type == AnnotationTarget.TEST_RESULT:
        if replacement:
            _set_pass_fail_status(db_test_result, annotation_passed(db, replacement))
        else:
            recalculate_overall_status(db_test_result)
        return

    if not target_reference:
        return

    args = (db, db_test_result, target_reference, deleted_annotation_id, replacement)
    if target_type == AnnotationTarget.METRIC:
        _revert_metric_override(*args)
    elif target_type == AnnotationTarget.TURN:
        _revert_turn_override(*args)

    recalculate_overall_status(db_test_result)


def _revert_metric_override(
    db: Session,
    db_test_result: models.TestResult,
    metric_name: str,
    deleted_annotation_id: str,
    replacement: Optional[models.Annotation],
) -> None:
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
    if not override or override.get("annotation_id") != deleted_annotation_id:
        return

    original_val = override["original_value"]
    original_error = override.get("original_error")

    if replacement:
        passed = annotation_passed(db, replacement)
        if passed == original_val:
            metric["is_successful"] = original_val
            metric.pop("override", None)
            if original_error is not None:
                metric["error"] = original_error
        else:
            now = datetime.now(timezone.utc).isoformat()
            metric["is_successful"] = passed
            new_override = {
                "original_value": original_val,
                "annotation_id": str(replacement.id),
                "overridden_by": str(replacement.user_id),
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
    db: Session,
    db_test_result: models.TestResult,
    reference: str,
    deleted_annotation_id: str,
    replacement: Optional[models.Annotation],
) -> None:
    turn_num = parse_turn_number(reference)
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
        if not override or override.get("annotation_id") != deleted_annotation_id:
            break

        original_val = override["original_value"]

        if replacement:
            passed = annotation_passed(db, replacement)
            if passed == original_val:
                turn["success"] = original_val
                turn.pop("override", None)
            else:
                now = datetime.now(timezone.utc).isoformat()
                turn["success"] = passed
                turn["override"] = {
                    "original_value": original_val,
                    "annotation_id": str(replacement.id),
                    "overridden_by": str(replacement.user_id),
                    "overridden_at": now,
                }
        else:
            turn["success"] = original_val
            turn.pop("override", None)
        break

    flag_modified(db_test_result, "test_output")


def _turns_all_passed(test_output) -> Optional[bool]:
    if not isinstance(test_output, dict):
        return None
    summary = test_output.get("conversation_summary")
    if not isinstance(summary, list) or not summary:
        return None
    return all(turn.get("success", True) for turn in summary if isinstance(turn, dict))


def recalculate_overall_status(db_test_result: models.TestResult) -> None:
    test_metrics = db_test_result.test_metrics
    metrics = (
        test_metrics.get("metrics")
        if isinstance(test_metrics, dict) and isinstance(test_metrics.get("metrics"), dict)
        else {}
    )
    turns_passed = _turns_all_passed(db_test_result.test_output)

    if not metrics:
        if turns_passed is None:
            execution, verdict = classify_metrics(
                metrics, no_metrics_applied=_no_metrics_applied(db_test_result)
            )
            _apply_outcome(db_test_result, execution, verdict)
            return
        execution, verdict = Execution.OK, (Verdict.PASS if turns_passed else Verdict.FAIL)
    else:
        execution, verdict = classify_metrics(metrics)
        if execution == Execution.OK and turns_passed is False:
            verdict = Verdict.FAIL

    _apply_outcome(db_test_result, execution, verdict)
