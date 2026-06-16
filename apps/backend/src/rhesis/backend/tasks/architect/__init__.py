"""Architect agent task package.

Submodules are imported lazily to avoid a circular import:

    worker → tasks → tasks.endpoint.explore → tasks.architect.progress
    → (this __init__) → tasks.architect.chat → worker  (boom)

Direct submodule imports still work and are preferred::

    from rhesis.backend.tasks.architect.chat import architect_chat_task
    from rhesis.backend.tasks.architect.progress import publish_task_progress
"""

import importlib as _importlib

_LAZY_MAP = {
    "architect_chat_task": "rhesis.backend.tasks.architect.chat",
    "register_awaiting_tasks": "rhesis.backend.tasks.architect.monitor",
    "lookup_session_for_task": "rhesis.backend.tasks.architect.progress",
    "publish_task_progress": "rhesis.backend.tasks.architect.progress",
    "_conversation_telemetry_context": "rhesis.backend.tasks.architect.telemetry",
    "_load_session_trace_id": "rhesis.backend.tasks.architect.telemetry",
}

__all__ = list(_LAZY_MAP)


def __getattr__(name: str):
    if name in _LAZY_MAP:
        mod = _importlib.import_module(_LAZY_MAP[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
