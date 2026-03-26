"""
Service layer for trace review override logic.

Handles applying, reverting, and recalculating overrides on trace_metrics
whenever a human review is created, updated, or deleted on a Trace.

Trace metrics live in a JSONB column with the structure::

    {
        "turn_metrics": { "metrics": { "<name>": { "is_successful": ..., ... } } },
        "conversation_metrics": { "metrics": { "<name>": { "is_successful": ..., ... } } },
        "turn_overrides": {
            "<turn_number>": {
                "success": bool,
                "override": { "original_value": bool, "review_id": ..., ... }
            }
        }
    }
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app import models
from rhesis.backend.app.constants import (
    OverallTestResult,
    REVIEW_TARGET_METRIC,
    REVIEW_TARGET_TRACE,
    REVIEW_TARGET_TURN,
    TestResultStatus,
    categorize_test_result_status,
)


def _is_passed_status(status_name: str) -> bool:
    return categorize_test_result_status(status_name) == OverallTestResult.PASSED


def _parse_turn_number(reference: str) -> Optional[int]:
    """Extract the turn number from a reference like 'Turn 2'."""
    digits = re.sub(r"\D", "", reference)
    return int(digits) if digits else None


def _set_trace_status(db_trace: models.Trace, passed: bool) -> None:
    """Look up the Pass/Fail status by name and assign to trace_metrics_status_id."""
    db = Session.object_session(db_trace)
    if db is None:
        return
    target_name = TestResultStatus.PASS.value if passed else TestResultStatus.FAIL.value
    status = (
        db.query(models.Status)
        .filter(
            models.Status.name == target_name,
            models.Status.organization_id == db_trace.organization_id,
        )
        .first()
    )
    if status:
        db_trace.trace_metrics_status_id = status.id


def _find_metric_in_trace_metrics(
    trace_metrics: Dict[str, Any], metric_name: str
) -> Optional[Dict[str, Any]]:
    """Find a metric entry across turn_metrics and conversation_metrics sections."""
    for section in ("turn_metrics", "conversation_metrics"):
        section_data = trace_metrics.get(section, {})
        metrics = section_data.get("metrics", {})
        if metric_name in metrics:
            return metrics[metric_name]
    return None


def _get_all_trace_metric_values(trace_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collect all metric entries across both sections."""
    all_metrics = []
    for section in ("turn_metrics", "conversation_metrics"):
        section_data = trace_metrics.get(section, {})
        metrics = section_data.get("metrics", {})
        for m in metrics.values():
            if isinstance(m, dict):
                all_metrics.append(m)
    return all_metrics


def apply_review_override(
    db_trace: models.Trace,
    target_type: str,
    target_reference: Optional[str],
    status_details: Dict[str, Any],
    current_user: models.User,
    review_id: str,
) -> None:
    """Apply a review override to trace_metrics or trace_metrics_status_id."""
    review_passed = _is_passed_status(status_details.get("name", ""))
    now = datetime.now(timezone.utc).isoformat()

    if target_type == REVIEW_TARGET_METRIC and target_reference:
        _apply_metric_override(
            db_trace, target_reference, review_passed, review_id, current_user, now
        )
        recalculate_overall_status(db_trace)
    elif target_type == REVIEW_TARGET_TURN:
        _apply_turn_override(
            db_trace, target_reference, review_passed, review_id,
            current_user, now,
        )
        recalculate_overall_status(db_trace)
    elif target_type == REVIEW_TARGET_TRACE:
        _set_trace_status(db_trace, review_passed)


def _apply_metric_override(
    db_trace: models.Trace,
    metric_name: str,
    review_passed: bool,
    review_id: str,
    current_user: models.User,
    now: str,
) -> None:
    """Override a single metric's is_successful value in trace_metrics."""
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
        original_val = (
            existing_override["original_value"] if existing_override else current_val
        )

        if review_passed == original_val:
            metric["is_successful"] = original_val
            metric.pop("override", None)
        else:
            metric["is_successful"] = review_passed
            metric["override"] = {
                "original_value": original_val,
                "review_id": review_id,
                "overridden_by": str(current_user.id),
                "overridden_at": now,
            }

    flag_modified(db_trace, "trace_metrics")


def _apply_turn_override(
    db_trace: models.Trace,
    target_reference: Optional[str],
    review_passed: bool,
    review_id: str,
    current_user: models.User,
    now: str,
) -> None:
    """Override a specific turn's success value in trace_metrics.turn_overrides.

    Per-turn overrides are stored under ``trace_metrics["turn_overrides"]``
    keyed by turn number (as string).  Each entry mirrors the
    ``conversation_summary`` turn-override pattern used by TestResult:
    ``{ "success": bool, "override": { "original_value": ..., ... } }``.
    """
    if not target_reference:
        return
    turn_num = _parse_turn_number(target_reference)
    if turn_num is None:
        return

    trace_metrics = db_trace.trace_metrics
    if not trace_metrics or not isinstance(trace_metrics, dict):
        return

    turn_section = trace_metrics.get("turn_metrics", {})
    metrics = turn_section.get("metrics", {})
    automated_passed = all(
        m.get("is_successful", False)
        for m in metrics.values()
        if isinstance(m, dict)
    ) if metrics else False

    if "turn_overrides" not in trace_metrics:
        trace_metrics["turn_overrides"] = {}

    turn_key = str(turn_num)
    existing = trace_metrics["turn_overrides"].get(turn_key, {})
    existing_override = existing.get("override")
    original_val = (
        existing_override["original_value"]
        if existing_override
        else automated_passed
    )

    if review_passed == original_val:
        trace_metrics["turn_overrides"].pop(turn_key, None)
        if not trace_metrics["turn_overrides"]:
            trace_metrics.pop("turn_overrides", None)
    else:
        trace_metrics["turn_overrides"][turn_key] = {
            "success": review_passed,
            "override": {
                "original_value": original_val,
                "review_id": review_id,
                "overridden_by": str(current_user.id),
                "overridden_at": now,
            },
        }

    flag_modified(db_trace, "trace_metrics")


