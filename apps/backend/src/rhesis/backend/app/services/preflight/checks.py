"""Individual preflight check functions."""

import asyncio
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.behavior import Behavior
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.metric import Metric, behavior_metric_association
from rhesis.backend.app.models.prompt import Prompt
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_set import TestSet, test_test_set_association
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.app.schemas.preflight import PreflightCheckResult, PreflightCheckStatus

from .constants import (
    CHECK_BEHAVIOR_METRIC_COVERAGE,
    CHECK_ENDPOINT_CONNECTIVITY,
    CHECK_EVALUATION_MODEL,
    CHECK_EXECUTION_MODEL,
    CHECK_METRIC_COMPATIBILITY,
    CHECK_METRIC_FUNCTIONALITY,
    CHECK_TEST_SET_NOT_EMPTY,
)
from .utils import (
    _apply_test_set_fields,
    _make_composite_key,
    _make_result,
    _publish_check_status,
    _publish_result,
    _verify_model_responds,
)

logger = logging.getLogger(__name__)


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

        model = await asyncio.to_thread(
            get_evaluation_model_with_override, db, user, model_id=evaluation_model_id
        )
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

        model = await asyncio.to_thread(
            get_execution_model_with_override, db, user, model_id=execution_model_id
        )
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


async def _validate_metrics_loadable(
    db: Session,
    user: User,
    metrics: List[Metric],
    evaluation_model_id: Optional[str] = None,
) -> PreflightCheckResult:
    """Validate metrics can be instantiated without running full LLM evaluation."""
    check_id = CHECK_METRIC_FUNCTIONALITY

    from rhesis.backend.app.utils.user_model_utils import (
        get_evaluation_model_with_override,
    )
    from rhesis.backend.metrics.metric_config import validate_metric_configs
    from rhesis.backend.metrics.strategies.local import prepare_metrics

    metric_configs, invalid_results = validate_metric_configs(metrics)

    load_errors: list[str] = []
    loaded_count = 0

    if metric_configs:
        model = await asyncio.to_thread(
            get_evaluation_model_with_override,
            db,
            user,
            model_id=evaluation_model_id,
        )
        org_id = str(user.organization_id) if user.organization_id else None

        try:
            metric_tasks = await asyncio.to_thread(
                prepare_metrics,
                metric_configs,
                "",
                [],
                model=model,
                db=db,
                organization_id=org_id,
            )
            loaded_count = len(metric_tasks)
        except Exception as e:
            load_errors.append(str(e))

    for key, detail in invalid_results.items():
        err = detail.get("error", "unknown") if isinstance(detail, dict) else str(detail)
        load_errors.append(f"{key}: {err}")

    total = len(metric_configs) + len(invalid_results)
    failed_count = total - loaded_count

    if failed_count > 0:
        return _make_result(
            check_id,
            PreflightCheckStatus.WARNING,
            f"{failed_count} of {total} metric(s) failed to load",
            "; ".join(load_errors[:5]) if load_errors else None,
        )

    metric_names = [m.name for m in metrics if m.name]
    return _make_result(
        check_id,
        PreflightCheckStatus.PASSED,
        f"All {loaded_count} metric(s) loaded successfully",
        ", ".join(metric_names) if metric_names else None,
    )


def _infer_endpoint_capabilities(endpoint: Endpoint) -> dict[str, bool]:
    """Derive what data the endpoint provides from its response_mapping."""
    mapping = endpoint.response_mapping or {}
    return {
        "context": "context" in mapping,
        "tool_calls": "tool_calls" in mapping,
        "metadata": "metadata" in mapping,
    }


TOOL_CALLS_CLASS_NAMES = {"DeepEvalToolUse"}


