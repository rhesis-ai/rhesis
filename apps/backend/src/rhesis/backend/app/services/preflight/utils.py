"""Preflight check utility functions."""

import asyncio
from typing import Optional

from rhesis.backend.app.schemas.preflight import PreflightCheckResult, PreflightCheckStatus
from rhesis.backend.app.schemas.websocket import ChannelTarget, EventType, WebSocketMessage

from .constants import LABELS, PER_TEST_SET_CHECKS


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
