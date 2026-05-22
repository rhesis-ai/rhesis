"""Preflight check orchestration — runs checks and publishes results."""

import asyncio
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.preflight import PreflightCheckResult, PreflightCheckStatus
from rhesis.backend.app.schemas.websocket import ChannelTarget, EventType, WebSocketMessage

from .checks import (
    check_behavior_metric_coverage,
    check_endpoint_connectivity,
    check_evaluation_model,
    check_execution_model,
    check_metric_functionality,
    check_test_set_not_empty,
)
from .constants import (
    CHECK_BEHAVIOR_METRIC_COVERAGE,
    CHECK_ENDPOINT_CONNECTIVITY,
    CHECK_EVALUATION_MODEL,
    CHECK_EXECUTION_MODEL,
    CHECK_METRIC_FUNCTIONALITY,
    CHECK_TEST_SET_NOT_EMPTY,
    LABELS,
)
from .utils import _apply_test_set_fields, _make_composite_key, _make_result, _publish_result

logger = logging.getLogger(__name__)


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
