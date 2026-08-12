"""Declarative registry of in-app notification kinds.

Adding a notification for a new completed job means adding one entry here --
nothing in ``tasks/base.py`` or the router changes. See ``service.notify()``
for how a catalog entry turns into a row + websocket event.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.models.enums import NotificationEventType, NotificationSection


@dataclass(frozen=True)
class RenderedNotification:
    title: str
    is_failure: bool = False
    body: Optional[str] = None
    entity_id: Optional[str] = None
    #: Extra ids beyond entity_id (e.g. a Garak import's several test sets),
    #: stored in Notification.payload["entity_ids"] for the frontend to
    #: highlight every affected row, not just one.
    entity_ids: Optional[list] = None


# A render function receives the Celery task instance (for self.request.kwargs /
# .headers / .get_tenant_context()), the task's return value, and the exception
# message (None on success). The caller normalizes a failed or non-dict return
# to ``{}`` (see BaseTask._send_task_completion_notification), so renderers can
# read keys off it without guarding -- but must not assume any key is present.
RenderFn = Callable[[Any, Dict[str, Any], Optional[str]], RenderedNotification]


@dataclass(frozen=True)
class NotificationKind:
    #: A NotificationEventType.<Resource> member. Typed as ``str`` since
    #: NotificationEventType is a namespace, not itself an enum -- see its
    #: docstring in models/enums.py.
    event_type: str
    section: NotificationSection
    entity_type: Optional[str]
    #: None for a kind emitted by a direct notify() caller (e.g. a router) --
    #: only the Celery-hook caller (tasks/base.py) ever invokes this.
    render: Optional[RenderFn] = None


def _task_kwargs(task) -> Dict[str, Any]:
    return getattr(task.request, "kwargs", None) or {}


def _task_headers(task) -> Dict[str, Any]:
    return getattr(task.request, "headers", None) or {}


def _render_generation_completed(task, retval, error) -> RenderedNotification:
    test_set_id = retval.get("test_set_id") or _task_kwargs(task).get("test_set_id")
    if error:
        return RenderedNotification(
            title="Test set generation failed", is_failure=True, entity_id=test_set_id
        )
    name = retval.get("test_set_name") or "Test set"
    count = retval.get("num_tests_generated", 0)
    return RenderedNotification(
        title=f'"{name}" is ready',
        body=f"{count} tests generated",
        entity_id=test_set_id,
    )


def _render_garak_import_completed(task, retval, error) -> RenderedNotification:
    if error:
        return RenderedNotification(title="Garak import failed", is_failure=True)
    test_sets = retval.get("test_sets", [])
    return RenderedNotification(
        title=f"Imported {retval.get('total_test_sets', len(test_sets))} Garak test set(s)",
        body=f"{retval.get('total_tests', 0)} tests total",
        # One notification covers the whole batch, so every created id goes in
        # entity_ids and all of their rows highlight.
        entity_ids=[
            ts["test_set_id"] for ts in test_sets if isinstance(ts, dict) and ts.get("test_set_id")
        ],
    )


def _render_garak_sync_completed(task, retval, error) -> RenderedNotification:
    test_set_id = _task_kwargs(task).get("test_set_id")
    if error:
        return RenderedNotification(
            title="Garak sync failed", is_failure=True, entity_id=test_set_id
        )
    return RenderedNotification(
        title="Garak sync complete",
        body=f"{retval.get('added', 0)} added, {retval.get('removed', 0)} removed",
        entity_id=test_set_id,
    )


def _render_execution_completed(task, retval, error) -> RenderedNotification:
    test_run_id = retval.get("test_run_id") or _task_headers(task).get("test_run_id")
    if error:
        return RenderedNotification(title="Test run failed", is_failure=True, entity_id=test_run_id)
    passed = retval.get("tests_passed", 0)
    failed = retval.get("tests_failed", 0)
    name = retval.get("test_set_name") or "Test run"
    return RenderedNotification(
        title=f'"{name}" finished',
        body=f"{passed} passed, {failed} failed",
        entity_id=test_run_id,
    )


NOTIFICATION_CATALOG: Dict[str, NotificationKind] = {
    NotificationEventType.TestSet.GENERATION_COMPLETED: NotificationKind(
        event_type=NotificationEventType.TestSet.GENERATION_COMPLETED,
        section=NotificationSection.TEST_SETS,
        entity_type=EntityType.TEST_SET.value,
        render=_render_generation_completed,
    ),
    NotificationEventType.TestSet.GARAK_IMPORT_COMPLETED: NotificationKind(
        event_type=NotificationEventType.TestSet.GARAK_IMPORT_COMPLETED,
        section=NotificationSection.TEST_SETS,
        entity_type=EntityType.TEST_SET.value,
        render=_render_garak_import_completed,
    ),
    NotificationEventType.TestSet.GARAK_SYNC_COMPLETED: NotificationKind(
        event_type=NotificationEventType.TestSet.GARAK_SYNC_COMPLETED,
        section=NotificationSection.TEST_SETS,
        entity_type=EntityType.TEST_SET.value,
        render=_render_garak_sync_completed,
    ),
    NotificationEventType.TestRun.EXECUTION_COMPLETED: NotificationKind(
        event_type=NotificationEventType.TestRun.EXECUTION_COMPLETED,
        section=NotificationSection.TEST_RUNS,
        entity_type=EntityType.TEST_RUN.value,
        render=_render_execution_completed,
    ),
    NotificationEventType.Task.ASSIGNED: NotificationKind(
        event_type=NotificationEventType.Task.ASSIGNED,
        section=NotificationSection.TASKS,
        entity_type=EntityType.TASK.value,
        # Emitted directly from task_notification.py, not a Celery hook.
    ),
}
