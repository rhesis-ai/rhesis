from celery.schedules import crontab

from rhesis.backend.app.config.settings import get_job_limit_settings, get_redis_settings
from rhesis.backend.app.ee_bootstrap import ee_celery_jobs

redis_settings = get_redis_settings()
job_limits = get_job_limit_settings()

# execute_test_configuration stops itself at EXECUTION_TIME_LIMIT (see
# jobs/execution/shared.run_deadline); the hard limit leaves room to wrap up.
EXECUTION_HARD_LIMIT = job_limits.execution_time_limit + 300
# Must outlast test runs and explorations, which stop themselves (see
# broker_transport_options below), so it follows the execution limit up.
VISIBILITY_TIMEOUT = max(7200, EXECUTION_HARD_LIMIT + 300)

# Every queue, the rule for what goes on it, and the jobs routed there. A new job goes on
# the queue whose rule it fits; tests/backend/celery/test_task_routes.py fails until it
# is listed. Names are exact (no globs), so a job is never routed by accident.
# Workers per queue: apps/worker/start.sh.
_J = "rhesis.backend.jobs."
QUEUES: dict[str, tuple[str, list[str]]] = {
    "test-runs": (
        "Runs a test set against an endpoint. One long task per run; its tests fan out "
        "in-process, so one slot holds a whole run.",
        [_J + "execute_test_configuration", _J + "execution.results.collect_results"],
    ),
    "long-jobs": (
        "Started by a user and runs for minutes, mostly waiting on LLM or endpoint calls.",
        [
            _J + "generate_and_save_test_set",
            _J + "generate_and_save_owasp_test_set",
            _J + "sync_garak_test_set",
            _J + "run_metric_tuning",
            _J + "endpoint.explore.run_exploration_task",
            _J + "audit_log.export",
        ],
    ),
    "architect": (
        "An interactive agent turn someone is waiting on.",
        [_J + "architect.architect_chat_task"],
    ),
    "trace-ingest": (
        "Stores incoming spans. Its own queue, so ingest admission measures only ingest "
        "and a backlog of trace evaluations cannot delay storing spans.",
        [_J + "telemetry.ingest.ingest_spans"],
    ),
    "trace-eval": (
        "Per-trace work after the spans are stored: cost enrichment, linking, metric evaluation.",
        [
            _J + "telemetry.enrich.enrich_trace_async",
            _J + "telemetry.post_ingest.post_ingest_link",
            _J + "telemetry.evaluate.evaluate_turn_trace_metrics",
            _J + "telemetry.evaluate.evaluate_conversation_trace_metrics",
        ],
    ),
    "quick-tasks": (
        "Seconds at most, high volume, nobody watching: bookkeeping and follow-ups.",
        [_J + "usage.accrue_usage", _J + "embedding.generate_embedding", _J + "count_test_sets"],
    ),
    "cpu-bound": (
        "Spends its time computing, not waiting: it would stall the I/O queues' event loops.",
        [
            _J + "embedding.compute_graph_test_set",
            _J + "embedding.compute_graph_source",
            _J + "file.extract_text",
            _J + "import_garak_probes",
        ],
    ),
    "maintenance": (
        "Scheduled housekeeping started by beat.",
        [
            _J + "heartbeat.beat_heartbeat",
            _J + "model_prices.refresh_model_prices",
            _J + "retention.sweep_expired_jobs",
            _J + "trace_retention.sweep_expired_traces",
            _J + "audit_retention.sweep_expired_audit_events",
            _J + "test_run_schedules.dispatch_due_schedules",
        ],
    ),
}

TASK_ROUTES = {name: {"queue": queue} for queue, (_, names) in QUEUES.items() for name in names}

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
        # Must exceed the longest task run, or Redis redelivers a still-running
        # task to a second worker and it runs twice: with task_acks_late the
        # message is only acked on completion. The worker's thread pool ignores
        # time_limit, so a test run is bounded by its own deadline
        # (EXECUTION_TIME_LIMIT) and this stays above it. Generation, Garak and
        # tuning jobs have no in-job limit yet and can still outlast it.
        "visibility_timeout": VISIBILITY_TIMEOUT,
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
    "task_routes": TASK_ROUTES,
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
        # Inert under --pool threads; kept equal to the in-job limit for other pools.
        "rhesis.backend.jobs.execute_test_configuration": {
            "soft_time_limit": job_limits.execution_time_limit,
            "time_limit": EXECUTION_HARD_LIMIT,
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
        "rhesis.backend.jobs.telemetry.ingest",
        "rhesis.backend.jobs.telemetry.post_ingest",
        "rhesis.backend.jobs.retention",
        "rhesis.backend.jobs.trace_retention",
        "rhesis.backend.jobs.heartbeat",
        "rhesis.backend.jobs.audit_retention",
        "rhesis.backend.jobs.model_prices",
        "rhesis.backend.jobs.test_run_schedules",
    ],
    # Run by the single `celery beat` process (the chart's beat Deployment, the
    # compose `beat` service). The retention sweeps are no-ops until their
    # *_ENABLED flag is set (see each job's docstring); they run at 03:00 and
    # 04:00 UTC, off peak hours for every timezone this platform has users in.
    "beat_schedule": {
        # Every 5 minutes; the "Celery beat heartbeat missing" alert fires when
        # its log line stops. Expires so a backlog does not pile up while no
        # worker is consuming.
        "beat-heartbeat": {
            "task": "rhesis.backend.jobs.heartbeat.beat_heartbeat",
            "schedule": 300.0,
            "options": {"expires": 240},
        },
        # Starts scheduled test runs. Expires so a backlog after downtime fires once,
        # not once per minute missed; a schedule's own missed-run handling covers the gap.
        "test-run-schedule-dispatch": {
            "task": "rhesis.backend.jobs.test_run_schedules.dispatch_due_schedules",
            "schedule": 60.0,
            "options": {"expires": 50},
        },
        "job-retention-sweep": {
            "task": "rhesis.backend.jobs.retention.sweep_expired_jobs",
            "schedule": crontab(hour=3, minute=0),
        },
        "trace-retention-sweep": {
            "task": "rhesis.backend.jobs.trace_retention.sweep_expired_traces",
            "schedule": crontab(hour=4, minute=0),
        },
        # Keeps the hosted spend cap priced from litellm's current price list.
        "refresh-model-prices": {
            "task": "rhesis.backend.jobs.model_prices.refresh_model_prices",
            "schedule": crontab(hour=2, minute=0),
        },
        # Always on: a no-op unless the EE audit log is installed.
        "audit-log-purge": {
            "task": "rhesis.backend.jobs.audit_retention.sweep_expired_audit_events",
            "schedule": crontab(hour=5, minute=0),
        },
    },
}

_ee_include, _ee_beat_schedule = ee_celery_jobs()
CELERY_CONFIG["include"] += _ee_include
CELERY_CONFIG["beat_schedule"].update(_ee_beat_schedule)

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
