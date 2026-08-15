"""Architect agent task package.

Submodules are imported lazily to avoid a circular import:

    worker → tasks → tasks.endpoint.explore → tasks.architect.progress
    → (this __init__) → tasks.architect.chat → worker  (boom)

Direct submodule imports still work and are preferred::

    from rhesis.backend.jobs.architect.chat import architect_chat_task
    from rhesis.backend.jobs.architect.progress import publish_task_progress
"""

import importlib as _importlib

_LAZY_MAP = {
    "architect_chat_task": "rhesis.backend.jobs.architect.chat",
    "register_awaiting_tasks": "rhesis.backend.jobs.architect.monitor",
    "lookup_session_for_task": "rhesis.backend.jobs.architect.progress",
    "publish_task_progress": "rhesis.backend.jobs.architect.progress",
    "_conversation_telemetry_context": "rhesis.backend.jobs.architect.telemetry",
    "_load_session_trace_id": "rhesis.backend.jobs.architect.telemetry",
}

__all__ = list(_LAZY_MAP)


def __getattr__(name: str):
    if name in _LAZY_MAP:
        mod = _importlib.import_module(_LAZY_MAP[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
