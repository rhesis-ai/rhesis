"""EE Celery jobs, merged into core's Celery config by ``app/ee_bootstrap.ee_celery_jobs``.

Plain data, so reading it imports nothing else.
"""

INCLUDE = ["rhesis.backend.ee.audit.streaming.jobs"]

BEAT_SCHEDULE = {
    # Sends new audit events to each org's streaming destinations. Expires so a
    # backlog does not pile up while no worker is consuming.
    "audit-stream-delivery": {
        "task": "rhesis.backend.ee.audit.streaming.jobs.deliver_audit_streams",
        "schedule": 15.0,
        "options": {"expires": 12},
    },
}
