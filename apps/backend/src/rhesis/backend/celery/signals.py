import logging

from celery.signals import worker_process_init


@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Called in each child process immediately after fork.
    We must dispose of inherited connection pools to prevent memory corruption
    (e.g., SIGSEGV or SIGKILL) from concurrent access across processes.
    """
    logger = logging.getLogger("celery.worker")
    logger.info("Initializing worker process: disposing parent connection pools")

    # 1. Dispose SQLAlchemy Engine
    try:
        from rhesis.backend.app.database import engine

        if engine:
            engine.dispose(False)
            logger.info("Disposed SQLAlchemy engine pool")
    except Exception as e:
        logger.warning(f"Error disposing SQLAlchemy engine: {e}")

    # 2. Re-initialize Redis caches (creates new connection pools)
    try:
        from rhesis.backend.app.services.telemetry.conversation_linking import (
            initialize_cache as init_conv_cache,
        )
        from rhesis.backend.app.services.telemetry.trace_metrics_cache import (
            initialize_cache as init_metrics_cache,
        )

        init_conv_cache()
        init_metrics_cache()
        logger.info("Re-initialized telemetry caches")
    except Exception as e:
        logger.warning(f"Error re-initializing caches: {e}")
