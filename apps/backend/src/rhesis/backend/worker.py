import os

from celery import Celery
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create the Celery app
app = Celery("rhesis")

# Configure Celery
app.conf.update(
    broker_url=os.getenv("BROKER_URL"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Limit chord unlocks to prevent infinite retry loops
    chord_unlock_max_retries=3,
    # Use light amqp result store
    result_persistent=False,
    # Additional stability configurations
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    # Prevent channel promise issues
    task_reject_on_worker_lost=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks without loading config files
app.autodiscover_tasks(["rhesis.backend.tasks"], force=True)
