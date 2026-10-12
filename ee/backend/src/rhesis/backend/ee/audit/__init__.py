"""Enterprise audit log: the sink that stores ``AuditRecorded`` events, and the read API.

Change capture lives in core (``app/models/audit_capture.py``) and stays idle
until :func:`register_audit` registers ``FeatureName.AUDIT_LOG``.
"""

from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.ee.audit.sink import AuditSink
from rhesis.backend.events import register_sink

_sink_registered = False


def register_audit() -> None:
    """Register the feature and its sink. Idempotent.

    Called from ``bootstrap_providers()``, which both the API process and the
    Celery workers run, so changes a job makes are recorded too.
    """
    global _sink_registered
    FeatureRegistry.register(
        Feature(
            name=FeatureName.AUDIT_LOG,
            display_name="Audit Log",
            description="Append-only record of every change, sign-in and denial.",
        )
    )
    if not _sink_registered:
        register_sink(AuditSink())
        _sink_registered = True
