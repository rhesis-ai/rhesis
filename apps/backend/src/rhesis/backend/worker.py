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
    # Chord configuration - prevent infinite retry loops
    chord_unlock_max_retries=3,
    chord_unlock_retry_delay=1.0,
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
    # Task-specific configurations
    task_routes={
        'celery.chord_unlock': {'queue': 'celery'},
    },
    task_annotations={
        'celery.chord_unlock': {
            'max_retries': 3,
            'retry_backoff': True,
            'retry_backoff_max': 60,
            'retry_jitter': True,
        },
        'rhesis.backend.tasks.execution.results.collect_results': {
            'max_retries': 3,
            'retry_backoff': True,
            'retry_backoff_max': 60,
        }
    },
    # Add explicit task discovery
    include=[
        'rhesis.backend.tasks.test_configuration',
        'rhesis.backend.tasks.example_task',
        'rhesis.backend.tasks.test_set',
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

# Call this after import
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
