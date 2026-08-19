"""English rendering of lifecycle events, shared by every sink that needs it.

Kept separate from any one sink so ``ActivityLogSink`` and ``WebSocketSink``
agree on what a ``JobFailed`` event says -- one source of truth for the
message a human reads, whether it lands in ``activity_log`` or a live push.
"""

from typing import Tuple

from rhesis.backend.events.types import (
    JobCancelled,
    JobCompleted,
    JobFailed,
    JobQueued,
    JobRetried,
    JobStarted,
    PlatformEvent,
)


def render(event: PlatformEvent) -> Tuple[str, str]:
    """(level, message) for a lifecycle event. ``ActivityLogged`` carries its
    own and is not rendered here.
    """
    if isinstance(event, JobQueued):
        return "info", "Job queued"
    if isinstance(event, JobStarted):
        return "info", "Job started"
    if isinstance(event, JobCompleted):
        return "info", "Job completed successfully"
    if isinstance(event, JobFailed):
        return "error", f"Job failed: {event.error_type}: {event.error_message}"
    if isinstance(event, JobRetried):
        return "warning", f"Retrying (attempt {event.attempt})"
    if isinstance(event, JobCancelled):
        return "info", "Job cancelled"
    raise TypeError(f"Cannot render {type(event).__name__}")
