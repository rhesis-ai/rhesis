from celery import Celery

from rhesis.backend.celery.config import CELERY_CONFIG

# Create the Celery app
app = Celery("rhesis")

# Configure Celery for Redis backend with TLS support
app.conf.update(CELERY_CONFIG)

# Auto-discover tasks
app.autodiscover_tasks(["rhesis.backend.tasks"], force=True)
