import logging
import time

from celery.signals import (
    after_setup_logger,
    celeryd_init,
    task_failure,
    task_postrun,
    task_prerun,
    task_revoked,
    worker_process_init,
    worker_ready,
    worker_shutdown,
)

import rhesis.backend.jobs.architect.monitor  # noqa: F401
from rhesis.backend.jobs.enums import RunStatus
from rhesis.backend.logging import set_logger

logger = logging.getLogger("celery.signals")

_EXECUTE_TEST_CONFIGURATION_TASK = "rhesis.backend.jobs.execute_test_configuration"
# Set in celeryd_init from the worker node name (e.g. main@host → MAIN).
_worker_role: str | None = None

# Reset tokens from bind_usage_attribution_for_task, keyed by task id. A dict
# rather than a single slot because eventlet/gevent pools interleave tasks in
# one process, so prerun/postrun pairs can overlap.
_usage_attribution_tokens: dict = {}


def _update_test_run_status(
    task_id: str,
    new_status: RunStatus,
    error_message: str = None,
    test_run_id: str = None,
):
    try:
        from uuid import UUID

        from rhesis.backend.app.crud.test_run import get_test_run
        from rhesis.backend.app.database import SessionLocal, bind_scope_to_session
        from rhesis.backend.jobs.execution.run import update_test_run_status
        from rhesis.backend.jobs.utils import get_test_run_by_task_id

        with SessionLocal() as db:
            if test_run_id:
                test_run = get_test_run(db, UUID(test_run_id))
            else:
                test_run = get_test_run_by_task_id(db, task_id)
            if test_run:
                org_id = str(test_run.organization_id) if test_run.organization_id else ""
                user_id = (
                    str(test_run.user_id)
                    if hasattr(test_run, "user_id") and test_run.user_id
                    else ""
                )
                project_id = (
                    str(test_run.project_id) if getattr(test_run, "project_id", None) else ""
                )
                bind_scope_to_session(db, org_id, user_id, project_id)

                if new_status == RunStatus.FAILED:
                    from rhesis.backend.jobs.utils import update_test_run_with_error

                    update_test_run_with_error(db, test_run, error_message or "Unknown error")
                else:
                    update_test_run_status(db, test_run, new_status.value)
                db.commit()
                logger.info(
                    f"Updated test_run {test_run.id} to {new_status.value} for task {task_id}"
                )
    except Exception as e:
        logger.error(f"Failed to update test run status for task {task_id}: {e}", exc_info=True)


@celeryd_init.connect
@worker_process_init.connect
def install_worker_usage_sink(**kwargs):
    """Register the process-wide token-usage sink and EE providers in the worker.

    Connected to both signals on purpose, and ``celeryd_init`` is the
    load-bearing one. ``worker_process_init`` is sent only by the prefork and
    solo pools (see ``celery/concurrency/{prefork,solo}.py``), and this
    deployment runs ``--pool threads`` for both the main and architect
    workers, so on its own it would never fire and no Celery task would
    accrue anything at all. ``celeryd_init`` fires for every pool.

    Keeping ``worker_process_init`` as well covers prefork children, where
    installing after the fork keeps the sink independent of whatever the
    parent had imported at fork time. Installation is idempotent, so being
    called by both costs nothing.

    ``bootstrap_ee_providers`` installs the EE license and quota providers so
    workers resolve licensed quota limits instead of falling back to free-tier
    defaults. It registers no features, so no feature gate can flip in a
    worker. No-op when the EE package is not installed.
    """
    from rhesis.backend.app.ee_bootstrap import bootstrap_ee_providers
    from rhesis.backend.app.utils.usage_tracking import install_usage_sink

    bootstrap_ee_providers()
    install_usage_sink()


def _task_organization_id(task, task_kwargs):
    """Resolve the org for a task that is starting, from the raw message.

    Cannot read ``task.request.organization_id``: Celery's tracer fires
    ``task_prerun`` *before* it calls ``Task.before_start``, and
    ``before_start`` is what copies the org off the message onto the request.
    At this point the attribute is still unset, so reading it would leave
    every Celery task unattributed -- which is most of the token spend.

    Mirrors ``BaseJob.before_start``'s own precedence, including kwargs
    winning over headers, so attribution matches what the task body will see
    a moment later rather than disagreeing with it on retries.
    """
    request = getattr(task, "request", None)
    headers = getattr(request, "headers", None) or {}

    organization_id = headers.get("organization_id") if hasattr(headers, "get") else None
    if (task_kwargs or {}).get("organization_id"):
        organization_id = task_kwargs["organization_id"]
    if not organization_id:
        # Anything that set it directly, e.g. a task invoked in-process.
        organization_id = getattr(request, "organization_id", None)
    return organization_id


