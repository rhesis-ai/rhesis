"""Architect agent task package.

Re-exports the public API so existing import paths continue to work:

    from rhesis.backend.tasks.architect import architect_chat_task
    from rhesis.backend.tasks.architect import register_awaiting_tasks
"""

from rhesis.backend.tasks.architect.chat import architect_chat_task
from rhesis.backend.tasks.architect.monitor import register_awaiting_tasks
from rhesis.backend.tasks.architect.progress import (
    lookup_session_for_task,
    publish_task_progress,
)
from rhesis.backend.tasks.architect.telemetry import (
    _conversation_telemetry_context,
    _load_session_trace_id,
)

__all__ = [
    "architect_chat_task",
    "register_awaiting_tasks",
    "lookup_session_for_task",
    "publish_task_progress",
    "_conversation_telemetry_context",
    "_load_session_trace_id",
]
