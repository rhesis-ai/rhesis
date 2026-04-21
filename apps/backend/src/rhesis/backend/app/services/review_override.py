"""
Service layer for review override logic.

Handles applying, reverting, and recalculating overrides on test_metrics
(metric-level) and test_output (turn-level) whenever a human review is
created, updated, or deleted.

All functions operate on already-loaded ORM instances and obtain the DB
session via Session.object_session() rather than accepting it as a parameter.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app import models
from rhesis.backend.app.constants import (
    REVIEW_TARGET_METRIC,
    REVIEW_TARGET_TEST_RESULT,
    REVIEW_TARGET_TURN,
    OverallTestResult,
    TestResultStatus,
    categorize_test_result_status,
)
from rhesis.backend.app.models.user import User


def is_passed_status(status_name: str) -> bool:
    """Determine if a status name represents a passed/successful outcome."""
    return categorize_test_result_status(status_name) == OverallTestResult.PASSED


def _parse_turn_number(reference: str) -> Optional[int]:
    """Extract the turn number from a reference like 'Turn 2'."""
    digits = re.sub(r"\D", "", reference)
    return int(digits) if digits else None


def _set_pass_fail_status(
    db_test_result: models.TestResult,
    passed: bool,
) -> None:
    """Look up the Pass/Fail status by name and assign it to the test result."""
    db = Session.object_session(db_test_result)
    if db is None:
        return
    target_name = TestResultStatus.PASS.value if passed else TestResultStatus.FAIL.value
    status = (
        db.query(models.Status)
        .filter(
            models.Status.name == target_name,
            models.Status.organization_id == db_test_result.organization_id,
        )
        .first()
    )
    if status:
        db_test_result.status_id = status.id


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
    now = datetime.utcnow().isoformat()

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
        _set_pass_fail_status(db_test_result, review_passed)


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
    metric = metrics.get(metric_name)
    if metric is None:
        return

    current_val = metric.get("is_successful", False)
    existing_override = metric.get("override")
    original_val = existing_override["original_value"] if existing_override else current_val

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
    metric = metrics.get(metric_name)
    if metric is None:
        return

    override = metric.get("override")
    if not override or override.get("review_id") != deleted_review_id:
        return

    original_val = override["original_value"]

    if replacement_review:
        review_passed = is_passed_status(replacement_review.get("status", {}).get("name", ""))
        if review_passed == original_val:
            metric["is_successful"] = original_val
            metric.pop("override", None)
        else:
            now = datetime.utcnow().isoformat()
            metric["is_successful"] = review_passed
            metric["override"] = {
                "original_value": original_val,
                "review_id": replacement_review["review_id"],
                "overridden_by": replacement_review.get("user", {}).get("user_id", ""),
                "overridden_at": now,
            }
    else:
        metric["is_successful"] = original_val
        metric.pop("override", None)

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
                now = datetime.utcnow().isoformat()
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


def recalculate_overall_status(
    db_test_result: models.TestResult,
) -> None:
    """Recalculate the overall test result Pass/Fail based on current metric values."""
    test_metrics = db_test_result.test_metrics
    if not test_metrics or not isinstance(test_metrics, dict):
        return
    metrics = test_metrics.get("metrics")
    if not metrics or not isinstance(metrics, dict):
        return

    all_passed = all(m.get("is_successful", False) for m in metrics.values() if isinstance(m, dict))
    _set_pass_fail_status(db_test_result, all_passed)
