"""Background jobs for the Rhesis backend.

Celery orchestration only. The units of work here are Celery tasks -- that is
Celery's own vocabulary and stays -- but in this codebase a "task" is a human
to-do (the ``task`` table, the Tasks screen), so the package is ``jobs``.
"""

import logging
import uuid
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from rhesis.backend.celery.core import app

# Import all task modules to ensure they're registered with Celery
# Import task functions after BaseJob is defined to avoid circular imports
from rhesis.backend.jobs import (
    embedding,  # noqa: F401
    endpoint,  # noqa: F401
    execution,  # noqa: F401
    file,  # noqa: F401
    garak,  # noqa: F401
    test_configuration,  # noqa: F401
    test_set,  # noqa: F401
    tracking,
    usage,  # noqa: F401
)
from rhesis.backend.jobs.base import (
    BaseJob,
    EmailEnabledJob,
    SilentJob,
    email_notification,
)
from rhesis.backend.jobs.embedding import (
    compute_source_graph_task,
    compute_test_set_graph_task,
    generate_embedding_task,
)
from rhesis.backend.jobs.enums import (
    DEFAULT_METRIC_WORKERS,
    DEFAULT_RESULT_STATUS,
    DEFAULT_RUN_STATUS_COMPLETED,
    DEFAULT_RUN_STATUS_FAILED,
    DEFAULT_RUN_STATUS_PROGRESS,
)
from rhesis.backend.jobs.execution.results import collect_results
from rhesis.backend.jobs.test_configuration import execute_test_configuration
from rhesis.backend.jobs.test_set import count_test_sets
from rhesis.backend.jobs.usage import accrue_usage
from rhesis.backend.jobs.utils import increment_test_run_progress
from rhesis.backend.notifications import email_service

logger = logging.getLogger(__name__)

# Type variable for task functions
T = TypeVar("T", bound=Callable)

__all__ = [
    # Core task system
    "app",
    # Classes
    "BaseJob",
    "EmailEnabledJob",
    "SilentJob",
    # Decorators
    "email_notification",
    # Helper functions
    "launch_job",
    "increment_test_run_progress",
    # Services
    "email_service",
    # Tasks
    "generate_embedding_task",
    "compute_test_set_graph_task",
    "compute_source_graph_task",
    "count_test_sets",
    "execute_test_configuration",
    "collect_results",
    "accrue_usage",
    # Constants
    "DEFAULT_METRIC_WORKERS",
    "DEFAULT_RESULT_STATUS",
    "DEFAULT_RUN_STATUS_PROGRESS",
    "DEFAULT_RUN_STATUS_COMPLETED",
    "DEFAULT_RUN_STATUS_FAILED",
]


def launch_job(
    task: T,
    *args: Any,
    current_user=None,
    celery_task_id: Optional[str] = None,
    db=None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    **kwargs: Any,
):
    """
    Launch a job with proper context from a FastAPI route.

    This helper automatically adds organization_id and user_id from current_user
    to the task context, removing the need to pass them explicitly.

    Also records a ``job`` row so the work shows up on the Jobs screen. That
    happens here rather than at each call site so a new job is visible without
    anyone remembering to register it. Recording is best-effort and never
    raises -- see :mod:`rhesis.backend.jobs.tracking`.

    Args:
        task: The Celery task to launch
        *args: Positional arguments to pass to the task
        current_user: User object from FastAPI dependency (must have id and organization_id)
        celery_task_id: Optional pre-generated Celery task ID.  Pass a UUID string
            to ensure the task is dispatched under a known ID so the caller can
            persist it before the worker starts.
        db: Optional SQLAlchemy Session. When supplied, project_id is read from
            db.info['_scope'] which is reliable for both sync and async route
            handlers. If omitted, falls back to the ContextVar (Celery / scripts).
        entity_type: Optional subject of the job (e.g. ``"TestSet"``), so the
            Jobs screen can offer a way back to whatever the job is about.
        entity_id: Optional id of that subject.
        **kwargs: Keyword arguments to pass to the task

    Returns:
        The AsyncResult from the launched task
    """
    # Prepare headers for tenant context (these won't interfere with task function signatures)
    headers = {}
    if current_user is not None:
        if hasattr(current_user, "id") and current_user.id is not None:
            headers["user_id"] = str(current_user.id)

        if hasattr(current_user, "organization_id") and current_user.organization_id is not None:
            headers["organization_id"] = str(current_user.organization_id)

    # Forward project_id to the Celery worker so it can re-bind the same scope
    # and stamp / filter by project correctly.
    #
    # Prefer Session.info['_scope'] (works for both sync and async route handlers)
    # over the ContextVar fallback (unreliable across anyio threadpool boundaries).
    scope_project_id = None
    if db is not None:
        session_scope = db.info.get("_scope")
        if session_scope is not None:
            scope_project_id = session_scope.project_id
    if scope_project_id is None:
        try:
            from rhesis.backend.app.scope import current_scope

            scope_project_id = current_scope().project_id
        except Exception:
            pass
    if scope_project_id:
        headers["project_id"] = str(scope_project_id)

    # A job row needs an id before dispatch, so mint one when the caller did
    # not supply it rather than letting Celery generate it after the fact.
    if celery_task_id is None and db is not None:
        celery_task_id = str(uuid.uuid4())

    if db is not None and celery_task_id:
        # Guarded here as well as inside create_job: the invariant is that
        # recording cannot stop a dispatch, and it should hold at this boundary
        # regardless of how create_job is implemented later.
        try:
            tracking.create_job(
                db,
                celery_task_id=celery_task_id,
                task_name=getattr(task, "name", "") or "",
                name=getattr(task, "display_name", None),
                organization_id=headers.get("organization_id"),
                user_id=headers.get("user_id"),
                project_id=headers.get("project_id"),
                entity_type=entity_type,
                entity_id=entity_id,
            )
        except Exception as exc:
            logger.warning(f"Could not record job row before dispatch: {exc}", exc_info=True)

    apply_kwargs: Dict[str, Any] = dict(args=args, kwargs=kwargs)
    if headers:
        apply_kwargs["headers"] = headers
    if celery_task_id:
        # Celery's own kwarg name, not ours: this is the framework boundary.
        apply_kwargs["task_id"] = celery_task_id

    if apply_kwargs.get("headers") or apply_kwargs.get("task_id"):
        return task.apply_async(**apply_kwargs)
    else:
        return task.delay(*args, **kwargs)