@task_prerun.connect
def bind_usage_attribution_for_task(task_id=None, task=None, kwargs=None, **_):
    """Name the org to bill for any LLM tokens this task spends.

    The org rides in on the task headers and is already unpacked onto
    the task message. Reading it here instead of threading it into each model
    constructor means a task that calls an LLM accrues correctly without
    knowing that usage accounting exists.

    A signal rather than ``BaseJob.before_start`` because not every task
    subclasses ``BaseJob`` -- ``tasks.usage.accrue_usage`` itself is a plain
    ``@app.task``, and the next one someone writes might be too. The cost of
    that choice is that the org has to be dug out of the raw message here;
    see :func:`_task_organization_id`.
    """
    from rhesis.backend.app.usage_attribution import bind_usage_org

    if not task_id:
        # Nothing to key the reset token by, so binding would leak into
        # whatever task runs next in this process. Skipping leaves the usage
        # unattributed, which is logged, rather than billed to the wrong org.
        # Deliberately not falling back to id(task): Celery instantiates one
        # task object per task type per worker, so concurrent runs of the
        # same task would share a key and reset each other's tokens.
        logger.warning("task_prerun without a task_id; usage will not be attributed")
        return

    _usage_attribution_tokens[task_id] = bind_usage_org(_task_organization_id(task, kwargs))


@task_postrun.connect
def clear_usage_attribution_for_task(task_id=None, **kwargs):
    """Unbind the org bound in ``bind_usage_attribution_for_task``.

    Load-bearing, not tidiness: a prefork worker runs task after task in one
    process, so a binding left in place would charge the next task's tokens
    to the previous task's organization.
    """
    from rhesis.backend.app.usage_attribution import reset_usage_org

    token = _usage_attribution_tokens.pop(task_id, None)
    if token is not None:
        reset_usage_org(token)


# Detach tokens from attach_trace_context_for_task, keyed by task id. Same
# dict-per-task-id shape as _usage_attribution_tokens, and for the same
# reason: pool types that interleave tasks in one process need prerun/postrun
# pairs that cannot cross-talk.
_trace_context_tokens: dict = {}


@task_prerun.connect
def attach_trace_context_for_task(task_id=None, task=None, **_):
    """Make the dispatching request's trace context current for this task.

    Mirrors ``bind_usage_attribution_for_task`` above -- a signal rather than
    ``BaseJob.before_start`` for the same reason: not every task subclasses
    ``BaseJob``. Reads the raw message headers directly rather than
    ``task.request.headers``, since ``before_start`` (which copies headers
    onto the request) has not run yet at ``task_prerun`` time.

    A task with no ``traceparent`` header (e.g. one dispatched outside
    ``launch_job``) gets nothing attached here; ``events.correlation``'s
    fallback still gives it valid, if unlinked, ids when something emits.
    """
    from rhesis.backend.events.correlation import attach_from_headers

    if not task_id:
        logger.warning("task_prerun without a task_id; trace context will not attach")
        return

    headers = getattr(getattr(task, "request", None), "headers", None) or {}
    token = attach_from_headers(headers)
    if token is not None:
        _trace_context_tokens[task_id] = token


@task_postrun.connect
def detach_trace_context_for_task(task_id=None, **kwargs):
    """Undo ``attach_trace_context_for_task``. Load-bearing for the same
    reason as ``clear_usage_attribution_for_task``: a binding left in place
    on a reused worker thread would misattribute the next task's spans and
    events to this one's trace.
    """
    from rhesis.backend.events.correlation import detach

    token = _trace_context_tokens.pop(task_id, None)
    detach(token)


@celeryd_init.connect
def capture_worker_role(sender=None, conf=None, **kwargs):
    """Derive MAIN/ARCHITECT from the Celery node name (``-n main@host``).

    Runs before ``after_setup_logger`` in Celery's worker boot sequence, so the
    role is available when we install our shared logging pipeline.
    """
    global _worker_role
    _worker_role = (sender.split("@", 1)[0] if sender else "worker").upper()


@worker_ready.connect
def warm_architect_worker(sender=None, **kwargs):
    """Preload the backend FastAPI app on the architect worker at boot.

    The architect task imports ``rhesis.backend.app.main`` lazily inside
    ``build_agent()``, which pulls in every router plus the ragas/sklearn
    stack and builds the OpenAPI schema — ~15-25s on a cold process. Paid
    lazily, that cost lands on the user's first message. Doing it here moves
    it to worker startup so the first architect turn hits a warm process.

    Scoped to the architect worker (node name ``architect@...``) so the main
    worker doesn't pay for an import it may not need.
    """
    hostname = getattr(sender, "hostname", "") or ""
    if not hostname.startswith("architect@"):
        return

    logger.info("Architect worker: starting backend app preload to warm import cache")
    start = time.perf_counter()
    try:
        from rhesis.backend.app.main import app

        # Build and cache the OpenAPI schema now; LocalToolProvider needs it
        # on the first tool call and it is otherwise rebuilt mid-request.
        app.openapi()
    except Exception as e:
        logger.error("Architect worker: backend app preload failed: %s", e, exc_info=True)
        return

    elapsed = time.perf_counter() - start
    logger.info("Architect worker: backend app preloaded in %.1fs", elapsed)


