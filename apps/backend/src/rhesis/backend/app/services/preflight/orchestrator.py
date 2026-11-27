"""Preflight check orchestration — runs checks and publishes results."""

import asyncio
import logging
from typing import Awaitable, List, Optional
from uuid import UUID

import anyio
from sqlalchemy.orm import Session

from rhesis.backend.app.database import scope_project_id
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointConnectionType
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.preflight import PreflightCheckResult, PreflightCheckStatus
from rhesis.backend.app.schemas.websocket import ChannelTarget, EventType, WebSocketMessage
from rhesis.backend.app.services.invokers.auth import AuthenticationManager
from rhesis.backend.app.services.preflight.checks import (
    _resolve_check_metrics,
    check_endpoint_connectivity,
    check_evaluation_model,
    check_execution_model,
    check_metric_compatibility,
    check_metric_functionality,
    check_requirement_metric_coverage,
    check_test_set_not_empty,
)
from rhesis.backend.app.services.preflight.constants import (
    CHECK_ENDPOINT_CONNECTIVITY,
    CHECK_EVALUATION_MODEL,
    CHECK_EXECUTION_MODEL,
    CHECK_METRIC_COMPATIBILITY,
    CHECK_METRIC_FUNCTIONALITY,
    CHECK_REQUIREMENT_METRIC_COVERAGE,
    CHECK_TEST_SET_NOT_EMPTY,
    LABELS,
)
from rhesis.backend.app.services.preflight.utils import (
    PreflightDbGate,
    _apply_test_set_fields,
    _make_composite_key,
    _make_result,
    _publish_result,
)
from rhesis.backend.app.services.run_models import RunModelNeeds, metric_backends, model_needs
from rhesis.backend.app.utils.crud_utils import get_item_detail
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException

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


def _load_endpoint_or_raise(db: Session, endpoint_id: UUID, organization_id: str):
    """Look the endpoint up, letting ItemDeletedException through to the caller."""
    return get_item_detail(db, Endpoint, endpoint_id, organization_id=organization_id)


def _test_set_name(db: Session, test_set_id: UUID) -> str:
    test_set = db.query(TestSet).filter(TestSet.id == test_set_id).first()
    return test_set.name if test_set else str(test_set_id)


def _load_endpoint(db: Session, endpoint_id: UUID, organization_id: str) -> Optional[Endpoint]:
    """Look the endpoint up, reporting a soft-deleted one the same as a missing one."""
    try:
        return _load_endpoint_or_raise(db, endpoint_id, organization_id)
    except ItemDeletedException:
        return None


def _load_endpoint_for_probe(
    db: Session, endpoint_id: UUID, organization_id: str
) -> Optional[Endpoint]:
    """Everything the connectivity probe needs from the database, in one thread hop.

    The load, and the auth token: a client-credentials endpoint with an expired token
    refreshes it with a blocking HTTP POST and writes the new one back to the
    row. Done here, both stay in the worker thread; done inside the awaited probe, both
    would run on the event loop.
    """
    endpoint = _load_endpoint(db, endpoint_id, organization_id)
    if endpoint is not None:
        AuthenticationManager.prefetch_token(db, endpoint)
        if endpoint.connection_type == EndpointConnectionType.SDK.value:
            # The SDK check reads it; loading it lazily there would hit the DB on the loop.
            _ = endpoint.status
    return endpoint


async def _connectivity_branch(
    db: PreflightDbGate,
    endpoint_id: UUID,
    organization_id: str,
    correlation_id: Optional[str],
    publish: bool,
) -> PreflightCheckResult:
    """Run the connectivity check on a session of its own.

    The run's shared session is only safe one caller at a time and this branch runs
    concurrently with the others, so the endpoint is loaded -- and its token refreshed
    -- in a second session, in a worker thread. The probe itself then runs with no
    session at all; see :func:`check_endpoint_connectivity`. The session stays open
    around it so the ORM object keeps its loaded state, and its close commits the
    refreshed token off the loop.
    """
    try:
        async with db.spawn_session() as check_db:
            endpoint = await anyio.to_thread.run_sync(
                _load_endpoint_for_probe, check_db, endpoint_id, organization_id
            )
            if endpoint is None:
                result = _make_result(
                    CHECK_ENDPOINT_CONNECTIVITY,
                    PreflightCheckStatus.FAILED,
                    "Endpoint not found",
                )
            else:
                return await check_endpoint_connectivity(endpoint, correlation_id, publish)
    except Exception as e:
        # Matches what check_endpoint_connectivity reports for its own failures, so
        # opening the session cannot turn into a differently-worded result.
        result = _make_result(
            CHECK_ENDPOINT_CONNECTIVITY,
            PreflightCheckStatus.FAILED,
            "Unexpected error during connectivity check",
            str(e),
        )

    _apply_test_set_fields(result)
    await _publish_result(result, correlation_id, publish)
    return result


