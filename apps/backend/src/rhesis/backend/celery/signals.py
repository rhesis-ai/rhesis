import logging
import time

from celery.signals import (
    after_setup_logger,
    celeryd_init,
    task_failure,
    task_revoked,
    worker_ready,
    worker_shutdown,
)

import rhesis.backend.tasks.architect.monitor  # noqa: F401
from rhesis.backend.logging import set_logger
from rhesis.backend.tasks.enums import RunStatus

logger = logging.getLogger("celery.signals")

_EXECUTE_TEST_CONFIGURATION_TASK = "rhesis.backend.tasks.execute_test_configuration"


def _update_test_run_status(task_id: str, new_status: RunStatus, error_message: str = None):
    try:
        from rhesis.backend.app.database import SessionLocal, bind_scope_to_session
        from rhesis.backend.tasks.execution.run import update_test_run_status
        from rhesis.backend.tasks.utils import get_test_run_by_task_id

        with SessionLocal() as db:
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
                    from rhesis.backend.tasks.utils import update_test_run_with_error

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
def setup_worker_log_format(sender=None, conf=None, **kwargs):
    """Prefix Celery log lines with MAIN/ARCHITECT so both workers are distinguishable."""
    if conf is None:
        return
    role = (sender.split("@", 1)[0] if sender else "worker").upper()
    conf.worker_log_format = f"[%(asctime)s: %(levelname)s/{role}/%(processName)s] %(message)s"
    conf.worker_task_log_format = (
        f"[%(asctime)s: %(levelname)s/{role}/%(processName)s] "
        "[%(task_name)s(%(task_id)s)] %(message)s"
    )


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
    """Replace Celery's default root logger setup with our shared pipeline
    (RedactingFormatter + JSON/color/plain stdout; file logs when BACKEND_ENV=local).

    Runs after Celery hijacks the root logger at worker boot (the default
    `worker_hijack_root_logger` behavior), so calling this at import time
    would just get overwritten by Celery's own setup.
    """
    set_logger()


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
            _update_test_run_status(task_id, RunStatus.CANCELLED)
