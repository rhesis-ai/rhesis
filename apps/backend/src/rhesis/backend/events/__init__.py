"""Shared emit path for user-facing job logs, the enterprise audit trail, and
OTel export. Only the job-logging sink ships today -- see ``sinks/base.py``
for what a future sink needs to satisfy, and ``dispatcher.py`` for delivery
policy.

Public surface: ``emit``, ``register_sink``. Event types live in ``types.py``
and are imported directly by callers that construct them.
"""

from rhesis.backend.events.dispatcher import emit, register_sink
from rhesis.backend.events.sinks.activity_log import ActivityLogSink

__all__ = ["emit", "register_sink"]

# A core (MIT) sink ships unconditionally and self-registers on import,
# unlike an EE sink -- which registers from ee/__init__.py:bootstrap(),
# gated on a FeatureName, exactly as SSO/API_CLIENTS/RBAC do today.
register_sink(ActivityLogSink())
