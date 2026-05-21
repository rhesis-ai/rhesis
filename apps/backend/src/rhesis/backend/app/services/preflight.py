"""Preflight check service for validating test execution environment."""

import asyncio
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.behavior import Behavior
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.metric import Metric, behavior_metric_association
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_set import TestSet, test_test_set_association
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.preflight import PreflightCheckResult, PreflightCheckStatus
from rhesis.backend.app.schemas.websocket import ChannelTarget, EventType, WebSocketMessage

logger = logging.getLogger(__name__)

CHECK_ENDPOINT_CONNECTIVITY = "endpoint_connectivity"
CHECK_EVALUATION_MODEL = "evaluation_model"
CHECK_EXECUTION_MODEL = "execution_model"
CHECK_BEHAVIOR_METRIC_COVERAGE = "behavior_metric_coverage"
CHECK_METRIC_FUNCTIONALITY = "metric_functionality"
CHECK_TEST_SET_NOT_EMPTY = "test_set_not_empty"

SHARED_CHECKS = {
    CHECK_ENDPOINT_CONNECTIVITY,
    CHECK_EVALUATION_MODEL,
    CHECK_EXECUTION_MODEL,
}

PER_TEST_SET_CHECKS = {
    CHECK_TEST_SET_NOT_EMPTY,
    CHECK_BEHAVIOR_METRIC_COVERAGE,
    CHECK_METRIC_FUNCTIONALITY,
}

LABELS = {
    CHECK_ENDPOINT_CONNECTIVITY: "Endpoint Connectivity",
    CHECK_EVALUATION_MODEL: "Evaluation Model",
    CHECK_EXECUTION_MODEL: "Execution Model",
    CHECK_BEHAVIOR_METRIC_COVERAGE: "Behavior-Metric Coverage",
    CHECK_METRIC_FUNCTIONALITY: "Metric Functionality",
    CHECK_TEST_SET_NOT_EMPTY: "Test Set Has Tests",
}


def _make_composite_key(
    check_id: str,
    test_set_id: Optional[str] = None,
) -> str:
    if test_set_id and check_id in PER_TEST_SET_CHECKS:
        return f"{check_id}:{test_set_id}"
    return check_id


def _make_result(
    check_id: str,
    status: PreflightCheckStatus,
    message: Optional[str] = None,
    detail: Optional[str] = None,
) -> PreflightCheckResult:
    return PreflightCheckResult(
        check_id=check_id,
        label=LABELS[check_id],
        status=status,
        message=message,
        detail=detail,
    )


async def _publish_check_status(
    correlation_id: str,
    check_id: str,
    status: PreflightCheckStatus,
    message: Optional[str] = None,
    detail: Optional[str] = None,
    test_set_id: Optional[str] = None,
    test_set_name: Optional[str] = None,
    composite_key: Optional[str] = None,
) -> None:
    from rhesis.backend.app.services.websocket.publisher import publish_event_async

    await publish_event_async(
        WebSocketMessage(
            type=EventType.PREFLIGHT_CHECK_UPDATE,
            payload={
                "check_id": check_id,
                "label": LABELS[check_id],
                "status": status.value,
                "message": message,
                "detail": detail,
                "correlation_id": correlation_id,
                "test_set_id": test_set_id,
                "test_set_name": test_set_name,
                "composite_key": composite_key or check_id,
            },
        ),
        ChannelTarget(channel=f"preflight:{correlation_id}"),
    )


def _apply_test_set_fields(
    result: PreflightCheckResult,
    test_set_id: Optional[str] = None,
    test_set_name: Optional[str] = None,
) -> PreflightCheckResult:
    if test_set_id:
        result.test_set_id = test_set_id
        result.test_set_name = test_set_name
        result.composite_key = _make_composite_key(result.check_id, test_set_id)
    else:
        result.composite_key = result.check_id
    return result


async def _publish_result(
    result: PreflightCheckResult,
    correlation_id: Optional[str],
    publish: bool,
) -> None:
    if publish and correlation_id:
        await _publish_check_status(
            correlation_id,
            result.check_id,
            result.status,
            result.message,
            result.detail,
            result.test_set_id,
            result.test_set_name,
            result.composite_key,
        )


