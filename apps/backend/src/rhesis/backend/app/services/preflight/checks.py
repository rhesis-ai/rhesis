"""Individual preflight check functions."""

import asyncio
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.metric import Metric, requirement_metric_association
from rhesis.backend.app.models.prompt import Prompt
from rhesis.backend.app.models.requirement import Requirement
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_set import TestSet, test_test_set_association
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.app.schemas.preflight import PreflightCheckResult, PreflightCheckStatus
from rhesis.backend.app.utils.crud_utils import get_item_detail

from .constants import (
    CHECK_ENDPOINT_CONNECTIVITY,
    CHECK_EVALUATION_MODEL,
    CHECK_EXECUTION_MODEL,
    CHECK_METRIC_COMPATIBILITY,
    CHECK_METRIC_FUNCTIONALITY,
    CHECK_REQUIREMENT_METRIC_COVERAGE,
    CHECK_TEST_SET_NOT_EMPTY,
)
from .utils import (
    PreflightDbGate,
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

    from rhesis.backend.app.crud import model as model_crud

    try:
        model_uuid = UUIDType(model_id)
    except (ValueError, AttributeError):
        return None

    model = model_crud.get_model(db=db, model_id=model_uuid, organization_id=organization_id)
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


# --- Off-loop segments -------------------------------------------------------------
#
# Every function below takes the Session first and does the psycopg2 work for one
# check. They run through ``PreflightDbGate.run``, which puts them in a worker thread and
# lets only one in at a time -- see :class:`PreflightDbGate`.


def _count_test_set_tests(db: Session, test_set_id: UUID) -> int:
    return (
        db.query(test_test_set_association.c.test_id)
        .filter(test_test_set_association.c.test_set_id == test_set_id)
        .count()
    )


def _resolve_purpose_model(db: Session, user: User, purpose: str, override: Optional[str]):
    """Resolve the model for *purpose*, for *user*."""
    from rhesis.backend.app.utils.user_model_utils import resolve_model

    return resolve_model(db, user, purpose, override=override)


def _model_detail(db: Session, model, model_id: Optional[str], user: User, purpose: str) -> str:
    """:func:`_build_model_detail` with the session first, for ``PreflightDbGate.run``."""
    return _build_model_detail(model, model_id, db, user, purpose)


def _describe_metrics(db: Session, metrics: List[Metric]):
    """Validate metric configs and read the names, while the ORM rows are reachable."""
    from rhesis.backend.metrics.metric_config import validate_metric_configs

    metric_configs, invalid_results = validate_metric_configs(metrics)
    names = [m.name for m in metrics if m.name]
    return metric_configs, invalid_results, names


def _prepare_metrics(db: Session, metric_configs, model, organization_id: Optional[str]):
    from rhesis.backend.metrics.strategies.local import prepare_metrics

    return prepare_metrics(
        metric_configs,
        "",
        [],
        model=model,
        db=db,
        organization_id=organization_id,
    )


def _resolve_check_metrics(
    db: Session,
    test_set_id: UUID,
    metric_mode: str,
    selected_metrics: Optional[list],
    organization_id: str,
) -> List[Metric]:
    """The metrics a check should validate, for the caller's metric mode."""
    if metric_mode == "define_custom" and selected_metrics:
        metric_ids = [m.id for m in selected_metrics]
        return db.query(Metric).filter(Metric.id.in_(metric_ids)).all()

    if metric_mode == "use_test_set":
        test_set = get_item_detail(db, TestSet, test_set_id, organization_id=organization_id)
        return list(test_set.metrics) if test_set else []

    requirement_ids = (
        db.query(Test.requirement_id)
        .join(
            test_test_set_association,
            Test.id == test_test_set_association.c.test_id,
        )
        .filter(test_test_set_association.c.test_set_id == test_set_id)
        .filter(Test.requirement_id.isnot(None))
        .distinct()
        .all()
    )
    requirement_id_set = {b[0] for b in requirement_ids}
    if not requirement_id_set:
        return []

    return (
        db.query(Metric)
        .join(
            requirement_metric_association,
            Metric.id == requirement_metric_association.c.metric_id,
        )
        .filter(requirement_metric_association.c.requirement_id.in_(requirement_id_set))
        .distinct()
        .all()
    )


def _scope_compatible_metrics(metrics: List[Metric], is_multi_turn: bool) -> List[Metric]:
    required_scope = MetricScope.MULTI_TURN if is_multi_turn else MetricScope.SINGLE_TURN
    return [
        m
        for m in metrics
        if m.class_name and m.metric_scope and required_scope.value in m.metric_scope
    ]


async def check_test_set_not_empty(
    db: PreflightDbGate,
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
        count = await db.run(_count_test_set_tests, test_set_id)

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
    endpoint: Endpoint,
    correlation_id: Optional[str] = None,
    publish: bool = True,
) -> PreflightCheckResult:
    """Probe the endpoint once, without a session.

    The probe is awaited on the event loop, so the invoker gets ``db=None``: every
    psycopg2 call it would otherwise make there -- the auth-token refresh, a trace
    lookup -- would block the whole worker for as long as the probe runs, up to the
    30-second timeout below. The orchestrator does that work first, in a worker
    thread, on a session of its own (:func:`_load_endpoint_for_probe`).
    """
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

        context = InvocationContext(db=None, endpoint=endpoint, input_data=input_data)
        response = await asyncio.wait_for(create_invoker(context).invoke(), timeout=30.0)

        from rhesis.backend.app.services.invokers.common.schemas import (
            ErrorResponse,
        )

        is_error = isinstance(response, ErrorResponse) or (
            isinstance(response, dict) and response.get("error")
        )

        if is_error:
            # ``output`` over ``message``: a connectivity check is read to find out *why* the
            # endpoint refused, and only ``output`` carries the status line plus the target's
            # own response body. ``message`` stops at "HTTP 401 error from endpoint".
            detail = (
                (response.output or response.message)
                if isinstance(response, ErrorResponse)
                else (response.get("output") or response.get("error"))
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
    db: PreflightDbGate,
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
        model = await db.run(_resolve_purpose_model, user, "evaluation", evaluation_model_id)
        await _verify_model_responds(model)
        model_detail = await db.run(_model_detail, model, evaluation_model_id, user, "evaluation")
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
    db: PreflightDbGate,
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
        model = await db.run(_resolve_purpose_model, user, "execution", execution_model_id)
        await _verify_model_responds(model)
        model_detail = await db.run(_model_detail, model, execution_model_id, user, "execution")
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
    db: PreflightDbGate,
    user: User,
    metrics: List[Metric],
    evaluation_model_id: Optional[str] = None,
) -> PreflightCheckResult:
    """Validate metrics can be instantiated without running full LLM evaluation."""
    check_id = CHECK_METRIC_FUNCTIONALITY

    metric_configs, invalid_results, metric_names = await db.run(_describe_metrics, metrics)

    load_errors: list[str] = []
    loaded_count = 0

    if metric_configs:
        model = await db.run(_resolve_purpose_model, user, "evaluation", evaluation_model_id)
        org_id = str(user.organization_id) if user.organization_id else None

        try:
            metric_tasks = await db.run(_prepare_metrics, metric_configs, model, org_id)
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


def _metric_compatibility_result(
    db: Session,
    endpoint: Endpoint,
    test_set_id: UUID,
    metric_mode: str,
    selected_metrics: Optional[list],
    is_multi_turn: bool,
) -> PreflightCheckResult:
    """Compare the metrics' data requirements against the endpoint's mapping."""
    check_id = CHECK_METRIC_COMPATIBILITY
    metrics = _resolve_check_metrics(
        db, test_set_id, metric_mode, selected_metrics, str(endpoint.organization_id)
    )

    if not metrics:
        return _make_result(
            check_id,
            PreflightCheckStatus.SKIPPED,
            "No metrics to check compatibility for",
        )

    required_scope = MetricScope.MULTI_TURN if is_multi_turn else MetricScope.SINGLE_TURN
    scope_compatible = _scope_compatible_metrics(metrics, is_multi_turn)
    if not scope_compatible:
        return _make_result(
            check_id,
            PreflightCheckStatus.SKIPPED,
            "No scope-compatible metrics to validate",
        )

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
            .filter((Prompt.expected_response.is_(None)) | (Prompt.expected_response == ""))
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
        return _make_result(
            check_id,
            PreflightCheckStatus.WARNING,
            f"{len(issues)} compatibility issue(s) detected",
            "; ".join(issues[:5]),
        )

    metric_names = [m.name for m in scope_compatible if m.name]
    return _make_result(
        check_id,
        PreflightCheckStatus.PASSED,
        f"All {len(scope_compatible)} metric(s) are compatible with endpoint configuration",
        ", ".join(metric_names) if metric_names else None,
    )


async def check_metric_compatibility(
    db: PreflightDbGate,
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
        result = await db.run(
            _metric_compatibility_result,
            endpoint,
            test_set_id,
            metric_mode,
            selected_metrics,
            is_multi_turn,
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


def _metric_functionality_metrics(
    db: Session,
    user: User,
    test_set_id: UUID,
    metric_mode: str,
    selected_metrics: Optional[list],
    is_multi_turn: bool,
):
    """Resolve the metrics to load-test, or the result that ends the check early.

    Returns ``(scope_compatible, early_result)``; exactly one of the two is set.
    """
    check_id = CHECK_METRIC_FUNCTIONALITY
    metrics = _resolve_check_metrics(
        db, test_set_id, metric_mode, selected_metrics, str(user.organization_id)
    )

    if not metrics:
        return None, _make_result(
            check_id,
            PreflightCheckStatus.WARNING,
            "No metrics found for this configuration",
        )

    scope_compatible = _scope_compatible_metrics(metrics, is_multi_turn)
    if not scope_compatible:
        scope_label = (MetricScope.MULTI_TURN if is_multi_turn else MetricScope.SINGLE_TURN).value
        has_class = [m for m in metrics if m.class_name]
        return None, _make_result(
            check_id,
            PreflightCheckStatus.WARNING,
            f"No metrics support {scope_label} scope",
            f"This test set requires {scope_label} "
            f"metrics, but none of the "
            f"{len(has_class)} resolved metric(s) "
            f"include that scope.",
        )

    return scope_compatible, None


async def check_metric_functionality(
    db: PreflightDbGate,
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
        scope_compatible, result = await db.run(
            _metric_functionality_metrics,
            user,
            test_set_id,
            metric_mode,
            selected_metrics,
            is_multi_turn,
        )
        if scope_compatible is not None:
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


def _custom_metric_coverage(db: Session, selected_metrics: Optional[list]) -> PreflightCheckResult:
    check_id = CHECK_REQUIREMENT_METRIC_COVERAGE
    if not selected_metrics:
        return _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "No custom metrics selected",
            "Custom metric mode is active but no metrics were selected.",
        )

    metric_ids = [m.id for m in selected_metrics]
    names = [row[0] for row in db.query(Metric.name).filter(Metric.id.in_(metric_ids)).all()]
    return _make_result(
        check_id,
        PreflightCheckStatus.PASSED,
        f"{len(selected_metrics)} custom metric(s) selected",
        ", ".join(names) if names else None,
    )


def _test_set_metric_coverage(
    db: Session, test_set_id: UUID, organization_id: str
) -> PreflightCheckResult:
    check_id = CHECK_REQUIREMENT_METRIC_COVERAGE
    test_set = get_item_detail(db, TestSet, test_set_id, organization_id=organization_id)
    if not test_set:
        return _make_result(check_id, PreflightCheckStatus.FAILED, "Test set not found")

    if not test_set.metrics:
        return _make_result(
            check_id,
            PreflightCheckStatus.WARNING,
            "Test set has no metrics configured",
            "Add metrics to the test set or switch to requirement metrics.",
        )

    metric_names = [m.name for m in test_set.metrics if m.name]
    return _make_result(
        check_id,
        PreflightCheckStatus.PASSED,
        f"Test set has {len(test_set.metrics)} metric(s)",
        ", ".join(metric_names) if metric_names else None,
    )


def _requirement_metric_coverage(db: Session, test_set_id: UUID) -> PreflightCheckResult:
    check_id = CHECK_REQUIREMENT_METRIC_COVERAGE
    requirement_rows = (
        db.query(Test.requirement_id, Requirement.name)
        .join(
            test_test_set_association,
            Test.id == test_test_set_association.c.test_id,
        )
        .join(Requirement, Requirement.id == Test.requirement_id)
        .filter(test_test_set_association.c.test_set_id == test_set_id)
        .filter(Test.requirement_id.isnot(None))
        .distinct()
        .all()
    )
    requirement_map = {row[0]: row[1] for row in requirement_rows}
    requirement_id_set = set(requirement_map.keys())

    if not requirement_id_set:
        return _make_result(
            check_id,
            PreflightCheckStatus.WARNING,
            "No requirements found in test set",
            "Tests in this set have no associated requirements.",
        )

    requirements_with_metrics = set(
        row[0]
        for row in db.query(requirement_metric_association.c.requirement_id)
        .join(
            Metric,
            Metric.id == requirement_metric_association.c.metric_id,
        )
        .filter(requirement_metric_association.c.requirement_id.in_(requirement_id_set))
        .filter(Metric.class_name.isnot(None))
        .distinct()
        .all()
    )

    missing = requirement_id_set - requirements_with_metrics
    if missing:
        names_list = [requirement_map.get(bid) or str(bid) for bid in missing]
        names_str = ", ".join(names_list[:10])
        if len(names_list) > 10:
            names_str += f" and {len(names_list) - 10} more"
        return _make_result(
            check_id,
            PreflightCheckStatus.WARNING,
            f"{len(missing)} of "
            f"{len(requirement_id_set)} requirement(s)"
            f" missing metric associations",
            f"No metrics assigned to: {names_str}. "
            "Tests linked to these requirements will be "
            "skipped during evaluation.",
        )

    requirement_names = list(requirement_map.values())
    return _make_result(
        check_id,
        PreflightCheckStatus.PASSED,
        f"All {len(requirement_id_set)} requirement(s) have metrics",
        ", ".join(n for n in requirement_names if n) or None,
    )


def _metric_coverage_result(
    db: Session,
    test_set_id: UUID,
    metric_mode: str,
    organization_id: str,
    selected_metrics: Optional[list],
) -> PreflightCheckResult:
    """Whether the configured metric mode actually covers the test set."""
    if metric_mode == "define_custom":
        return _custom_metric_coverage(db, selected_metrics)
    if metric_mode == "use_test_set":
        return _test_set_metric_coverage(db, test_set_id, organization_id)
    return _requirement_metric_coverage(db, test_set_id)


async def check_requirement_metric_coverage(
    db: PreflightDbGate,
    test_set_id: UUID,
    metric_mode: str,
    organization_id: str,
    selected_metrics: Optional[list] = None,
    correlation_id: Optional[str] = None,
    publish: bool = True,
    test_set_name: Optional[str] = None,
) -> PreflightCheckResult:
    check_id = CHECK_REQUIREMENT_METRIC_COVERAGE
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
        result = await db.run(
            _metric_coverage_result,
            test_set_id,
            metric_mode,
            organization_id,
            selected_metrics,
        )
    except Exception as e:
        result = _make_result(
            check_id,
            PreflightCheckStatus.FAILED,
            "Error checking requirement-metric coverage",
            str(e),
        )

    _apply_test_set_fields(result, ts_id_str, test_set_name)
    await _publish_result(result, correlation_id, publish)
    return result
