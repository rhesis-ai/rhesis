import os

from celery import Celery
from dotenv import load_dotenv

# Load environment variables from .env file (only works locally, not in Cloud Run)
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
    # Database backend specific chord configuration
    chord_unlock_max_retries=10,  # Increase retries for database backend
    chord_unlock_retry_delay=5.0,  # Longer delay between retries
    result_chord_join_timeout=300,  # 5 minutes timeout for chord joins
    # Database backend optimizations
    result_persistent=True,
    result_expires=7200,  # 2 hours - longer for database backend
    database_table_names={
        'task': 'celery_taskmeta',
        'group': 'celery_groupmeta',
    },
    # Force database transactions to be committed immediately
    database_engine_options={
        'isolation_level': 'AUTOCOMMIT',  # Prevent read-after-write issues
        'pool_pre_ping': True,  # Verify connections before use
        'pool_recycle': 3600,  # Recycle connections hourly
    },
    # Additional stability configurations for database backend
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    # Prevent channel promise issues
    task_reject_on_worker_lost=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Enhanced chord reliability for database backend
    task_track_started=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    # Force result backend to use polling for chord coordination
    result_backend_always_retry=True,
    result_backend_max_retries=10,
    # Task-specific configurations
    task_routes={
        'celery.chord_unlock': {'queue': 'celery'},
        'rhesis.backend.tasks.execution.results.collect_results': {'queue': 'celery'},
    },
    task_annotations={
        'celery.chord_unlock': {
            'max_retries': 10,  # More retries for database backend
            'retry_backoff': True,
            'retry_backoff_max': 300,  # Up to 5 minutes between retries
            'retry_jitter': True,
            'soft_time_limit': 600,  # 10 minutes soft limit
            'time_limit': 900,       # 15 minutes hard limit
            # Database-specific chord_unlock settings
            'chord_unlock_retry_delay': 10.0,  # Longer delays
        },
        'rhesis.backend.tasks.execution.results.collect_results': {
            'max_retries': 3,
            'retry_backoff': True,
            'retry_backoff_max': 60,
            'soft_time_limit': 600,  # 10 minutes soft limit
            'time_limit': 900,       # 15 minutes hard limit
        },
        'rhesis.backend.tasks.execute_single_test': {
            'max_retries': 2,
            'retry_backoff': True,
            'retry_backoff_max': 120,
            'soft_time_limit': 300,  # 5 minutes soft limit
            'time_limit': 600,       # 10 minutes hard limit
        }
    },
    # Add explicit task discovery
    include=[
        'rhesis.backend.tasks.test_configuration',
        'rhesis.backend.tasks.example_task',
        'rhesis.backend.tasks.test_set',
        'rhesis.backend.tasks.execution.results',
        'rhesis.backend.tasks.execution.test',
        'rhesis.backend.tasks.execution.db_chord_coordinator',
    ],
)

# Print configuration for debugging
print(f"Celery app created with broker: {bool(app.conf.broker_url)}")
print(f"Result backend configured: {bool(app.conf.result_backend)}")

# Auto-discover tasks without loading config files
app.autodiscover_tasks(["rhesis.backend.tasks"], force=True)

# After autodiscovery, print discovered tasks
def print_registered_tasks():
    """Print all registered tasks for debugging"""
    print("Registered Celery tasks:")
    for task_name in sorted(app.tasks.keys()):
        print(f"  - {task_name}")

# Call this after import if log level is debug
if app.conf.worker_log_format == 'DEBUG':
    print_registered_tasks()

# Test task registration by checking if our main task is available
if __name__ == "__main__":
    print("\n=== Worker Module Test ===")
    expected_task = "rhesis.backend.tasks.execute_test_configuration"
    if expected_task in app.tasks:
        print(f"✅ Task {expected_task} is properly registered")
        task = app.tasks[expected_task]
        print(f"Task type: {type(task)}")
        print(f"Task name: {task.name}")
    else:
        print(f"❌ Task {expected_task} is NOT registered")
        print("Available tasks:")
        for name in sorted(app.tasks.keys()):
            print(f"  - {name}")