def _resolve_run_metrics(
    db: Session,
    test_set_ids: list[UUID],
    metric_mode: str,
    selected_metrics: Optional[list],
    organization_id: str,
):
    """Each test set's metrics, and the backends among them that judge with a model."""
    by_test_set = {
        ts_id: _resolve_check_metrics(db, ts_id, metric_mode, selected_metrics, organization_id)
        for ts_id in test_set_ids
    }
    all_metrics = [m for metrics in by_test_set.values() for m in metrics]
    return by_test_set, metric_backends(db, all_metrics)


async def _run_model_needs(
    db: PreflightDbGate,
    test_sets: list[tuple[UUID, str, bool]],
    metric_mode: str,
    selected_metrics: Optional[list],
    organization_id: str,
    replay: bool,
):
    """The models this run needs, by the rule the execute route uses.

    Returns ``(needs, metrics_by_test_set)``. If the metrics can't be resolved, both
    model checks run as before, so preflight never checks less than it used to.
    """
    any_multi_turn = any(mt for _, _, mt in test_sets)
    try:
        by_test_set, backends = await db.run(
            _resolve_run_metrics,
            [ts_id for ts_id, _, _ in test_sets],
            metric_mode,
            selected_metrics,
            organization_id,
        )
    except Exception as e:
        logger.warning(f"Could not resolve preflight metrics, checking both models: {e}")
        return RunModelNeeds(evaluation=True, execution=any_multi_turn), {}
    return model_needs(backends, any_multi_turn, replay), by_test_set


async def _skipped_model_check(
    check_id: str, message: str, correlation_id: Optional[str], publish: bool
) -> PreflightCheckResult:
    result = _make_result(check_id, PreflightCheckStatus.SKIPPED, message)
    _apply_test_set_fields(result)
    await _publish_result(result, correlation_id, publish)
    return result


async def _model_checks(
    db: PreflightDbGate,
    user: User,
    needs: RunModelNeeds,
    any_multi_turn: bool,
    scoring_target: str,
    execution_model_id: Optional[str],
    evaluation_model_id: Optional[str],
    correlation_id: Optional[str],
    publish: bool,
):
    """The evaluation and execution model checks: ``(tasks, skipped_results)``."""
    tasks: list[tuple[str, Awaitable[PreflightCheckResult]]] = []
    skipped: List[PreflightCheckResult] = []

    if needs.evaluation:
        evaluation_check = check_evaluation_model(
            db,
            user,
            evaluation_model_id,
            correlation_id,
            publish,
            # Only a fresh run interprets; a re-score reads the stored contract.
            probe_interpretation=any_multi_turn and scoring_target == "fresh",
        )
        tasks.append((CHECK_EVALUATION_MODEL, evaluation_check))
    else:
        skipped.append(
            await _skipped_model_check(
                CHECK_EVALUATION_MODEL,
                "Not needed: no metric in this run is judged by the evaluation model",
                correlation_id,
                publish,
            )
        )

    # Shown only for multi-turn runs, as before.
    if needs.execution:
        execution_check = check_execution_model(
            db, user, execution_model_id, correlation_id, publish
        )
        tasks.append((CHECK_EXECUTION_MODEL, execution_check))
    elif any_multi_turn:
        skipped.append(
            await _skipped_model_check(
                CHECK_EXECUTION_MODEL,
                "Not needed: a re-score reuses the stored conversations",
                correlation_id,
                publish,
            )
        )
    return tasks, skipped


