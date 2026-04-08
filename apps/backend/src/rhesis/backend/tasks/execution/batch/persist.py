"""
Synchronous DB persistence for batch test results.

Runs inside ``asyncio.to_thread()`` — opens a short-lived session,
writes deferred traces, creates the test-result record, and signals
conversation completion for multi-turn tests.
"""

import logging
from typing import Any, Dict

from rhesis.backend.app.models.test import Test
from rhesis.backend.tasks.execution.batch.context import ExecutionContext

logger = logging.getLogger(__name__)


def persist_result(
    ctx: ExecutionContext,
    test_id: str,
    test: Test,
    output: Dict[str, Any],
    metrics_results: Dict[str, Any],
    deferred_traces: list,
    execution_time: float,
    is_multi_turn: bool,
) -> None:
    """Open session, write deferred traces, write test result, link traces."""
    from rhesis.backend.app.database import get_db_with_tenant_variables
    from rhesis.backend.app.services.invokers.tracing import persist_deferred_trace
    from rhesis.backend.tasks.execution.executors.results import create_test_result_record

    with get_db_with_tenant_variables(ctx.organization_id, ctx.user_id or "") as db:
        try:
            for trace_data in deferred_traces:
                persist_deferred_trace(db, trace_data)

            metadata = None
            if ctx.reference_test_run_id:
                metadata = {
                    "source": "rescore",
                    "reference_test_run_id": ctx.reference_test_run_id,
                }

            create_test_result_record(
                db=db,
                test=test,
                test_config_id=str(ctx.test_config.id),
                test_run_id=str(ctx.test_run.id),
                test_id=test_id,
                organization_id=ctx.organization_id,
                user_id=ctx.user_id,
                execution_time=execution_time,
                metrics_results=metrics_results,
                processed_result=output,
                metadata=metadata,
            )

            db.commit()

            if is_multi_turn and deferred_traces:
                _signal_conversation_complete(ctx, deferred_traces)
        except Exception:
            db.rollback()
            raise


def _signal_conversation_complete(ctx: ExecutionContext, deferred_traces: list) -> None:
    """Notify the trace-metrics cache that a conversation is done."""
    try:
        trace_id = deferred_traces[0].trace_id
        project_id = str(ctx.endpoint.project_id) if ctx.endpoint.project_id else None

        if trace_id and project_id:
            from rhesis.backend.app.services.telemetry.trace_metrics_cache import (
                signal_conversation_complete,
            )

            signal_conversation_complete(trace_id, project_id, ctx.organization_id)
            logger.info(f"[BATCH] Signaled conversation complete for trace {trace_id}")
    except Exception as e:
        logger.warning(f"[BATCH] Failed to signal conversation complete: {e}")