async def _verify_model_responds(model) -> None:
    """Send a minimal completion request to verify the model actually works."""
    from rhesis.sdk.models.base import BaseLLM

    if not isinstance(model, BaseLLM):
        return
    await asyncio.wait_for(model.a_generate("Hi", max_tokens=1), timeout=10.0)


async def check_test_set_not_empty(
    db: Session,
    test_set_id: UUID,
    correlation_id: Optional[str] = None,
    publish: bool = True,
    test_set_name: Optional[str] = None,
) -> PreflightCheckResult:
    check_id = CHECK_TEST_SET_NOT_EMPTY
    ts_id_str = str(test_set_id) if test_set_name else None
    comp_key = _make_composite_key(check_id, ts_id_str)

    if publish and correlation_id:
        await _publish_check_status(
            correlation_id,
            check_id,
            PreflightCheckStatus.RUNNING,
            test_set_id=ts_id_str,
            test_set_name=test_set_name,
            composite_key=comp_key,
        )

    try:
        count = (
            db.query(test_test_set_association.c.test_id)
            .filter(test_test_set_association.c.test_set_id == test_set_id)
            .count()
        )

        if count == 0:
            result = _make_result(
                check_id,
                PreflightCheckStatus.FAILED,
                "Test set has no tests",
                "Add tests to the test set before executing.",
            )
        else:
            result = _make_result(
                check_id,
                PreflightCheckStatus.PASSED,
                f"Test set contains {count} test(s)",
            )
    except Exception as e:
        result = _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "Error checking test set contents",
            str(e),
        )

    _apply_test_set_fields(result, ts_id_str, test_set_name)
    await _publish_result(result, correlation_id, publish)
    return result


def _describe_model(model) -> str:
    """Return a short description of a model for display."""
    from rhesis.sdk.models.base import BaseLLM

    if isinstance(model, BaseLLM):
        provider = getattr(model, "PROVIDER", "unknown")
        name = getattr(model, "model_name", "unknown")
        return f"{provider} / {name}"
    return str(model)


def _get_requested_model_label(
    db: Session, model_id: Optional[str], organization_id: str
) -> Optional[str]:
    """Look up the user-selected model record and return its label."""
    if not model_id:
        return None
    from uuid import UUID as UUIDType

    from rhesis.backend.app import crud

    try:
        model_uuid = UUIDType(model_id)
    except (ValueError, AttributeError):
        return None

    model = crud.get_model(db=db, model_id=model_uuid, organization_id=organization_id)
    if not model:
        return None
    return str(model.name)


def _build_model_detail(
    resolved_model,
    model_id: Optional[str],
    db: Session,
    user: User,
    purpose: str = "evaluation",
) -> str:
    """Build detail showing the user-selected model name."""
    resolved = _describe_model(resolved_model)
    effective_id = model_id
    if not effective_id:
        settings = getattr(user.settings.models, purpose, None)
        if settings:
            mid = getattr(settings, "model_id", None)
            if mid:
                effective_id = str(mid)
    requested = _get_requested_model_label(db, effective_id, str(user.organization_id))
    if requested:
        return requested
    return resolved


def _extract_response_preview(response: dict, max_length: int = 500) -> str:
    """Extract a human-readable preview from an endpoint response dict."""
    import json

    output = response.get("output")
    if output and isinstance(output, str):
        text = output.strip()
    else:
        try:
            text = json.dumps(response, indent=2, default=str)
        except (TypeError, ValueError):
            text = str(response)

    if len(text) > max_length:
        text = text[:max_length] + "…"
    return text


