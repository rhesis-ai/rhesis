"""Override writer for annotations on a Trace.

The trace equivalent of the test_result writer: its verdict lives in
``trace_metrics_status_id`` and its metrics are split into ``turn_metrics`` and
``conversation_metrics``, with turn verdicts kept in a ``turn_overrides`` map.
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
    is_passed_status,
    parse_turn_number,
)


def _apply_outcome(
    db_trace: models.Trace, execution: Execution, verdict: Optional[Verdict]
) -> None:
    from rhesis.backend.app.utils.crud_utils import get_or_create_status

    db = Session.object_session(db_trace)
    if db is None:
        return
    status_name = outcome_to_test_result_status_name(outcome_of(execution, verdict))
    status = get_or_create_status(
        db,
        status_name,
        "TestResult",
        organization_id=str(db_trace.organization_id),
    )
    db_trace.trace_metrics_status_id = status.id
    db_trace.execution = execution.value
    db_trace.verdict = verdict.value if verdict else None


def _set_pass_fail_status(db_trace: models.Trace, passed: bool) -> None:
    _apply_outcome(db_trace, Execution.OK, Verdict.PASS if passed else Verdict.FAIL)


def _get_all_trace_metric_values(trace_metrics: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for section in ("turn_metrics", "conversation_metrics"):
        section_data = trace_metrics.get(section, {})
        metrics = section_data.get("metrics", {})
        for name, m in metrics.items():
            if isinstance(m, dict):
                merged[f"{section}.{name}"] = m
    return merged


def apply_override(
    db_trace: models.Trace,
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
        _apply_metric_override(db_trace, target_reference, passed, annotation_id, user_id, now)
        recalculate_overall_status(db_trace)
    elif target_type == AnnotationTarget.TURN:
        _apply_turn_override(db_trace, target_reference, passed, annotation_id, user_id, now)
        recalculate_overall_status(db_trace)
    elif target_type == AnnotationTarget.TRACE:
        _set_pass_fail_status(db_trace, passed)


def _apply_metric_override(
    db_trace: models.Trace,
    metric_name: str,
    passed: bool,
    annotation_id: str,
    user_id: str,
    now: str,
) -> None:
    trace_metrics = db_trace.trace_metrics
    if not trace_metrics or not isinstance(trace_metrics, dict):
        return

    for section in ("turn_metrics", "conversation_metrics"):
        section_data = trace_metrics.get(section, {})
        metrics = section_data.get("metrics", {})
        metric = metrics.get(metric_name)
        if metric is None:
            continue

        current_val = metric.get("is_successful", False)
        existing_override = metric.get("override")
        original_val = existing_override["original_value"] if existing_override else current_val

        if passed == original_val:
            metric["is_successful"] = original_val
            metric.pop("override", None)
            original_error = (existing_override or {}).get("original_error")
            if original_error is not None:
                metric["error"] = original_error
        else:
            metric["is_successful"] = passed
            override_data = {
                "original_value": original_val,
                "annotation_id": annotation_id,
                "overridden_by": user_id,
                "overridden_at": now,
            }
            stashed_error = metric.pop("error", None)
            if stashed_error is None and existing_override:
                stashed_error = existing_override.get("original_error")
            if stashed_error is not None:
                override_data["original_error"] = stashed_error
            metric["override"] = override_data

    flag_modified(db_trace, "trace_metrics")


def _apply_turn_override(
    db_trace: models.Trace,
    target_reference: Optional[str],
    passed: bool,
    annotation_id: str,
    user_id: str,
    now: str,
) -> None:
    if not target_reference:
        return
    turn_num = parse_turn_number(target_reference)
    if turn_num is None:
        return

    trace_metrics = db_trace.trace_metrics
    if not trace_metrics or not isinstance(trace_metrics, dict):
        return

    turn_section = trace_metrics.get("turn_metrics", {})
    metrics = turn_section.get("metrics", {})
    turn_execution, turn_verdict = classify_metrics(metrics)
    automated_passed = turn_execution == Execution.OK and turn_verdict == Verdict.PASS

    if "turn_overrides" not in trace_metrics:
        trace_metrics["turn_overrides"] = {}

    turn_key = str(turn_num)
    existing = trace_metrics["turn_overrides"].get(turn_key, {})
    existing_override = existing.get("override")
    original_val = existing_override["original_value"] if existing_override else automated_passed

    if passed == original_val:
        trace_metrics["turn_overrides"].pop(turn_key, None)
        if not trace_metrics["turn_overrides"]:
            trace_metrics.pop("turn_overrides", None)
    else:
        trace_metrics["turn_overrides"][turn_key] = {
            "success": passed,
            "override": {
                "original_value": original_val,
                "annotation_id": annotation_id,
                "overridden_by": user_id,
                "overridden_at": now,
            },
        }

    flag_modified(db_trace, "trace_metrics")


def revert_override(
    db: Session,
    db_trace: models.Trace,
    target_type: str,
    target_reference: Optional[str],
    deleted_annotation_id: str,
    replacement: Optional[models.Annotation],
) -> None:
    if target_type == AnnotationTarget.TRACE:
        if replacement:
            passed = annotation_passed(db, replacement)
            _set_pass_fail_status(db_trace, passed)
        else:
            recalculate_overall_status(db_trace)
        return

    if target_type == AnnotationTarget.TURN:
        _revert_turn_override(db, db_trace, target_reference, deleted_annotation_id, replacement)
        recalculate_overall_status(db_trace)
        return

    if not target_reference:
        return

    if target_type == AnnotationTarget.METRIC:
        _revert_metric_override(db, db_trace, target_reference, deleted_annotation_id, replacement)

    recalculate_overall_status(db_trace)


def _revert_metric_override(
    db: Session,
    db_trace: models.Trace,
    metric_name: str,
    deleted_annotation_id: str,
    replacement: Optional[models.Annotation],
) -> None:
    trace_metrics = db_trace.trace_metrics
    if not trace_metrics or not isinstance(trace_metrics, dict):
        return

    for section in ("turn_metrics", "conversation_metrics"):
        section_data = trace_metrics.get(section, {})
        metrics = section_data.get("metrics", {})
        metric = metrics.get(metric_name)
        if metric is None:
            continue

        override = metric.get("override")
        if not override or override.get("annotation_id") != deleted_annotation_id:
            continue

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

    flag_modified(db_trace, "trace_metrics")


def _revert_turn_override(
    db: Session,
    db_trace: models.Trace,
    target_reference: Optional[str],
    deleted_annotation_id: str,
    replacement: Optional[models.Annotation],
) -> None:
    if not target_reference:
        return
    turn_num = parse_turn_number(target_reference)
    if turn_num is None:
        return

    trace_metrics = db_trace.trace_metrics
    if not trace_metrics or not isinstance(trace_metrics, dict):
        return

    turn_overrides = trace_metrics.get("turn_overrides", {})
    turn_key = str(turn_num)
    existing = turn_overrides.get(turn_key)
    if not existing:
        return

    override = existing.get("override")
    if not override or override.get("annotation_id") != deleted_annotation_id:
        return

    original_val = override["original_value"]

    if replacement:
        passed = annotation_passed(db, replacement)
        if passed == original_val:
            turn_overrides.pop(turn_key, None)
        else:
            now = datetime.now(timezone.utc).isoformat()
            turn_overrides[turn_key] = {
                "success": passed,
                "override": {
                    "original_value": original_val,
                    "annotation_id": str(replacement.id),
                    "overridden_by": str(replacement.user_id),
                    "overridden_at": now,
                },
            }
    else:
        turn_overrides.pop(turn_key, None)

    if not turn_overrides:
        trace_metrics.pop("turn_overrides", None)

    flag_modified(db_trace, "trace_metrics")


def recalculate_overall_status(db_trace: models.Trace) -> None:
    trace_metrics = db_trace.trace_metrics
    if not trace_metrics or not isinstance(trace_metrics, dict):
        _apply_outcome(db_trace, Execution.ERROR, None)
        return

    all_metrics = _get_all_trace_metric_values(trace_metrics)
    if not all_metrics:
        _apply_outcome(db_trace, Execution.ERROR, None)
        return

    execution, verdict = classify_metrics(all_metrics)

    turn_overrides = trace_metrics.get("turn_overrides", {})
    if turn_overrides:
        turns_passed = all(entry.get("success", True) for entry in turn_overrides.values())
        if execution == Execution.OK and turns_passed is False:
            verdict = Verdict.FAIL

    _apply_outcome(db_trace, execution, verdict)