async def run_preflight_checks_multi(
    db: Session,
    user: User,
    test_sets: list[tuple[UUID, str, bool]],
    endpoint_id: UUID,
    scoring_target: str = "fresh",
    metric_mode: str = "use_requirement",
    selected_metrics: Optional[list] = None,
    execution_model_id: Optional[str] = None,
    evaluation_model_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    publish: bool = True,
) -> List[PreflightCheckResult]:
    """Run preflight checks for one or more test sets.

    Shared checks (endpoint, models) run once.
    Per-test-set checks run for each test set.

    ``db`` is only ever touched inside ``anyio.to_thread.run_sync`` (see
    :class:`~rhesis.backend.app.services.preflight.utils.PreflightDbGate`), so an
    ``async def`` caller can hand over its request session.
    """
    results: List[PreflightCheckResult] = []
    tasks: list[tuple[str, asyncio.Task]] = []
    multi = len(test_sets) > 1
    ts_name_map: dict[str, str] = (
        {str(ts_id): ts_name for ts_id, ts_name, _ in test_sets} if multi else {}
    )

    organization_id = str(user.organization_id)
    # Every query below runs through this: in a worker thread, one at a time.
    off_loop = PreflightDbGate(db, organization_id, str(user.id), scope_project_id(db))

    try:
        endpoint = await off_loop.run(_load_endpoint_or_raise, endpoint_id, organization_id)
        endpoint_status = "not found"
    except ItemDeletedException:
        endpoint = None
        endpoint_status = "has been deleted"
    any_multi_turn = any(mt for _, _, mt in test_sets)

    # --- Shared checks ---

    # Endpoint connectivity
    if scoring_target == "fresh":
        if endpoint:
            tasks.append(
                (
                    CHECK_ENDPOINT_CONNECTIVITY,
                    _connectivity_branch(
                        off_loop, endpoint_id, organization_id, correlation_id, publish
                    ),
                )
            )
        else:
            r = _make_result(
                CHECK_ENDPOINT_CONNECTIVITY,
                PreflightCheckStatus.FAILED,
                f"Endpoint {endpoint_status}",
            )
            _apply_test_set_fields(r)
            results.append(r)
            await _publish_result(r, correlation_id, publish)
    else:
        if not endpoint:
            r = _make_result(
                CHECK_ENDPOINT_CONNECTIVITY,
                PreflightCheckStatus.FAILED,
                f"Endpoint {endpoint_status}",
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

    # Evaluation and execution models, only the ones the run will build
    needs, metrics_by_test_set = await _run_model_needs(
        off_loop,
        test_sets,
        metric_mode,
        selected_metrics,
        organization_id,
        replay=scoring_target != "fresh",
    )
    model_tasks, skipped_models = await _model_checks(
        off_loop,
        user,
        needs,
        any_multi_turn,
        scoring_target,
        execution_model_id,
        evaluation_model_id,
        correlation_id,
        publish,
    )
    tasks.extend(model_tasks)
    results.extend(skipped_models)

    # --- Per-test-set checks ---
    for ts_id, ts_name, is_mt in test_sets:
        ts_id_str = str(ts_id) if multi else None
        ts_label = ts_name if multi else None

        tasks.append(
            (
                _make_composite_key(CHECK_TEST_SET_NOT_EMPTY, ts_id_str),
                check_test_set_not_empty(
                    off_loop,
                    ts_id,
                    correlation_id,
                    publish,
                    test_set_name=ts_label,
                ),
            )
        )

        tasks.append(
            (
                _make_composite_key(CHECK_REQUIREMENT_METRIC_COVERAGE, ts_id_str),
                check_requirement_metric_coverage(
                    off_loop,
                    ts_id,
                    metric_mode,
                    organization_id,
                    selected_metrics,
                    correlation_id,
                    publish,
                    test_set_name=ts_label,
                ),
            )
        )

        if endpoint:
            tasks.append(
                (
                    _make_composite_key(CHECK_METRIC_COMPATIBILITY, ts_id_str),
                    check_metric_compatibility(
                        off_loop,
                        endpoint,
                        ts_id,
                        metric_mode,
                        selected_metrics,
                        is_mt,
                        correlation_id,
                        publish,
                        test_set_name=ts_label,
                    ),
                )
            )
        else:
            r = _make_result(
                CHECK_METRIC_COMPATIBILITY,
                PreflightCheckStatus.SKIPPED,
                "Metric compatibility check skipped: endpoint not found",
            )
            _apply_test_set_fields(r, ts_id_str, ts_label)
            results.append(r)
            await _publish_result(r, correlation_id, publish)

        tasks.append(
            (
                _make_composite_key(CHECK_METRIC_FUNCTIONALITY, ts_id_str),
                check_metric_functionality(
                    off_loop,
                    user,
                    ts_id,
                    metric_mode,
                    selected_metrics,
                    is_mt,
                    evaluation_model_id,
                    correlation_id,
                    publish,
                    test_set_name=ts_label,
                    endpoint=endpoint,
                    resolved_metrics=metrics_by_test_set.get(ts_id),
                ),
            )
        )

    # Run all concurrently
    if tasks:
        check_keys = [k for k, _ in tasks]
        coros = [coro for _, coro in tasks]
        task_results = await asyncio.gather(*coros, return_exceptions=True)
        for comp_key, tr in zip(check_keys, task_results, strict=True):
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
    metric_mode: str = "use_requirement",
    selected_metrics: Optional[list] = None,
    execution_model_id: Optional[str] = None,
    evaluation_model_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    is_multi_turn: bool = False,
    publish: bool = True,
) -> List[PreflightCheckResult]:
    """Run preflight checks for a single test set (backward compat)."""
    ts_name = await anyio.to_thread.run_sync(_test_set_name, db, test_set_id)
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