async def check_endpoint_connectivity(
    db: Session,
    endpoint: Endpoint,
    correlation_id: Optional[str] = None,
    publish: bool = True,
) -> PreflightCheckResult:
    check_id = CHECK_ENDPOINT_CONNECTIVITY

    if publish and correlation_id:
        await _publish_check_status(
            correlation_id,
            check_id,
            PreflightCheckStatus.RUNNING,
        )

    try:
        from rhesis.backend.app.services.invokers import create_invoker
        from rhesis.backend.app.services.invokers.context import InvocationContext
        from rhesis.backend.app.services.invokers.conversation import (
            ConversationTracker,
        )

        input_data: dict = {"input": "[place your input here]"}

        if ConversationTracker.detect_stateless_mode(endpoint):
            messages: list = []
            system_prompt = ConversationTracker.extract_system_prompt(endpoint)
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": input_data["input"]})
            input_data["messages"] = messages

        context = InvocationContext(db=db, endpoint=endpoint, input_data=input_data)
        response = await asyncio.wait_for(create_invoker(context).invoke(), timeout=30.0)

        from rhesis.backend.app.services.invokers.common.schemas import (
            ErrorResponse,
        )

        is_error = isinstance(response, ErrorResponse) or (
            isinstance(response, dict) and response.get("error")
        )

        if is_error:
            detail = (
                response.message if isinstance(response, ErrorResponse) else response.get("error")
            )
            result = _make_result(
                check_id,
                PreflightCheckStatus.FAILED,
                "Endpoint connectivity check failed",
                str(detail) if detail else None,
            )
        else:
            response_preview = _extract_response_preview(response)
            result = _make_result(
                check_id,
                PreflightCheckStatus.PASSED,
                "Endpoint is reachable and responding",
                response_preview,
            )

    except asyncio.TimeoutError:
        result = _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "Endpoint connectivity check timed out",
        )
    except Exception as e:
        result = _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "Unexpected error during connectivity check",
            str(e),
        )

    _apply_test_set_fields(result)
    await _publish_result(result, correlation_id, publish)
    return result


async def check_evaluation_model(
    db: Session,
    user: User,
    evaluation_model_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    publish: bool = True,
) -> PreflightCheckResult:
    check_id = CHECK_EVALUATION_MODEL

    if publish and correlation_id:
        await _publish_check_status(
            correlation_id,
            check_id,
            PreflightCheckStatus.RUNNING,
        )

    try:
        from rhesis.backend.app.utils.user_model_utils import (
            get_evaluation_model_with_override,
        )

        model = get_evaluation_model_with_override(db, user, model_id=evaluation_model_id)
        await _verify_model_responds(model)
        model_detail = _build_model_detail(model, evaluation_model_id, db, user, "evaluation")
        result = _make_result(
            check_id,
            PreflightCheckStatus.PASSED,
            "Evaluation model is configured and valid",
            model_detail,
        )
    except asyncio.TimeoutError:
        result = _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "Evaluation model validation timed out",
            "The model did not respond within 10 seconds.",
        )
    except Exception as e:
        result = _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "Evaluation model configuration error",
            str(e),
        )

    _apply_test_set_fields(result)
    await _publish_result(result, correlation_id, publish)
    return result


async def check_execution_model(
    db: Session,
    user: User,
    execution_model_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    publish: bool = True,
) -> PreflightCheckResult:
    check_id = CHECK_EXECUTION_MODEL

    if publish and correlation_id:
        await _publish_check_status(
            correlation_id,
            check_id,
            PreflightCheckStatus.RUNNING,
        )

    try:
        from rhesis.backend.app.utils.user_model_utils import (
            get_execution_model_with_override,
        )

        model = get_execution_model_with_override(db, user, model_id=execution_model_id)
        await _verify_model_responds(model)
        model_detail = _build_model_detail(model, execution_model_id, db, user, "execution")
        result = _make_result(
            check_id,
            PreflightCheckStatus.PASSED,
            "Execution model is configured and valid",
            model_detail,
        )
    except asyncio.TimeoutError:
        result = _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "Execution model validation timed out",
            "The model did not respond within 10 seconds.",
        )
    except Exception as e:
        result = _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "Execution model configuration error",
            str(e),
        )

    _apply_test_set_fields(result)
    await _publish_result(result, correlation_id, publish)
    return result


