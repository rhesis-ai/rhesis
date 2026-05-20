import os

# Worker-context config: retry aggressively to ensure task delivery
CELERY_CONFIG = {
    # Redis configuration
    "broker_url": os.getenv("BROKER_URL", "redis://localhost:6379/0"),
    "result_backend": os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    # Serialization
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    # Timezone
    "timezone": "UTC",
    "enable_utc": True,
    # Redis-optimized settings
    "result_expires": 3600,  # 1 hour - shorter for Redis efficiency
    "result_compression": "gzip",
    # Connection settings for Redis reliability
    "broker_connection_retry_on_startup": True,
    "broker_connection_retry": True,
    "broker_connection_max_retries": 10,
    # Cap the kombu broker connection pool (default is 10, making explicit)
    "broker_pool_limit": 10,
    # Redis transport options with explicit connection pool caps.
    # max_connections limits the underlying redis-py ConnectionPool so that
    # slow operations under Redis contention don't cause unbounded growth.
    "broker_transport_options": {
        "retry_on_timeout": True,
        "connection_pool_kwargs": {
            "max_connections": 10,
            "retry_on_timeout": True,
            "socket_connect_timeout": 30,
            "socket_timeout": 30,
        },
    },
    "result_backend_transport_options": {
        "retry_on_timeout": True,
        "connection_pool_kwargs": {
            "max_connections": 5,
            "retry_on_timeout": True,
            "socket_connect_timeout": 30,
            "socket_timeout": 30,
        },
    },
    # Task execution settings
    "task_routes": {
        "rhesis.backend.tasks.execution.*": {"queue": "execution"},
        "rhesis.backend.tasks.telemetry.*": {"queue": "telemetry"},
        "rhesis.backend.tasks.architect.*": {"queue": "architect"},
    },
    # Worker settings
    "worker_prefetch_multiplier": 1,
    "task_acks_late": True,
    "worker_disable_rate_limits": False,
    "task_track_started": True,
    "task_publish_retry": True,
    "task_publish_retry_policy": {
        "max_retries": 5,
        "interval_start": 0.1,
        "interval_step": 0.2,
        "interval_max": 1.0,
    },
    # Task tracking for monitoring
    "task_send_sent_event": False,  # Disable for performance
    "worker_send_task_events": False,  # Disable for performance
    # Reduce verbose task result logging
    "task_always_eager": False,
    "task_eager_propagates": False,
    # Suppress verbose task result logging
    "worker_log_format": "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    "worker_task_log_format": "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    # Task annotations
    "task_annotations": {
        "rhesis.backend.tasks.execute_test_configuration": {
            "soft_time_limit": 3600,
            "time_limit": 3900,
        },
        "rhesis.backend.tasks.telemetry.evaluate.evaluate_turn_trace_metrics": {
            "max_retries": 3,
            "soft_time_limit": 300,
            "time_limit": 360,
        },
        "rhesis.backend.tasks.telemetry.evaluate.evaluate_conversation_trace_metrics": {
            "max_retries": 3,
            "soft_time_limit": 600,
            "time_limit": 660,
        },
    },
    # Task discovery
    "include": [
        "rhesis.backend.tasks.test_configuration",
        "rhesis.backend.tasks.embedding.generate",
        "rhesis.backend.tasks.embedding.graph",
        "rhesis.backend.tasks.example_task",
        "rhesis.backend.tasks.test_set",
        "rhesis.backend.tasks.execution.results",
        "rhesis.backend.tasks.telemetry.enrich",
        "rhesis.backend.tasks.architect",
        "rhesis.backend.tasks.telemetry.evaluate",
        "rhesis.backend.tasks.telemetry.post_ingest",
    ],
}

# Web-context overrides: fail fast instead of blocking HTTP request threads.
# Applied by apply_web_context_overrides() during FastAPI startup.
# Worst case changes from 10 retries x 30s = 300s to a single 2s attempt.
WEB_CELERY_OVERRIDES = {
    "broker_connection_max_retries": 0,
    # Web processes only publish tasks — they need fewer connections than workers.
    "broker_pool_limit": 5,
    "broker_transport_options": {
        "retry_on_timeout": False,
        "connection_pool_kwargs": {
            "max_connections": 5,
            "retry_on_timeout": False,
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
        },
    },
    "result_backend_transport_options": {
        "retry_on_timeout": False,
        "connection_pool_kwargs": {
            "max_connections": 3,
            "retry_on_timeout": False,
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
        },
    },
    "task_publish_retry_policy": {
        "max_retries": 1,
        "interval_start": 0.1,
        "interval_step": 0.1,
        "interval_max": 0.5,
    },
}
