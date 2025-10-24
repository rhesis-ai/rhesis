import os

from celery import Celery
from dotenv import load_dotenv

# Load environment variables from .env file (only works locally, not in Cloud Run)
load_dotenv()

# Create the Celery app
app = Celery("rhesis")

# Configure Celery for Redis backend with TLS support
app.conf.update(
    # Redis configuration
    broker_url=os.getenv("BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Redis-optimized settings
    result_expires=3600,  # 1 hour - shorter for Redis efficiency
    result_compression="gzip",
    # Connection settings for Redis reliability
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    # Simplified Redis transport options
    broker_transport_options={
        "retry_on_timeout": True,
        "connection_pool_kwargs": {
            "retry_on_timeout": True,
            "socket_connect_timeout": 30,
            "socket_timeout": 30,
        },
    },
    result_backend_transport_options={
        "retry_on_timeout": True,
        "connection_pool_kwargs": {
            "retry_on_timeout": True,
            "socket_connect_timeout": 30,
            "socket_timeout": 30,
        },
    },
    # Task execution settings
    task_routes={
        "rhesis.backend.tasks.execution.*": {"queue": "execution"},
        "rhesis.backend.tasks.metrics.*": {"queue": "metrics"},
    },
    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    # Chord settings (Redis native support)
    task_track_started=True,
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": 5,
        "interval_start": 0.1,
        "interval_step": 0.2,
        "interval_max": 1.0,
    },
    # Task tracking for monitoring
    task_send_sent_event=False,  # Disable for performance
    worker_send_task_events=False,  # Disable for performance
    # Reduce verbose task result logging
    task_always_eager=False,
    task_eager_propagates=False,
    # Suppress verbose task result logging
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    # Task annotations
    task_annotations={
        "rhesis.backend.tasks.execution.results.collect_results": {
            "max_retries": 3,
            "retry_backoff": True,
            "retry_backoff_max": 60,
            "soft_time_limit": 300,  # 5 minutes
            "time_limit": 600,  # 10 minutes
        },
        "rhesis.backend.tasks.execution.test.execute_single_test": {
            "max_retries": 2,
            "retry_backoff": True,
            "retry_backoff_max": 120,
            "soft_time_limit": 300,  # 5 minutes
            "time_limit": 600,  # 10 minutes
        },
    },
    # Task discovery
    include=[
        "rhesis.backend.tasks.test_configuration",
        "rhesis.backend.tasks.example_task",
        "rhesis.backend.tasks.test_set",
        "rhesis.backend.tasks.execution.results",
        "rhesis.backend.tasks.execution.test",
    ],
)

# Auto-discover tasks
app.autodiscover_tasks(["rhesis.backend.tasks"], force=True)

# Configure logging to reduce verbosity
import logging

# Suppress verbose Celery task result logging
logging.getLogger("celery.task").setLevel(logging.WARNING)
logging.getLogger("celery.worker").setLevel(logging.WARNING)

if __name__ == "__main__":
    print("\n=== Worker Module Test ===")
    print("Redis-optimized Celery configuration loaded")
    print(f"Available tasks: {len(app.tasks)}")