async def check_behavior_metric_coverage(
    db: Session,
    test_set_id: UUID,
    metric_mode: str,
    selected_metrics: Optional[list] = None,
    correlation_id: Optional[str] = None,
    publish: bool = True,
    test_set_name: Optional[str] = None,
) -> PreflightCheckResult:
    check_id = CHECK_BEHAVIOR_METRIC_COVERAGE
    ts_id_str = str(test_set_id) if test_set_name else None
    comp_key = _make_composite_key(check_id, ts_id_str)

    if publish and correlation_id:
        await _publish_check_status(
            correlation_id,
            check_id,
            PreflightCheckStatus.RUNNING,
            test_set_id=ts_id_str,
            test_set_name=test_set_name,
            composite_key=comp_key,
        )

    try:
        if metric_mode == "define_custom":
            if not selected_metrics:
                result = _make_result(
                    check_id,
                    PreflightCheckStatus.FAILED,
                    "No custom metrics selected",
                    "Custom metric mode is active but no metrics were selected.",
                )
            else:
                metric_ids = [m.id for m in selected_metrics]
                names = [
                    row[0] for row in db.query(Metric.name).filter(Metric.id.in_(metric_ids)).all()
                ]
                result = _make_result(
                    check_id,
                    PreflightCheckStatus.PASSED,
                    f"{len(selected_metrics)} custom metric(s) selected",
                    ", ".join(names) if names else None,
                )
        elif metric_mode == "use_test_set":
            test_set = db.query(TestSet).filter(TestSet.id == test_set_id).first()
            if not test_set:
                result = _make_result(
                    check_id,
                    PreflightCheckStatus.FAILED,
                    "Test set not found",
                )
            elif not test_set.metrics:
                result = _make_result(
                    check_id,
                    PreflightCheckStatus.WARNING,
                    "Test set has no metrics configured",
                    "Add metrics to the test set or switch to behavior metrics.",
                )
            else:
                metric_names = [m.name for m in test_set.metrics if m.name]
                result = _make_result(
                    check_id,
                    PreflightCheckStatus.PASSED,
                    f"Test set has {len(test_set.metrics)} metric(s)",
                    ", ".join(metric_names) if metric_names else None,
                )
        else:
            behavior_rows = (
                db.query(Test.behavior_id, Behavior.name)
                .join(
                    test_test_set_association,
                    Test.id == test_test_set_association.c.test_id,
                )
                .join(Behavior, Behavior.id == Test.behavior_id)
                .filter(test_test_set_association.c.test_set_id == test_set_id)
                .filter(Test.behavior_id.isnot(None))
                .distinct()
                .all()
            )
            behavior_map = {row[0]: row[1] for row in behavior_rows}
            behavior_id_set = set(behavior_map.keys())

            if not behavior_id_set:
                result = _make_result(
                    check_id,
                    PreflightCheckStatus.WARNING,
                    "No behaviors found in test set",
                    "Tests in this set have no associated behaviors.",
                )
            else:
                behaviors_with_metrics = set(
                    row[0]
                    for row in db.query(behavior_metric_association.c.behavior_id)
                    .join(
                        Metric,
                        Metric.id == behavior_metric_association.c.metric_id,
                    )
                    .filter(behavior_metric_association.c.behavior_id.in_(behavior_id_set))
                    .filter(Metric.class_name.isnot(None))
                    .distinct()
                    .all()
                )

                missing = behavior_id_set - behaviors_with_metrics
                if missing:
                    names_list = [behavior_map.get(bid) or str(bid) for bid in missing]
                    names_str = ", ".join(names_list[:10])
                    if len(names_list) > 10:
                        names_str += f" and {len(names_list) - 10} more"
                    result = _make_result(
                        check_id,
                        PreflightCheckStatus.WARNING,
                        f"{len(missing)} of "
                        f"{len(behavior_id_set)} behavior(s)"
                        f" missing metric associations",
                        f"No metrics assigned to: {names_str}. "
                        "Tests linked to these behaviors will be "
                        "skipped during evaluation.",
                    )
                else:
                    behavior_names = list(behavior_map.values())
                    result = _make_result(
                        check_id,
                        PreflightCheckStatus.PASSED,
                        f"All {len(behavior_id_set)} behavior(s) have metrics",
                        ", ".join(n for n in behavior_names if n) or None,
                    )

    except Exception as e:
        result = _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "Error checking behavior-metric coverage",
            str(e),
        )

    _apply_test_set_fields(result, ts_id_str, test_set_name)
    await _publish_result(result, correlation_id, publish)
    return result