def _check_metric_endpoint_issues(
    metrics: List[Metric],
    capabilities: dict[str, bool],
    missing_ground_truth_count: int,
    total_tests: int,
) -> list[str]:
    """Return one issue string per incompatible metric (deduplicated by metric)."""
    issues: list[str] = []
    for m in metrics:
        name = m.name or m.class_name or "Unknown"
        if m.context_required and not capabilities["context"]:
            issues.append(
                f"{name} requires context but endpoint response mapping has no context field"
            )
        if m.ground_truth_required and missing_ground_truth_count > 0:
            issues.append(
                f"{name} requires ground truth but {missing_ground_truth_count} of "
                f"{total_tests} test(s) have no expected_response"
            )
        if m.class_name in TOOL_CALLS_CLASS_NAMES and not capabilities["tool_calls"]:
            issues.append(
                f"{name} requires tool_calls but endpoint response mapping has no tool_calls field"
            )
    return issues


async def check_metric_compatibility(
    db: Session,
    endpoint: Endpoint,
    test_set_id: UUID,
    metric_mode: str,
    selected_metrics: Optional[list] = None,
    is_multi_turn: bool = False,
    correlation_id: Optional[str] = None,
    publish: bool = True,
    test_set_name: Optional[str] = None,
) -> PreflightCheckResult:
    """Check whether metrics' data requirements match endpoint capabilities."""
    check_id = CHECK_METRIC_COMPATIBILITY
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
        from rhesis.backend.app.schemas.metric import MetricScope

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
                PreflightCheckStatus.SKIPPED,
                "No metrics to check compatibility for",
            )
        else:
            required_scope = MetricScope.MULTI_TURN if is_multi_turn else MetricScope.SINGLE_TURN
            scope_compatible = [
                m
                for m in metrics
                if m.class_name and m.metric_scope and required_scope.value in m.metric_scope
            ]

            if not scope_compatible:
                result = _make_result(
                    check_id,
                    PreflightCheckStatus.SKIPPED,
                    "No scope-compatible metrics to validate",
                )
            else:
                capabilities = _infer_endpoint_capabilities(endpoint)

                # Ground-truth coverage only applies to single-turn tests: multi-turn tests
                # have prompt_id=NULL so the Prompt join would undercount. Skip the query
                # entirely when no metric needs it.
                needs_ground_truth = any(m.ground_truth_required for m in scope_compatible)
                if needs_ground_truth and required_scope == MetricScope.SINGLE_TURN:
                    total_tests = (
                        db.query(test_test_set_association.c.test_id)
                        .filter(test_test_set_association.c.test_set_id == test_set_id)
                        .count()
                    )
                    missing_ground_truth = (
                        db.query(Prompt.id)
                        .join(Test, Test.prompt_id == Prompt.id)
                        .join(
                            test_test_set_association,
                            Test.id == test_test_set_association.c.test_id,
                        )
                        .filter(test_test_set_association.c.test_set_id == test_set_id)
                        .filter(
                            (Prompt.expected_response.is_(None)) | (Prompt.expected_response == "")
                        )
                        .count()
                    )
                else:
                    total_tests = 0
                    missing_ground_truth = 0

                issues = _check_metric_endpoint_issues(
                    scope_compatible, capabilities, missing_ground_truth, total_tests
                )

                if issues:
                    # Dedupe by metric: each metric contributes at most one entry per requirement,
                    # so count unique issues (one per metric-requirement pair) for the summary.
                    result = _make_result(
                        check_id,
                        PreflightCheckStatus.WARNING,
                        f"{len(issues)} compatibility issue(s) detected",
                        "; ".join(issues[:5]),
                    )
                else:
                    metric_names = [m.name for m in scope_compatible if m.name]
                    result = _make_result(
                        check_id,
                        PreflightCheckStatus.PASSED,
                        f"All {len(scope_compatible)} metric(s) are "
                        "compatible with endpoint configuration",
                        ", ".join(metric_names) if metric_names else None,
                    )

    except Exception as e:
        result = _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "Error checking metric compatibility",
            str(e),
        )

    _apply_test_set_fields(result, ts_id_str, test_set_name)
    await _publish_result(result, correlation_id, publish)
    return result


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
                result = await _validate_metrics_loadable(
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
