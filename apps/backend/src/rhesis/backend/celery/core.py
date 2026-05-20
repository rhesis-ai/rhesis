import logging

from celery import Celery

from rhesis.backend.celery.config import CELERY_CONFIG

logger = logging.getLogger(__name__)

# Create the Celery app
app = Celery("rhesis")

# Configure Celery for Redis backend with TLS support
app.conf.update(CELERY_CONFIG)

# Auto-discover tasks
app.autodiscover_tasks(["rhesis.backend.tasks"], force=True)

_web_overrides_applied = False


def apply_web_context_overrides():
    """Apply fail-fast broker settings for the FastAPI web process.

    Workers keep the default aggressive retry config (30s timeouts,
    10 retries). The web process should never block an HTTP thread
    for more than a couple of seconds waiting on Redis.
    """
    global _web_overrides_applied
    if _web_overrides_applied:
        return

    from rhesis.backend.celery.config import WEB_CELERY_OVERRIDES

    app.conf.update(WEB_CELERY_OVERRIDES)
    _web_overrides_applied = True
    logger.info("Celery broker configured for web context (fail-fast timeouts)")
