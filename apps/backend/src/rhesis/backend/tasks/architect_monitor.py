"""Event-driven monitoring for background tasks awaited by the Architect.

Instead of a polling loop, this module uses a Celery ``task_postrun``
signal.  Every time *any* Celery task finishes the signal handler does
a single O(1) Redis lookup to check whether the completed task is one
the Architect is waiting for.  If it is, an atomic counter is
decremented and — when it reaches zero — the Architect is automatically
resumed with the results.

Redis keys (all with a 2-hour TTL):

* ``arch:task:<id>``  — JSON with session context.  ``<id>`` can be a
  Celery task ID **or** a ``test_run_id``.  For test execution the
  agent registers the ``test_run_id`` because the parent Celery task
  (``execute_test_configuration``) finishes before the chord callback
  (``collect_results``) which carries the actual results.
* ``arch:count:<session_id>``  — integer countdown of remaining tasks
* ``arch:result:<session_id>:<task_id>``  — individual task result
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import redis as _redis_lib
from celery.signals import task_postrun

logger = logging.getLogger(__name__)

_KEY_TTL = 7200  # 2 hours

_redis_pool: Optional[_redis_lib.ConnectionPool] = None


def _get_redis() -> _redis_lib.Redis:
    """Return a Redis client reusing a shared connection pool."""
    global _redis_pool
    if _redis_pool is None:
        url = os.getenv("BROKER_URL") or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_pool = _redis_lib.ConnectionPool.from_url(url)
    return _redis_lib.Redis(connection_pool=_redis_pool)


# ------------------------------------------------------------------
# Public API — called from architect.py
# ------------------------------------------------------------------


def register_awaiting_tasks(
    session_id: str,
    task_ids: List[str],
    org_id: str,
    user_id: str,
    auto_approve: bool = False,
) -> None:
    """Store the set of task IDs the Architect is waiting for."""
    r = _get_redis()
    pipe = r.pipeline()

    context = json.dumps(
        {
            "session_id": session_id,
            "org_id": org_id,
            "user_id": user_id,
            "auto_approve": auto_approve,
        }
    )

    for tid in task_ids:
        pipe.set(f"arch:task:{tid}", context, ex=_KEY_TTL)

    count_key = f"arch:count:{session_id}"
    pipe.set(count_key, len(task_ids), ex=_KEY_TTL)
    pipe.execute()

    logger.info(
        "Registered %d awaiting task(s) for session %s: %s",
        len(task_ids),
        session_id,
        task_ids,
    )


# ------------------------------------------------------------------
# Result summarisation (reused from previous implementation)
# ------------------------------------------------------------------


def _summarize_result(task_id: str, state: str, result: Any) -> str:
    """Build a human-readable summary line for a completed task."""
    if state == "SUCCESS" and isinstance(result, dict):
        test_set_id = result.get("test_set_id")
        test_run_id = result.get("test_run_id")
        if test_set_id:
            name = result.get("name") or result.get("test_set_name", "test set")
            count = result.get(
                "test_count",
                result.get("num_tests_generated", "?"),
            )
            return (
                f"Test set '{name}' generated successfully "
                f"({count} tests). test_set_id={test_set_id}"
            )
        if test_run_id:
            name = result.get("test_set_name", "test run")
            total = result.get("total_tests", "?")
            passed = result.get("tests_passed", "?")
            failed = result.get("tests_failed", "?")
            return (
                f"Test run for '{name}' completed "
                f"({passed} passed, {failed} failed out of "
                f"{total} tests). test_run_id={test_run_id}"
            )
        return f"Task {task_id} completed: {result}"

    if state == "SUCCESS":
        return f"Task {task_id} completed: {result}"

    error = str(result) if result else "unknown error"
    return f"Task {task_id} failed: {error}"


# ------------------------------------------------------------------
# Signal handler — fires on every task completion
# ------------------------------------------------------------------


def _resolve_awaiting_key(
    r: _redis_lib.Redis,
    task_id: str,
    retval: Any,
) -> Optional[str]:
    """Find the Redis key that maps this completed task to an architect session.

    Checks in order:
    1. Direct task-ID match (``arch:task:<task_id>``)
    2. If the result is a *final* execution result containing both
       ``test_run_id`` and ``execution_status`` (set only by
       ``collect_results``), try ``arch:task:<test_run_id>``.
       This avoids a premature match when the parent
       ``execute_test_configuration`` task finishes — that task
       also carries ``test_run_id`` but without ``execution_status``.
    """
    key = f"arch:task:{task_id}"
    if r.exists(key):
        return key

    if isinstance(retval, dict):
        test_run_id = retval.get("test_run_id")
        is_final = "execution_status" in retval or "tests_passed" in retval
        if test_run_id and is_final:
            alt_key = f"arch:task:{test_run_id}"
            if r.exists(alt_key):
                return alt_key

    return None


@task_postrun.connect
def _on_task_done(
    sender=None,
    task_id=None,
    state=None,
    retval=None,
    **kwargs,
) -> None:
    """Check whether a just-finished task is awaited by the Architect."""
    if task_id is None:
        return

    r = _get_redis()
    matched_key = _resolve_awaiting_key(r, task_id, retval)
    if matched_key is None:
        return  # not an awaited task — fast exit

    raw = r.get(matched_key)
    if raw is None:
        return
    context = json.loads(raw)
    session_id = context["session_id"]
    r.delete(matched_key)

    try:
        serialisable = (
            retval
            if isinstance(retval, (dict, list, str, int, float, bool, type(None)))
            else str(retval)
        )
    except Exception:
        serialisable = str(retval)

    result_key = f"arch:result:{session_id}:{task_id}"
    r.set(
        result_key,
        json.dumps({"task_id": task_id, "state": state, "result": serialisable}),
        ex=_KEY_TTL,
    )

    count_key = f"arch:count:{session_id}"
    remaining = r.decr(count_key)

    logger.info(
        "Architect task %s finished (state=%s, key=%s), %d remaining for session %s",
        task_id,
        state,
        matched_key,
        max(remaining, 0),
        session_id,
    )

    if remaining > 0:
        return

    _resume_architect(session_id, context, r)


# ------------------------------------------------------------------
# Resume the Architect conversation
# ------------------------------------------------------------------


def _resume_architect(
    session_id: str,
    context: Dict[str, Any],
    r: _redis_lib.Redis,
) -> None:
    """Gather stored results and dispatch a new architect turn."""
    pattern = f"arch:result:{session_id}:*"
    result_keys = list(r.scan_iter(pattern, count=100))
    summaries: List[str] = []

    for key in result_keys:
        raw = r.get(key)
        if raw:
            entry = json.loads(raw)
            summaries.append(_summarize_result(entry["task_id"], entry["state"], entry["result"]))
        r.delete(key)

    r.delete(f"arch:count:{session_id}")

    message = (
        "[TASK_COMPLETED] The background tasks you were waiting "
        "for have finished. Here are the results:\n"
        + "\n".join(f"- {s}" for s in summaries)
        + "\nPlease continue with the next steps in the plan."
    )

    logger.info(
        "All tasks ready for session %s, auto-resuming architect",
        session_id,
    )

    from rhesis.backend.tasks.architect import architect_chat_task

    architect_chat_task.apply_async(
        kwargs={
            "session_id": session_id,
            "user_message": message,
            "auto_approve": context.get("auto_approve"),
        },
        headers={
            "organization_id": context.get("org_id", ""),
            "user_id": context.get("user_id", ""),
        },
    )