@after_setup_logger.connect
def configure_worker_logging(logger=None, **kw):
    """Replace Celery's default root logger setup with our shared pipeline.

    Runs after Celery hijacks the root logger at worker boot (the default
    `worker_hijack_root_logger` requirement), so calling this at import time
    would just get overwritten by Celery's own setup.

    Uses the role captured from the Celery hostname in ``celeryd_init``.
    """
    set_logger(worker_role=_worker_role)


@after_setup_logger.connect
def quiet_celery_internal_loggers(logger=None, **kw):
    """Silence low-signal Celery internal DEBUG chatter (e.g. pidbox
    'enable_events()' control-mailbox heartbeats) without lowering the
    worker's overall log level.

    Runs after Celery configures its loggers at worker boot, so these
    levels stick (an import-time setLevel would be reset by Celery).
    """
    for name in (
        "celery.utils.functional",
        "celery.app.trace",
        "kombu.pidbox",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


@task_failure.connect
def handle_task_failure(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    traceback=None,
    einfo=None,
    **kw,
):
    task_name = getattr(sender, "name", str(sender))
    if task_name == _EXECUTE_TEST_CONFIGURATION_TASK:
        logger.info(
            f"Task failure caught for {task_name} (ID: {task_id}). Setting TestRun to Failed."
        )
        _update_test_run_status(
            task_id,
            RunStatus.FAILED,
            str(exception) if exception else "Task failed or worker crashed",
            test_run_id=(kwargs or {}).get("test_run_id"),
        )


@worker_shutdown.connect
def handle_worker_shutdown(sender=None, **kw):
    """Release thread-local httpx clients on clean worker shutdown."""
    try:
        from rhesis.backend.app.services.invokers.rest_invoker import (
            _close_thread_local_client,
        )

        _close_thread_local_client()
    except Exception as e:
        logger.debug(f"Could not close thread-local HTTP client on shutdown: {e}")


@task_revoked.connect
def handle_task_revoked(sender=None, request=None, **kw):
    if request:
        task_id = request.id
        task_name = request.task
        if task_name == _EXECUTE_TEST_CONFIGURATION_TASK:
            logger.info(
                f"Task revoked caught for {task_name} (ID: {task_id}). "
                f"Setting TestRun to Cancelled."
            )
            task_kwargs = getattr(request, "kwargs", None) or {}
            _update_test_run_status(
                task_id,
                RunStatus.CANCELLED,
                test_run_id=task_kwargs.get("test_run_id"),
            )

        # A signal rather than a BaseJob hook because revocation can land on a
        # task that never started, so no hook of ours would ever run for it.
        # The tenant triple comes off the message headers for the same reason:
        # before_start has not copied them onto the request yet.
        headers = getattr(request, "headers", None) or {}
        _mark_job_cancelled(task_id, task_name, headers)


def _mark_job_cancelled(task_id: str, task_name: str, headers: dict) -> None:
    from rhesis.backend.jobs import tracking

    try:
        tracking.mark_cancelled(
            task_id,
            headers.get("organization_id") or "",
            headers.get("user_id") or "",
            headers.get("project_id") or "",
        )
    except Exception as exc:
        logger.warning(f"Could not mark job {task_id} cancelled: {exc}", exc_info=True)

    # Separate try/except, matching BaseJob._advance_job_row: the activity
    # log narrative must not affect (or be affected by) the job row update
    # above. No pre-check for whether a job row exists -- unlike JobQueued,
    # which fires on every dispatch including untracked high-frequency
    # types, a revoke only ever targets something a user chose to cancel,
    # so an orphaned entry here would be a rare edge case, not routine noise.
    try:
        from datetime import datetime, timezone

        from rhesis.backend.events import emit
        from rhesis.backend.events.correlation import resolve_ids
        from rhesis.backend.events.types import JobCancelled
        from rhesis.backend.jobs.tracking import job_type_for

        org_id = headers.get("organization_id")
        if not org_id:
            return

        # One-shot extraction from the message headers, not the ambient
        # context: task_prerun never ran for a task revoked before it
        # started, so there is nothing attached to read instead.
        trace_id, span_id = resolve_ids(headers)
        emit(
            JobCancelled(
                occurred_at=datetime.now(timezone.utc),
                organization_id=org_id,
                project_id=headers.get("project_id"),
                user_id=headers.get("user_id"),
                trace_id=trace_id,
                span_id=span_id,
                celery_task_id=task_id,
                source=job_type_for(task_name or ""),
            )
        )
    except Exception as exc:
        logger.warning(f"Could not emit JobCancelled for {task_id}: {exc}", exc_info=True)
