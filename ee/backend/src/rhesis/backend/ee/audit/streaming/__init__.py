"""Streaming the audit log to an org's own destinations (webhook, Splunk HEC, Datadog).

No outbox: ``audit_event`` is already durable, so each destination keeps a
cursor on ``(recorded_at, id)`` and a job on beat sends what comes after it.
Delivery is at least once; receivers drop duplicates by event id.
"""
