"""
Async batch runner — semaphore-gated concurrent test execution.

Contains the ``asyncio.gather``-based runner and the per-test coroutine.
Delegates to `invocation.py` and `evaluation.py`.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List

from rhesis.backend.app.services.test_run_timing import TestPhase
from rhesis.backend.app.utils.response_extractor import has_http_error_in_result
from rhesis.backend.jobs.execution.batch.context import ExecutionContext
from rhesis.backend.jobs.execution.batch.evaluation import evaluate_metrics
from rhesis.backend.jobs.execution.batch.invocation import is_multi_turn_test, run_test
from rhesis.backend.jobs.execution.shared import is_task_revoked

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cancellation watchdog
# ---------------------------------------------------------------------------


async def _cancellation_watchdog(
    task_id: str | None,
    tasks: List[asyncio.Task],
    poll_interval: float = 1.0,
) -> None:
    """Poll the Celery revoke set and cancel all batch tasks when triggered.

    Runs as a sibling asyncio Task alongside the test fan-out.  When the
    Celery task is revoked, each test Task receives a CancelledError at its
    next await point (i.e. mid HTTP call, mid metric evaluation, etc.).
    The watchdog exits as soon as it fires or is itself cancelled by run_batch
    after the tests finish naturally.
    """
    while True:
        await asyncio.sleep(poll_interval)
        if is_task_revoked(task_id):
            pending = [t for t in tasks if not t.done()]
            logger.info(f"[BATCH] Revoke detected — cancelling {len(pending)} in-flight tasks")
            for t in pending:
                t.cancel()
            return


# ---------------------------------------------------------------------------
# Recovery pass helpers
# ---------------------------------------------------------------------------


def _is_retriable_failure(result: Dict[str, Any]) -> bool:
    """Return True for transient failures that are worth retrying.

    Excluded from retries:
    - ``cancelled``  — deliberately stopped, don't re-invoke
    - ``skipped``    — idempotency guard, no-op on retry
    - ``succeeded``  — already done
    - Timeout        — the endpoint was too slow; a retry will likely timeout again
    - Missing data   — pre-fetch issue, won't resolve on retry
    """
    if result.get("status") != "failed":
        return False
    error = result.get("error", "")
    if error.startswith("Timeout after") or error.startswith("Test data not pre-fetched"):
        return False
    return True


async def _run_gather(
    ctx: ExecutionContext,
    test_ids: List[str],
    semaphore: asyncio.Semaphore,
    penelope_agent: Any,
    evaluator: Any,
    on_progress: Any = None,
    progress_base: int = 0,
    progress_total: int = 0,
    on_emit: Any = None,
    on_test_phase: Any = None,
) -> List[Dict[str, Any]]:
    """Fan out test_ids as asyncio Tasks and gather results."""
    completed_count = 0
    last_emit_time = time.monotonic()
    # At most ~20 progress lines per batch, or one every 2s, whichever comes
    # first, plus always the last one. Emitting every single test completion
    # was producing ~4,000 ActivityLogged events (each opening a DB session)
    # for a single 4,000-test run.
    emit_interval = max(1, progress_total // 20) if progress_total else 1

    async def _tracked(test_id: str) -> Dict[str, Any]:
        nonlocal completed_count, last_emit_time
        td = ctx.test_data.get(test_id)
        test_obj = td.get("test") if td else None
        cat_obj = getattr(test_obj, "category", None)
        category = getattr(cat_obj, "name", None) or ""
        status = "failed"
        result: Dict[str, Any] = {}
        try:
            result = await _execute_single_test(
                ctx,
                test_id,
                semaphore,
                penelope_agent,
                evaluator,
                on_emit=on_emit,
                on_test_phase=on_test_phase,
            )
            status = result.get("status", "completed")
            return result
        finally:
            completed_count += 1
            current = progress_base + completed_count
            if on_progress and progress_total:
                try:
                    on_progress(current, progress_total)
                except Exception:
                    pass
            if on_emit and progress_total:
                now = time.monotonic()
                # Failures are never throttled -- they carry the error text,
                # which is the whole reason to read the activity log, and
                # they are rare enough not to reintroduce the volume problem.
                if (
                    status == "failed"
                    or current % emit_interval == 0
                    or current == progress_total
                    or now - last_emit_time > 2.0
                ):
                    try:
                        label = f" — {category}" if category else ""
                        error = result.get("error", "") if isinstance(result, dict) else ""
                        suffix = f": {error}" if error and status == "failed" else ""
                        on_emit(f"Test {current}/{progress_total} {status}{label}{suffix}")
                        last_emit_time = now
                    except Exception:
                        pass

    tasks = [asyncio.create_task(_tracked(test_id)) for test_id in test_ids]
    watchdog = asyncio.create_task(_cancellation_watchdog(ctx.celery_task_id, tasks))
    try:
        raw = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        watchdog.cancel()
        await asyncio.gather(watchdog, return_exceptions=True)

    results: List[Dict[str, Any]] = []
    for test_id, result in zip(test_ids, raw):
        if isinstance(result, asyncio.CancelledError):
            logger.info(f"[BATCH] Test {test_id} cancelled mid-flight")
            results.append({"test_id": test_id, "status": "cancelled", "execution_time": 0})
        elif isinstance(result, Exception):
            logger.error(f"[BATCH] Test {test_id} raised exception: {result}")
            results.append(
                {
                    "test_id": test_id,
                    "status": "failed",
                    "error": str(result),
                    "execution_time": 0,
                    "exception_type": type(result).__name__,
                }
            )
        else:
            results.append(result)
    return results


# ---------------------------------------------------------------------------
# Top-level batch runner
# ---------------------------------------------------------------------------


async def run_batch(
    ctx: ExecutionContext,
    test_ids: List[str],
    on_progress: Any = None,
    on_emit: Any = None,
    on_test_phase: Any = None,
) -> List[Dict[str, Any]]:
    """Async entry point: run all tests with semaphore-gated concurrency.

    After the main pass, up to ``ctx.recovery_rounds`` additional passes are run
    for tests whose failure looks transient (network errors, unexpected
    exceptions, persist failures).  Timeouts and cancellations are not retried.
    """
    semaphore = asyncio.Semaphore(ctx.batch_concurrency)

    # Create a single PenelopeAgent for the batch (model + metrics are shared;
    # per-test state is created fresh inside a_execute_test).
    penelope_agent = None
    has_multi_turn = any(
        is_multi_turn_test(ctx.test_data.get(tid, {}).get("test")) for tid in test_ids
    )
    if has_multi_turn:
        from rhesis.backend.app.utils.usage_tracking import stamp_usage_provenance
        from rhesis.backend.app.utils.user_model_utils import ensure_language_model
        from rhesis.penelope import PenelopeAgent

        # Penelope is a separate package and cannot stamp usage provenance
        # itself, so both branches have to be handled from this side:
        #   - a model we resolved: already stamped by resolve_model, and
        #     ensure_language_model keeps the guarantee if a bare provider
        #     string ever reaches here, since PenelopeAgent's own string
        #     branch is an unstamped get_model.
        #   - Penelope's own default: stamp the instance it built. It runs on
        #     this deployment's credentials, exactly like any other default.
        # Together these mean no model reaches an LLM call unstamped, which
        # is what lets accrue_model_tokens treat "unstamped" as a plain bug.
        penelope_agent = (
            PenelopeAgent(model=ensure_language_model(ctx.execution_model))
            if ctx.execution_model
            else PenelopeAgent()
        )
        stamp_usage_provenance(penelope_agent.model, metered=True)

        # Fetch credentials / tokens once before the concurrent fan-out so
        # all coroutines hit a warm cache rather than racing to fetch in parallel.
        await penelope_agent.model.warmup()

    # Create a single MetricEvaluator for the batch (stateless, safe to share).
    evaluator = None
    if ctx.has_metrics:
        from rhesis.backend.metrics.evaluator import MetricEvaluator

        evaluator = MetricEvaluator(
            model=ctx.evaluation_model,
            connector_metric_sender=ctx.connector_metric_sender,
            # No `db` here on purpose: the session closed before this point. Judge
            # models for per-metric `model_id` overrides were resolved in prefetch.
            metric_models=ctx.metric_models,
        )

    # Snapshot test data before the main pass so recovery rounds can restore it
    # for tests whose data was popped in the finally block of _execute_single_test.
    # Also stored on ctx so execute_tests_as_batch can persist error records for
    # tests that fail without ever writing a DB row.
    test_data_snapshot = dict(ctx.test_data)
    ctx.test_data_snapshot = test_data_snapshot

    # --- Main pass ---
    total = len(test_ids)
    results = await _run_gather(
        ctx,
        test_ids,
        semaphore,
        penelope_agent,
        evaluator,
        on_progress=on_progress,
        progress_base=0,
        progress_total=total,
        on_emit=on_emit,
        on_test_phase=on_test_phase,
    )

    # --- Recovery pass passes ---
    if ctx.recovery_rounds > 0:
        result_map: Dict[str, Dict[str, Any]] = {r["test_id"]: r for r in results}

        for recovery_round in range(ctx.recovery_rounds):
            retry_ids = [tid for tid in test_ids if _is_retriable_failure(result_map.get(tid, {}))]
            if not retry_ids:
                break

            logger.info(
                f"[BATCH] Recovery pass {recovery_round + 1}/{ctx.recovery_rounds}: "
                f"retrying {len(retry_ids)} failed test(s): {retry_ids}"
            )

            # Restore pre-fetched data so _execute_single_test can run again.
            for tid in retry_ids:
                if tid in test_data_snapshot:
                    ctx.test_data[tid] = test_data_snapshot[tid]
                else:
                    logger.warning(f"[BATCH] Recovery pass: no snapshot data for {tid}, skipping")
                    retry_ids = [t for t in retry_ids if t != tid]

            # on_test_phase is threaded through here (unlike on_progress /
            # on_emit, which would double-count against progress_total) so
            # the live grid keeps ticking through recovery instead of
            # freezing on the last main-pass state.
            recovery_results = await _run_gather(
                ctx,
                retry_ids,
                semaphore,
                penelope_agent,
                evaluator,
                on_test_phase=on_test_phase,
            )

            recovered = 0
            for recovery_result in recovery_results:
                tid = recovery_result["test_id"]
                prev_status = result_map.get(tid, {}).get("status")
                result_map[tid] = recovery_result
                if recovery_result.get("status") == "succeeded":
                    recovered += 1
                    logger.info(f"[BATCH] Recovery pass recovered test {tid} (was: {prev_status})")
                else:
                    logger.warning(
                        f"[BATCH] Recovery pass test {tid} still {recovery_result.get('status')}: "
                        f"{recovery_result.get('error', '')}"
                    )

            logger.info(
                f"[BATCH] Recovery pass {recovery_round + 1} complete: "
                f"{recovered}/{len(retry_ids)} recovered"
            )

        # Preserve original ordering.
        results = [result_map[tid] for tid in test_ids]

    return results


# ---------------------------------------------------------------------------
# Per-test coroutine
# ---------------------------------------------------------------------------


async def _execute_single_test(
    ctx: ExecutionContext,
    test_id: str,
    semaphore: asyncio.Semaphore,
    penelope_agent: Any = None,
    evaluator: Any = None,
    on_emit: Any = None,
    on_test_phase: Any = None,
) -> Dict[str, Any]:
    """Unified coroutine for both single-turn and multi-turn tests."""
    async with semaphore:
        # Both short-circuits below still report "done": they are terminal
        # for this test, and without it the grid's completed count would
        # never reach total on a run with skipped or unprefetched tests.
        def _report_done() -> None:
            if on_test_phase:
                try:
                    on_test_phase(test_id, TestPhase.DONE)
                except Exception:
                    logger.debug("on_test_phase(done) failed", exc_info=True)

        if test_id in ctx.existing_result_ids:
            logger.info(f"[BATCH] Skipping test {test_id}: result already exists")
            _report_done()
            return {"test_id": test_id, "status": "skipped", "execution_time": 0}

        td = ctx.test_data.get(test_id)
        if not td:
            _report_done()
            return {
                "test_id": test_id,
                "status": "failed",
                "error": "Test data not pre-fetched",
                "execution_time": 0,
            }

        test = td["test"]
        prompt_content = td["prompt_content"]
        expected_response = td["expected_response"]

        is_multi_turn = is_multi_turn_test(test)

        if on_test_phase:
            try:
                on_test_phase(test_id, TestPhase.GENERATING)
            except Exception:
                logger.debug("on_test_phase(generating) failed", exc_info=True)

        test_execution_context = {
            "test_run_id": str(ctx.test_run.id),
            "test_id": test_id,
            "test_configuration_id": str(ctx.test_config.id),
        }

        start_time = time.monotonic()
        deferred_traces: list = []
        output: Dict[str, Any] = {}
        penelope_metrics: Dict[str, Any] = {}
        metrics_results: Dict[str, Any] = {}

        try:
            # --- Run the test ---
            try:
                coro = run_test(
                    ctx,
                    test,
                    test_id,
                    prompt_content,
                    test_execution_context,
                    is_multi_turn,
                    deferred_traces,
                    penelope_agent,
                )
                result = await asyncio.wait_for(coro, timeout=ctx.per_test_timeout)
                output = result.get("output", {})
                penelope_metrics = result.get("penelope_metrics", {})
                deferred_traces = result.get("deferred_traces", deferred_traces)
                # Absent for single-turn tests, which have no evaluation contract concept.
                contract_usable = result.get("contract_usable", True)
                if on_test_phase:
                    try:
                        on_test_phase(test_id, TestPhase.EVALUATING)
                    except Exception:
                        logger.debug("on_test_phase(evaluating) failed", exc_info=True)
            except asyncio.TimeoutError:
                logger.error(f"[BATCH] Test {test_id} timed out after {ctx.per_test_timeout}s")
                return {
                    "test_id": test_id,
                    "status": "failed",
                    "error": f"Timeout after {ctx.per_test_timeout}s",
                    "execution_time": (time.monotonic() - start_time) * 1000,
                }
            except Exception as e:
                logger.error(f"[BATCH] Test {test_id} failed: {e}", exc_info=True)
                return {
                    "test_id": test_id,
                    "status": "failed",
                    "error": str(e),
                    "execution_time": (time.monotonic() - start_time) * 1000,
                    "exception_type": type(e).__name__,
                }

            # --- Async metric evaluation ---
            if not contract_usable:
                # The conversation was never run (see invocation._run_multi_turn), so there is
                # nothing to score. Checked before the evaluator branch below: that one would
                # otherwise evaluate configured metrics against the empty error output.
                metrics_results = {}
                logger.info(
                    f"[BATCH] Test {test_id} reported as Error: evaluation contract was not usable"
                )
            elif has_http_error_in_result(output):
                metrics_results = {}
                logger.info(f"[BATCH] HTTP error for test {test_id}; skipping metrics")
                if on_emit:
                    from rhesis.backend.app.utils.response_extractor import (
                        get_http_error_status_code,
                    )

                    code = get_http_error_status_code(output)
                    on_emit(f"  Endpoint returned HTTP {code}, skipping metrics")
            elif evaluator and ctx.get_metric_configs_for_test(test_id):
                metrics_results = await evaluate_metrics(
                    ctx,
                    evaluator,
                    test,
                    test_id,
                    output,
                    prompt_content,
                    expected_response,
                    is_multi_turn,
                    penelope_metrics,
                    on_emit=on_emit,
                )
            else:
                metrics_results = dict(penelope_metrics)

            execution_time = (time.monotonic() - start_time) * 1000

            # --- Persist result and deferred traces in a thread ---
            try:
                from rhesis.backend.jobs.execution.batch.persist import persist_result

                await asyncio.to_thread(
                    persist_result,
                    ctx,
                    test_id,
                    test,
                    output,
                    metrics_results,
                    deferred_traces,
                    execution_time,
                    is_multi_turn,
                )
            except Exception as e:
                logger.error(f"[BATCH] Persist failed for {test_id}: {e}", exc_info=True)
                return {
                    "test_id": test_id,
                    "status": "failed",
                    "error": f"Persist failed: {e}",
                    "execution_time": execution_time,
                }

            return {
                "test_id": test_id,
                "status": "succeeded",
                "execution_time": execution_time,
                "metrics": metrics_results,
            }
        finally:
            ctx.test_data.pop(test_id, None)
            ctx.input_files.pop(test_id, None)
            if on_test_phase:
                try:
                    on_test_phase(test_id, TestPhase.DONE)
                except Exception:
                    logger.debug("on_test_phase(done) failed", exc_info=True)
            deferred_traces.clear()
            output.clear()
            penelope_metrics.clear()
