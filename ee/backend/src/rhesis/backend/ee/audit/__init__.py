"""Enterprise audit log: the sink that stores ``AuditRecorded`` events, and the read API.

Change capture lives in core (``app/models/audit_capture.py``) and stays idle
until :func:`register_audit` registers ``FeatureName.AUDIT_LOG``.
"""

from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.ee.audit.sink import AuditSink
from rhesis.backend.events import register_sink

_sink_registered = False


def register_audit() -> None:
    """Register the feature, its sink and the export cleanup. Idempotent.

    Called from ``bootstrap_providers()``, which both the API process and the
    Celery workers run, so changes a job makes are recorded too.
    """
    # Here, not at the top: the export package imports this one.
    from rhesis.backend.app.services.audit_retention import register_export_cleanup
    from rhesis.backend.ee.audit.export.cleanup import delete_expired_exports

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
    register_export_cleanup(delete_expired_exports)