def revert_override(
    db_trace: models.Trace,
    target_type: str,
    target_reference: Optional[str],
    deleted_review_id: str,
    remaining_reviews: List[Dict[str, Any]],
) -> None:
    """Revert an override when a review is deleted."""
    if target_type == REVIEW_TARGET_TRACE:
        same_target = [
            r
            for r in remaining_reviews
            if r.get("target", {}).get("type") == REVIEW_TARGET_TRACE
        ]
        if same_target:
            latest = max(
                same_target,
                key=lambda r: r.get("updated_at") or r.get("created_at") or "",
            )
            review_passed = _is_passed_status(
                latest.get("status", {}).get("name", "")
            )
            _set_trace_status(db_trace, review_passed)
        else:
            recalculate_overall_status(db_trace)
        return

    if target_type == REVIEW_TARGET_TURN:
        same_target = [
            r
            for r in remaining_reviews
            if r.get("target", {}).get("type") == REVIEW_TARGET_TURN
            and r.get("target", {}).get("reference") == target_reference
        ]
        replacement = (
            max(
                same_target,
                key=lambda r: r.get("updated_at") or r.get("created_at") or "",
            )
            if same_target
            else None
        )
        _revert_turn_override(
            db_trace, target_reference, deleted_review_id, replacement
        )
        recalculate_overall_status(db_trace)
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
        max(
            same_target,
            key=lambda r: r.get("updated_at") or r.get("created_at") or "",
        )
        if same_target
        else None
    )

    if target_type == REVIEW_TARGET_METRIC:
        _revert_metric_override(
            db_trace, target_reference, deleted_review_id, replacement
        )

    recalculate_overall_status(db_trace)


def _revert_metric_override(
    db_trace: models.Trace,
    metric_name: str,
    deleted_review_id: str,
    replacement_review: Optional[Dict[str, Any]],
) -> None:
    """Revert a metric override, optionally re-applying a replacement review."""
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
        if not override or override.get("review_id") != deleted_review_id:
            continue

        original_val = override["original_value"]

        if replacement_review:
            review_passed = _is_passed_status(
                replacement_review.get("status", {}).get("name", "")
            )
            if review_passed == original_val:
                metric["is_successful"] = original_val
                metric.pop("override", None)
            else:
                now = datetime.now(timezone.utc).isoformat()
                metric["is_successful"] = review_passed
                metric["override"] = {
                    "original_value": original_val,
                    "review_id": replacement_review["review_id"],
                    "overridden_by": replacement_review.get("user", {}).get(
                        "user_id", ""
                    ),
                    "overridden_at": now,
                }
        else:
            metric["is_successful"] = original_val
            metric.pop("override", None)

    flag_modified(db_trace, "trace_metrics")


def _revert_turn_override(
    db_trace: models.Trace,
    target_reference: Optional[str],
    deleted_review_id: str,
    replacement_review: Optional[Dict[str, Any]],
) -> None:
    """Revert a specific per-turn override, optionally re-applying a replacement."""
    if not target_reference:
        return
    turn_num = _parse_turn_number(target_reference)
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
    if not override or override.get("review_id") != deleted_review_id:
        return

    original_val = override["original_value"]

    if replacement_review:
        review_passed = _is_passed_status(
            replacement_review.get("status", {}).get("name", "")
        )
        if review_passed == original_val:
            turn_overrides.pop(turn_key, None)
        else:
            now = datetime.now(timezone.utc).isoformat()
            turn_overrides[turn_key] = {
                "success": review_passed,
                "override": {
                    "original_value": original_val,
                    "review_id": replacement_review["review_id"],
                    "overridden_by": replacement_review.get("user", {}).get(
                        "user_id", ""
                    ),
                    "overridden_at": now,
                },
            }
    else:
        turn_overrides.pop(turn_key, None)

    if not turn_overrides:
        trace_metrics.pop("turn_overrides", None)

    flag_modified(db_trace, "trace_metrics")


def recalculate_overall_status(db_trace: models.Trace) -> None:
    """Recalculate trace_metrics_status_id from metrics and turn overrides."""
    trace_metrics = db_trace.trace_metrics
    if not trace_metrics or not isinstance(trace_metrics, dict):
        return

    all_metrics = _get_all_trace_metric_values(trace_metrics)
    if not all_metrics:
        return

    metrics_passed = all(m.get("is_successful", False) for m in all_metrics)

    turn_overrides = trace_metrics.get("turn_overrides", {})
    turns_passed = all(
        entry.get("success", True) for entry in turn_overrides.values()
    )

    _set_trace_status(db_trace, metrics_passed and turns_passed)
