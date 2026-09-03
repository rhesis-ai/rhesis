from celery.schedules import crontab

from rhesis.backend.app.config.settings import get_redis_settings

redis_settings = get_redis_settings()

# Worker-context config: retry aggressively to ensure task delivery
CELERY_CONFIG = {
    # Redis configuration
    "broker_url": redis_settings.broker_url,
    "result_backend": redis_settings.result_backend,
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
        # Must exceed the longest task_annotations time_limit below, or Redis
        # redelivers a still-running task to a second worker: with
        # task_acks_late the message is only acked on completion, and kombu's
        # default here is 3600s -- shorter than the 3900s hard limit on
        # execute_test_configuration. Nothing guards against the duplicate
        # (a run already in Progress is re-executed from the first test), and
        # progress is written as an absolute value keyed by celery_task_id,
        # which a redelivery reuses -- so the second pass drags the counter
        # backwards over the first.
        "visibility_timeout": 7200,
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
        "rhesis.backend.jobs.execution.*": {"queue": "execution"},
        "rhesis.backend.jobs.telemetry.*": {"queue": "telemetry"},
        "rhesis.backend.jobs.architect.*": {"queue": "architect"},
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
    # Task annotations
    "task_annotations": {
        "rhesis.backend.jobs.execute_test_configuration": {
            "soft_time_limit": 3600,
            "time_limit": 3900,
        },
        "rhesis.backend.jobs.telemetry.evaluate.evaluate_turn_trace_metrics": {
            "max_retries": 3,
            "soft_time_limit": 300,
            "time_limit": 360,
        },
        "rhesis.backend.jobs.telemetry.evaluate.evaluate_conversation_trace_metrics": {
            "max_retries": 3,
            "soft_time_limit": 600,
            "time_limit": 660,
        },
    },
    # Task discovery
    "include": [
        "rhesis.backend.jobs.test_configuration",
        "rhesis.backend.jobs.embedding.generate",
        "rhesis.backend.jobs.embedding.graph",
        "rhesis.backend.jobs.test_set",
        "rhesis.backend.jobs.execution.results",
        "rhesis.backend.jobs.telemetry.enrich",
        "rhesis.backend.jobs.architect.chat",
        "rhesis.backend.jobs.telemetry.evaluate",
        "rhesis.backend.jobs.telemetry.post_ingest",
        "rhesis.backend.jobs.retention",
        "rhesis.backend.jobs.trace_retention",
    ],
    # Requires a `celery beat` process actually running against this app --
    # not deployed anywhere yet (see jobs/retention.py's own docstring for
    # why the task itself is still a no-op until JOB_RETENTION_ENABLED=true).
    # Runs at 03:00 UTC, off peak hours for every timezone this platform has
    # users in today.
    "beat_schedule": {
        "job-retention-sweep": {
            "task": "rhesis.backend.jobs.retention.sweep_expired_jobs",
            "schedule": crontab(hour=3, minute=0),
        },
        "trace-retention-sweep": {
            "task": "rhesis.backend.jobs.trace_retention.sweep_expired_traces",
            "schedule": crontab(hour=4, minute=0),
        },
    },
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
