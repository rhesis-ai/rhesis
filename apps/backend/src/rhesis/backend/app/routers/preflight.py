"""Preflight check router for validating test execution environment."""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import TestSetType
from rhesis.backend.app.dependencies import get_tenant_db_session
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.preflight import (
    PreflightCheckInfo,
    PreflightCheckRequest,
    PreflightCheckResponse,
    PreflightMode,
    PreflightSyncResponse,
)
from rhesis.backend.app.services.preflight import (
    CHECK_BEHAVIOR_METRIC_COVERAGE,
    CHECK_ENDPOINT_CONNECTIVITY,
    CHECK_EVALUATION_MODEL,
    CHECK_EXECUTION_MODEL,
    CHECK_METRIC_FUNCTIONALITY,
    CHECK_TEST_SET_NOT_EMPTY,
    LABELS,
    compute_summary,
    run_preflight_checks_multi,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preflight-checks", tags=["preflight"])


def _is_multi_turn(test_set: TestSet) -> bool:
    if not test_set.test_set_type:
        return False
    try:
        type_value = getattr(test_set.test_set_type, "type_value", None)
        if not type_value:
            return False
        return TestSetType.from_string(type_value) == TestSetType.MULTI_TURN
    except (ValueError, AttributeError):
        return False


def _determine_applicable_checks(
    scoring_target: str,
    test_sets: list[tuple[str, str, bool]],
) -> list[PreflightCheckInfo]:
    """Build the list of checks with composite keys for multi-test-set.

    Args:
        scoring_target: "fresh" or "reuse"
        test_sets: list of (test_set_id_str, test_set_name, is_multi_turn)
    """
    checks = []
    any_multi_turn = any(mt for _, _, mt in test_sets)
    multi = len(test_sets) > 1

    # --- Shared checks (no test_set_id) ---
    checks.append(
        PreflightCheckInfo(
            check_id=CHECK_ENDPOINT_CONNECTIVITY,
            label=LABELS[CHECK_ENDPOINT_CONNECTIVITY],
            applicable=scoring_target == "fresh",
        )
    )
    checks.append(
        PreflightCheckInfo(
            check_id=CHECK_EVALUATION_MODEL,
            label=LABELS[CHECK_EVALUATION_MODEL],
            applicable=True,
        )
    )
    if any_multi_turn:
        checks.append(
            PreflightCheckInfo(
                check_id=CHECK_EXECUTION_MODEL,
                label=LABELS[CHECK_EXECUTION_MODEL],
                applicable=True,
            )
        )

    # --- Per-test-set checks ---
    for ts_id_str, ts_name, _ in test_sets:
        for check_id in [
            CHECK_TEST_SET_NOT_EMPTY,
            CHECK_BEHAVIOR_METRIC_COVERAGE,
            CHECK_METRIC_FUNCTIONALITY,
        ]:
            composite_key = (
                f"{check_id}:{ts_id_str}" if multi else check_id
            )
            checks.append(
                PreflightCheckInfo(
                    check_id=check_id,
                    label=LABELS[check_id],
                    applicable=True,
                    test_set_id=ts_id_str if multi else None,
                    test_set_name=ts_name if multi else None,
                    composite_key=composite_key,
                )
            )

    return checks


async def _run_preflight_background(
    organization_id: str,
    user_id: str,
    request: PreflightCheckRequest,
    correlation_id: str,
    test_sets: list[tuple[uuid.UUID, str, bool]],
) -> None:
    """Run preflight checks in a background task with its own DB session."""
    from rhesis.backend.app.database import get_db_with_tenant_variables

    try:
        with get_db_with_tenant_variables(organization_id, user_id) as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(
                    f"Preflight background task: user {user_id} not found"
                )
                return

            await run_preflight_checks_multi(
                db=db,
                user=user,
                test_sets=test_sets,
                endpoint_id=request.endpoint_id,
                scoring_target=request.scoring_target,
                metric_mode=request.metric_mode,
                selected_metrics=request.selected_metrics,
                execution_model_id=request.execution_model_id,
                evaluation_model_id=request.evaluation_model_id,
                correlation_id=correlation_id,
                publish=True,
            )
    except Exception:
        logger.exception("Preflight background task failed")


@router.post("")
async def run_preflight(
    request: PreflightCheckRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    # Query all requested test sets
    db_test_sets = (
        db.query(TestSet)
        .filter(TestSet.id.in_(request.test_set_ids))
        .all()
    )

    found_ids = {ts.id for ts in db_test_sets}
    missing = [
        str(tid) for tid in request.test_set_ids if tid not in found_ids
    ]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Test set(s) not found: {', '.join(missing)}",
        )

    # Build (id, name, is_multi_turn) tuples preserving request order
    ts_by_id = {ts.id: ts for ts in db_test_sets}
    test_sets: list[tuple[uuid.UUID, str, bool]] = [
        (tid, ts_by_id[tid].name or str(tid), _is_multi_turn(ts_by_id[tid]))
        for tid in request.test_set_ids
    ]

    if request.mode == PreflightMode.SYNC:
        results = await run_preflight_checks_multi(
            db=db,
            user=current_user,
            test_sets=test_sets,
            endpoint_id=request.endpoint_id,
            scoring_target=request.scoring_target,
            metric_mode=request.metric_mode,
            selected_metrics=request.selected_metrics,
            execution_model_id=request.execution_model_id,
            evaluation_model_id=request.evaluation_model_id,
            correlation_id=None,
            publish=False,
        )
        summary, passed, failed, warnings, skipped = compute_summary(results)
        return PreflightSyncResponse(
            checks=results,
            summary=summary,
            passed=passed,
            failed=failed,
            warnings=warnings,
            skipped=skipped,
        )

    # Async mode: return 202 immediately, run checks in background
    correlation_id = request.correlation_id or str(uuid.uuid4())

    ts_strs = [
        (str(tid), name, mt) for tid, name, mt in test_sets
    ]
    checks = _determine_applicable_checks(request.scoring_target, ts_strs)

    asyncio.create_task(
        _run_preflight_background(
            organization_id=str(current_user.organization_id),
            user_id=str(current_user.id),
            request=request,
            correlation_id=correlation_id,
            test_sets=test_sets,
        )
    )

    return JSONResponse(
        status_code=202,
        content=PreflightCheckResponse(
            correlation_id=correlation_id,
            checks=checks,
        ).model_dump(),
    )