async def _evaluate_metrics_dry_run(
    db: Session,
    user: User,
    metrics: List[Metric],
    evaluation_model_id: Optional[str] = None,
) -> PreflightCheckResult:
    """Run a single evaluation with dummy data."""
    check_id = CHECK_METRIC_FUNCTIONALITY

    from rhesis.backend.app.utils.user_model_utils import (
        get_evaluation_model_with_override,
    )
    from rhesis.backend.metrics.evaluator import MetricEvaluator
    from rhesis.sdk.metrics.conversational.types import ConversationHistory

    model = get_evaluation_model_with_override(db, user, model_id=evaluation_model_id)
    org_id = str(user.organization_id) if user.organization_id else None

    dummy_conversation = ConversationHistory.from_messages([
        {"role": "user", "content": "Is this a test?"},
        {"role": "assistant", "content": "Yes, this is a test."},
    ])

    evaluator = MetricEvaluator(model=model, db=db, organization_id=org_id)
    eval_results = evaluator.evaluate(
        input_text="Is this a test?",
        output_text="Yes, this is a test.",
        expected_output="Yes, this is a test.",
        context=["This is a preflight test."],
        metrics=metrics,
        max_workers=3,
        conversation_history=dummy_conversation,
    )

    failed: list[str] = []
    succeeded = 0
    for name, detail in eval_results.items():
        if isinstance(detail, dict) and detail.get("error"):
            failed.append(f"{name}: {detail['error']}")
        else:
            succeeded += 1

    total = len(eval_results)
    if failed:
        return _make_result(
            check_id,
            PreflightCheckStatus.WARNING,
            f"{len(failed)} of {total} metric(s) returned errors",
            "; ".join(failed[:5]),
        )

    metric_names = [m.name for m in metrics if m.name]
    return _make_result(
        check_id,
        PreflightCheckStatus.PASSED,
        f"All {succeeded} metric(s) evaluated successfully",
        ", ".join(metric_names) if metric_names else None,
    )


async def check_metric_functionality(
    db: Session,
    user: User,
    test_set_id: UUID,
    metric_mode: str,
    selected_metrics: Optional[list] = None,
    is_multi_turn: bool = False,
    evaluation_model_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    publish: bool = True,
    test_set_name: Optional[str] = None,
) -> PreflightCheckResult:
    check_id = CHECK_METRIC_FUNCTIONALITY
    ts_id_str = str(test_set_id) if test_set_name else None
    comp_key = _make_composite_key(check_id, ts_id_str)

    if publish and correlation_id:
        await _publish_check_status(
            correlation_id,
            check_id,
            PreflightCheckStatus.RUNNING,
            test_set_id=ts_id_str,
            test_set_name=test_set_name,
            composite_key=comp_key,
        )

    try:
        metrics: List[Metric] = []

        if metric_mode == "define_custom" and selected_metrics:
            metric_ids = [m.id for m in selected_metrics]
            metrics = db.query(Metric).filter(Metric.id.in_(metric_ids)).all()
        elif metric_mode == "use_test_set":
            test_set = db.query(TestSet).filter(TestSet.id == test_set_id).first()
            if test_set:
                metrics = list(test_set.metrics)
        else:
            behavior_ids = (
                db.query(Test.behavior_id)
                .join(
                    test_test_set_association,
                    Test.id == test_test_set_association.c.test_id,
                )
                .filter(test_test_set_association.c.test_set_id == test_set_id)
                .filter(Test.behavior_id.isnot(None))
                .distinct()
                .all()
            )
            behavior_id_set = {b[0] for b in behavior_ids}
            if behavior_id_set:
                metrics = (
                    db.query(Metric)
                    .join(
                        behavior_metric_association,
                        Metric.id == behavior_metric_association.c.metric_id,
                    )
                    .filter(behavior_metric_association.c.behavior_id.in_(behavior_id_set))
                    .distinct()
                    .all()
                )

        if not metrics:
            result = _make_result(
                check_id,
                PreflightCheckStatus.WARNING,
                "No metrics found for this configuration",
            )
        else:
            from rhesis.backend.app.schemas.metric import MetricScope

            required_scope = MetricScope.MULTI_TURN if is_multi_turn else MetricScope.SINGLE_TURN
            scope_compatible = [
                m
                for m in metrics
                if m.class_name and m.metric_scope and required_scope.value in m.metric_scope
            ]

            if not scope_compatible:
                scope_label = required_scope.value
                has_class = [m for m in metrics if m.class_name]
                result = _make_result(
                    check_id,
                    PreflightCheckStatus.WARNING,
                    f"No metrics support {scope_label} scope",
                    f"This test set requires {scope_label} "
                    f"metrics, but none of the "
                    f"{len(has_class)} resolved metric(s) "
                    f"include that scope.",
                )
            else:
                result = await _evaluate_metrics_dry_run(
                    db, user, scope_compatible, evaluation_model_id
                )

    except Exception as e:
        result = _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "Error checking metric functionality",
            str(e),
        )

    _apply_test_set_fields(result, ts_id_str, test_set_name)
    await _publish_result(result, correlation_id, publish)
    return result


