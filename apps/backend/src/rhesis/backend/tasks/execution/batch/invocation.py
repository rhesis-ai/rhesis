"""
Test invocation for batch tests (single-turn and multi-turn).
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from rhesis.backend.app.models.test import Test
from rhesis.backend.tasks.execution.batch.context import ExecutionContext

logger = logging.getLogger(__name__)


def is_multi_turn_test(test: Optional[Test]) -> bool:
    """Check if a test is multi-turn."""
    if test is None:
        return False
    from rhesis.backend.tasks.enums import TestType
    from rhesis.backend.tasks.execution.modes import get_test_type

    return get_test_type(test) == TestType.MULTI_TURN


async def load_input_files_lazy(
    ctx: ExecutionContext, test_id: str
) -> Optional[List]:
    """Load input files on demand (inside the semaphore) to avoid holding all
    base64-encoded attachments in memory for the full batch duration."""
    cached = ctx.input_files.get(test_id)
    if cached is not None:
        return cached

    def _load():
        from rhesis.backend.app.database import get_db_with_tenant_variables
        from rhesis.backend.tasks.execution.executors.output_providers import (
            SingleTurnOutput,
        )

        with get_db_with_tenant_variables(ctx.organization_id, ctx.user_id or "") as db:
            return SingleTurnOutput._load_input_files(db, test_id, ctx.organization_id)

    try:
        files = await asyncio.to_thread(_load)
        if files:
            ctx.input_files[test_id] = files
            return files
    except Exception as e:
        logger.warning(f"[BATCH] Failed to load input files for {test_id}: {e}")
    return None


async def run_test(
    ctx: ExecutionContext,
    test: Test,
    test_id: str,
    prompt_content: str,
    test_execution_context: Dict[str, str],
    is_multi_turn: bool,
    deferred_traces: list,
    penelope_agent: Any = None,
) -> Dict[str, Any]:
    """Run a single test (endpoint invocation or Penelope conversation)."""
    if is_multi_turn:
        return await _run_multi_turn(
            ctx, test, test_id, test_execution_context,
            deferred_traces, penelope_agent,
        )
    return await _run_single_turn(
        ctx, test_id, prompt_content, test_execution_context, deferred_traces,
    )


async def _run_multi_turn(
    ctx: ExecutionContext,
    test: Test,
    test_id: str,
    test_execution_context: Dict[str, str],
    deferred_traces: list,
    penelope_agent: Any,
) -> Dict[str, Any]:
    from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget

    test_config_data = test.test_configuration or {}
    goal = test_config_data.get("goal")
    instructions = test_config_data.get("instructions")
    scenario = test_config_data.get("scenario")
    restrictions = test_config_data.get("restrictions")
    context = test_config_data.get("context")
    max_turns = test_config_data.get("max_turns") or 10
    min_turns = test_config_data.get("min_turns")

    input_files = await load_input_files_lazy(ctx, test_id)

    target = BackendEndpointTarget(
        endpoint_id=str(ctx.endpoint.id),
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        test_execution_context=test_execution_context,
        endpoint=ctx.endpoint,
        invoke_max_attempts=ctx.invoke_max_attempts,
        invoke_retry_min_wait=ctx.invoke_retry_min_wait,
        invoke_retry_max_wait=ctx.invoke_retry_max_wait,
    )

    penelope_result = await penelope_agent.a_execute_test(
        target=target,
        goal=goal,
        instructions=instructions,
        scenario=scenario,
        restrictions=restrictions,
        context=context,
        max_turns=max_turns,
        min_turns=min_turns,
        files=input_files if input_files else None,
    )

    deferred_traces.extend(target._deferred_traces)

    trace = penelope_result.model_dump(mode="json")
    penelope_metrics = trace.pop("metrics", {})

    return {
        "output": trace,
        "penelope_metrics": penelope_metrics,
        "deferred_traces": deferred_traces,
    }


async def _run_single_turn(
    ctx: ExecutionContext,
    test_id: str,
    prompt_content: str,
    test_execution_context: Dict[str, str],
    deferred_traces: list,
) -> Dict[str, Any]:
    from rhesis.backend.app.dependencies import get_endpoint_service
    from rhesis.backend.tasks.execution.batch.retry import invoke_with_retry
    from rhesis.backend.tasks.execution.executors.results import process_endpoint_result

    input_data: Dict[str, Any] = {"input": prompt_content}

    input_files = await load_input_files_lazy(ctx, test_id)
    if input_files:
        input_data["files"] = input_files

    endpoint_service = get_endpoint_service()

    async def _invoke():
        return await endpoint_service.invoke_endpoint(
            db=None,
            endpoint_id=str(ctx.endpoint.id),
            input_data=input_data,
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            test_execution_context=test_execution_context,
            endpoint=ctx.endpoint,
            deferred_trace=True,
        )

    result = await invoke_with_retry(
        _invoke,
        max_attempts=ctx.invoke_max_attempts,
        min_wait=ctx.invoke_retry_min_wait,
        max_wait=ctx.invoke_retry_max_wait,
        label=f"single_turn[{test_id[:8]}]",
    )

    deferred_trace = result.pop("_deferred_trace", None) if isinstance(result, dict) else None
    if deferred_trace:
        deferred_traces.append(deferred_trace)

    processed = process_endpoint_result(result)

    return {
        "output": processed,
        "penelope_metrics": {},
        "deferred_traces": deferred_traces,
    }
