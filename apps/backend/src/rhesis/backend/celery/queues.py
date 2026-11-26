"""Every Celery queue, the rule for what goes on it, and the jobs routed there.

Plain data with no imports, so tools such as apps/worker/queue_monitor.py can read it
without building the backend's settings.
"""

# Every queue, the rule for what goes on it, and the jobs routed there. A new job goes on
# the queue whose rule it fits; tests/backend/jobs/test_task_routes.py fails until it
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