def compute_summary(
    results: List[PreflightCheckResult],
) -> tuple[str, int, int, int, int]:
    passed = sum(1 for r in results if r.status == PreflightCheckStatus.PASSED)
    failed = sum(1 for r in results if r.status == PreflightCheckStatus.FAILED)
    warnings = sum(1 for r in results if r.status == PreflightCheckStatus.WARNING)
    skipped = sum(1 for r in results if r.status == PreflightCheckStatus.SKIPPED)

    if failed > 0:
        summary = "failed"
    elif warnings > 0:
        summary = "warning"
    else:
        summary = "passed"

    return summary, passed, failed, warnings, skipped


def _result_to_payload(r: PreflightCheckResult) -> dict:
    return {
        "check_id": r.check_id,
        "label": r.label,
        "status": r.status.value,
        "message": r.message,
        "detail": r.detail,
        "test_set_id": r.test_set_id,
        "test_set_name": r.test_set_name,
        "composite_key": r.composite_key,
    }


async def run_preflight_checks_multi(
    db: Session,
    user: User,
    test_sets: list[tuple[UUID, str, bool]],
    endpoint_id: UUID,
    scoring_target: str = "fresh",
    metric_mode: str = "use_behavior",
    selected_metrics: Optional[list] = None,
    execution_model_id: Optional[str] = None,
    evaluation_model_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    publish: bool = True,
) -> List[PreflightCheckResult]:
    """Run preflight checks for one or more test sets.

    Shared checks (endpoint, models) run once.
    Per-test-set checks run for each test set.
    """
    results: List[PreflightCheckResult] = []
    tasks: list[tuple[str, asyncio.Task]] = []
    multi = len(test_sets) > 1
    ts_name_map: dict[str, str] = (
        {str(ts_id): ts_name for ts_id, ts_name, _ in test_sets} if multi else {}
    )

    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    any_multi_turn = any(mt for _, _, mt in test_sets)

    # --- Shared checks ---

    # Endpoint connectivity
    if scoring_target == "fresh":
        if endpoint:
            tasks.append(
                (
                    CHECK_ENDPOINT_CONNECTIVITY,
                    check_endpoint_connectivity(db, endpoint, correlation_id, publish),
                )
            )
        else:
            r = _make_result(
                CHECK_ENDPOINT_CONNECTIVITY,
                PreflightCheckStatus.FAILED,
                "Endpoint not found",
            )
            _apply_test_set_fields(r)
            results.append(r)
            await _publish_result(r, correlation_id, publish)
    else:
        if not endpoint:
            r = _make_result(
                CHECK_ENDPOINT_CONNECTIVITY,
                PreflightCheckStatus.FAILED,
                "Endpoint not found",
                "The endpoint is required even when reusing outputs.",
            )
        else:
            r = _make_result(
                CHECK_ENDPOINT_CONNECTIVITY,
                PreflightCheckStatus.SKIPPED,
                "Connectivity not tested when reusing outputs",
            )
        _apply_test_set_fields(r)
        results.append(r)
        await _publish_result(r, correlation_id, publish)

    # Evaluation model (always)
    tasks.append(
        (
            CHECK_EVALUATION_MODEL,
            check_evaluation_model(db, user, evaluation_model_id, correlation_id, publish),
        )
    )

    # Execution model (if any test set is multi-turn)
    if any_multi_turn:
        tasks.append(
            (
                CHECK_EXECUTION_MODEL,
                check_execution_model(db, user, execution_model_id, correlation_id, publish),
            )
        )

    # --- Per-test-set checks ---
    for ts_id, ts_name, is_mt in test_sets:
        ts_id_str = str(ts_id) if multi else None
        ts_label = ts_name if multi else None

        tasks.append(
            (
                _make_composite_key(CHECK_TEST_SET_NOT_EMPTY, ts_id_str),
                check_test_set_not_empty(
                    db,
                    ts_id,
                    correlation_id,
                    publish,
                    test_set_name=ts_label,
                ),
            )
        )

        tasks.append(
            (
                _make_composite_key(CHECK_BEHAVIOR_METRIC_COVERAGE, ts_id_str),
                check_behavior_metric_coverage(
                    db,
                    ts_id,
                    metric_mode,
                    selected_metrics,
                    correlation_id,
                    publish,
                    test_set_name=ts_label,
                ),
            )
        )

        tasks.append(
            (
                _make_composite_key(CHECK_METRIC_FUNCTIONALITY, ts_id_str),
                check_metric_functionality(
                    db,
                    user,
                    ts_id,
                    metric_mode,
                    selected_metrics,
                    is_mt,
                    evaluation_model_id,
                    correlation_id,
                    publish,
                    test_set_name=ts_label,
                ),
            )
        )

    # Run all concurrently
    if tasks:
        check_keys = [k for k, _ in tasks]
        coros = [coro for _, coro in tasks]
        task_results = await asyncio.gather(*coros, return_exceptions=True)
        for comp_key, tr in zip(check_keys, task_results):
            if isinstance(tr, Exception):
                base_check_id = comp_key.split(":")[0]
                logger.error(
                    f"Preflight check '{comp_key}' failed: {tr}",
                    exc_info=tr,
                )
                parts = comp_key.split(":", 1)
                ts_id = parts[1] if len(parts) > 1 else None
                ts_name = ts_name_map.get(ts_id) if ts_id else None
                results.append(
                    PreflightCheckResult(
                        check_id=base_check_id,
                        label=LABELS.get(base_check_id, base_check_id),
                        status=PreflightCheckStatus.FAILED,
                        message="Check raised an unexpected error",
                        detail=str(tr),
                        composite_key=comp_key,
                        test_set_id=ts_id,
                        test_set_name=ts_name,
                    )
                )
            else:
                results.append(tr)

    # Publish completion event
    if publish and correlation_id:
        from rhesis.backend.app.services.websocket.publisher import (
            publish_event_async,
        )

        summary, passed, failed, warnings, skipped = compute_summary(results)
        await publish_event_async(
            WebSocketMessage(
                type=EventType.PREFLIGHT_COMPLETE,
                payload={
                    "correlation_id": correlation_id,
                    "summary": summary,
                    "passed": passed,
                    "failed": failed,
                    "warnings": warnings,
                    "skipped": skipped,
                    "checks": [_result_to_payload(r) for r in results],
                },
            ),
            ChannelTarget(channel=f"preflight:{correlation_id}"),
        )

    return results


async def run_preflight_checks(
    db: Session,
    user: User,
    test_set_id: UUID,
    endpoint_id: UUID,
    scoring_target: str = "fresh",
    metric_mode: str = "use_behavior",
    selected_metrics: Optional[list] = None,
    execution_model_id: Optional[str] = None,
    evaluation_model_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    is_multi_turn: bool = False,
    publish: bool = True,
) -> List[PreflightCheckResult]:
    """Run preflight checks for a single test set (backward compat)."""
    test_set = db.query(TestSet).filter(TestSet.id == test_set_id).first()
    ts_name = test_set.name if test_set else str(test_set_id)
    return await run_preflight_checks_multi(
        db=db,
        user=user,
        test_sets=[(test_set_id, ts_name, is_multi_turn)],
        endpoint_id=endpoint_id,
        scoring_target=scoring_target,
        metric_mode=metric_mode,
        selected_metrics=selected_metrics,
        execution_model_id=execution_model_id,
        evaluation_model_id=evaluation_model_id,
        correlation_id=correlation_id,
        publish=publish,
    )
