"""Shared emit path for user-facing job logs, live WebSocket push, the
enterprise audit trail, and OTel export. Two core sinks ship today -- see
``sinks/base.py`` for what a future sink needs to satisfy, and
``dispatcher.py`` for delivery policy.

Public surface: ``emit``, ``register_sink``. Event types live in ``types.py``
and are imported directly by callers that construct them.
"""

from rhesis.backend.events.dispatcher import emit, register_sink
from rhesis.backend.events.sinks.activity_log import ActivityLogSink
from rhesis.backend.events.sinks.websocket import WebSocketSink

__all__ = ["emit", "register_sink"]

# Core (MIT) sinks ship unconditionally and self-register on import, unlike
# an EE sink -- which registers from ee/__init__.py:bootstrap(), gated on a
# FeatureName, exactly as SSO/API_CLIENTS/RBAC do today.
register_sink(ActivityLogSink())
register_sink(WebSocketSink())
