"""Event-driven monitoring for background tasks awaited by the Architect.

Instead of a polling loop, this module uses a Celery ``task_postrun``
signal.  Every time *any* Celery task finishes the signal handler does
a single O(1) Redis lookup to check whether the completed task is one
the Architect is waiting for.  If it is, an atomic counter is
decremented and — when it reaches zero — the Architect is automatically
resumed with the results.

Redis keys (all with a 2-hour TTL unless noted):

* ``arch:task:<id>``  — JSON with session context.  ``<id>`` can be a
  Celery task ID **or** a ``test_run_id``.  For test execution the
  agent registers the ``test_run_id`` because the parent Celery task
  (``execute_test_configuration``) finishes before the chord callback
  (``collect_results``) which carries the actual results.
* ``arch:count:<session_id>``  — integer countdown of remaining tasks
* ``arch:result:<session_id>:<task_id>``  — individual task result
* ``arch:early:<id>``  — result of a task that completed *before*
  ``register_awaiting_tasks`` was called (5-minute TTL).  Consumed by
  ``register_awaiting_tasks`` immediately after writing the ``arch:task``
  keys, closing the race window between task dispatch and registration.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import redis as _redis_lib
from celery.signals import task_postrun

from rhesis.backend.app.config.settings import get_redis_settings
from rhesis.backend.app.constants import ARCHITECT_RESUME_PREFIX

logger = logging.getLogger(__name__)

_KEY_TTL = 7200  # 2 hours
_EARLY_TTL = 300  # 5 minutes — long enough for the agent turn to finish

_redis_pool: Optional[_redis_lib.ConnectionPool] = None


def _get_redis() -> _redis_lib.Redis:
    """Return a Redis client reusing a shared connection pool."""
    global _redis_pool
    if _redis_pool is None:
        url = get_redis_settings().broker_url
        _redis_pool = _redis_lib.ConnectionPool.from_url(url)
    return _redis_lib.Redis(connection_pool=_redis_pool)


# ------------------------------------------------------------------
# Serialisation helper
# ------------------------------------------------------------------


def _serialise_retval(retval: Any) -> Any:
    try:
        return (
            retval
            if isinstance(retval, (dict, list, str, int, float, bool, type(None)))
            else str(retval)
        )
    except Exception:
        return str(retval)


# ------------------------------------------------------------------
# Public API — called from chat.py
# ------------------------------------------------------------------


def register_awaiting_tasks(
    session_id: str,
    task_ids: List[str],
    org_id: str,
    user_id: str,
    auto_approve: bool = False,
    project_id: str | None = None,
) -> None:
    """Store the set of task IDs the Architect is waiting for."""
    r = _get_redis()
    pipe = r.pipeline()

    context_dict = {
        "session_id": session_id,
        "org_id": org_id,
        "user_id": user_id,
        "auto_approve": auto_approve,
        "project_id": project_id,
    }
    context = json.dumps(context_dict)

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

    _drain_early_completions(r, session_id, task_ids, context_dict)


# ------------------------------------------------------------------
# Early-completion handling (race-condition fix)
# ------------------------------------------------------------------


def _store_early_completion(
    r: _redis_lib.Redis,
    task_id: str,
    state: str,
    retval: Any,
) -> List[str]:
    """Stash a result that arrived before registration.

    Only stores results that look like they came from the test execution
    or generation pipeline (retval dict with ``test_run_id`` or
    ``test_set_id``).  Returns the list of Redis keys written, empty if
    nothing was stored.
    """
    if not isinstance(retval, dict):
        return []

    test_run_id = retval.get("test_run_id")
    test_set_id = retval.get("test_set_id")
    if not test_run_id and not test_set_id:
        return []

    data = json.dumps(
        {
            "task_id": task_id,
            "state": state,
            "result": _serialise_retval(retval),
        }
    )

    keys: List[str] = []
    pipe = r.pipeline()

    key = f"arch:early:{task_id}"
    pipe.set(key, data, ex=_EARLY_TTL)
    keys.append(key)

    # Only store the test_run_id alt key for *final* execution results
    # (same guard as _resolve_awaiting_key) — execute_test_configuration
    # also carries test_run_id but without execution_status/tests_passed,
    # and matching it would resume the architect with incomplete data.
    is_final = "execution_status" in retval or "tests_passed" in retval
    if test_run_id and is_final and str(test_run_id) != str(task_id):
        key = f"arch:early:{test_run_id}"
        pipe.set(key, data, ex=_EARLY_TTL)
        keys.append(key)

    pipe.execute()

    logger.debug(
        "Stored early completion for task %s (keys: %s)",
        task_id,
        keys,
    )
    return keys


def _drain_early_completions(
    r: _redis_lib.Redis,
    session_id: str,
    task_ids: List[str],
    context: Dict[str, Any],
) -> None:
    """Check whether any registered tasks already completed.

    Called immediately after ``register_awaiting_tasks`` writes the
    ``arch:task`` and ``arch:count`` keys.  For each registered ID, if
    an ``arch:early:<id>`` key exists, process it as if ``_on_task_done``
    had just fired.
    """
    count_key = f"arch:count:{session_id}"

    for tid in task_ids:
        early_key = f"arch:early:{tid}"
        early_raw = r.get(early_key)
        if early_raw is None:
            continue

        # Claim the registration key so _on_task_done's re-check
        # cannot double-process the same task.
        task_key = f"arch:task:{tid}"
        if not r.delete(task_key):
            r.delete(early_key)
            continue

        r.delete(early_key)
        entry = json.loads(early_raw)

        result_key = f"arch:result:{session_id}:{entry['task_id']}"
        r.set(result_key, early_raw, ex=_KEY_TTL)

        remaining = r.decr(count_key)

        logger.info(
            "Drained early completion for task %s (%s), %d remaining for session %s",
            tid,
            entry["task_id"],
            max(remaining, 0),
            session_id,
        )

        if remaining <= 0:
            _resume_architect(session_id, context, r)
            return


# ------------------------------------------------------------------
# Result summarisation
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


def _process_task_completion(
    r: _redis_lib.Redis,
    matched_key: str,
    task_id: str,
    state: str,
    retval: Any,
) -> None:
    """Claim an ``arch:task`` key and record the result.

    Uses ``r.delete`` as the claim: only the caller whose delete
    returns >= 1 proceeds, preventing double-processing when
    ``_on_task_done``'s re-check races with ``_drain_early_completions``.
    """
    raw = r.get(matched_key)
    if raw is None:
        return
    if not r.delete(matched_key):
        return

    context = json.loads(raw)
    session_id = context["session_id"]

    result_key = f"arch:result:{session_id}:{task_id}"
    r.set(
        result_key,
        json.dumps({"task_id": task_id, "state": state, "result": _serialise_retval(retval)}),
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

    if matched_key is not None:
        _process_task_completion(r, matched_key, task_id, state, retval)
        return

    # No registration yet.  If the result looks like a pipeline task
    # (execution or generation), stash it so register_awaiting_tasks
    # can pick it up — this closes the race where the task finishes
    # before the architect turn registers its awaited IDs.
    early_keys = _store_early_completion(r, task_id, state, retval)
    if not early_keys:
        return

    # Re-check: registration may have appeared between our first
    # lookup and the early-result write.
    matched_key = _resolve_awaiting_key(r, task_id, retval)
    if matched_key is not None:
        for ek in early_keys:
            r.delete(ek)
        _process_task_completion(r, matched_key, task_id, state, retval)


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
        f"{ARCHITECT_RESUME_PREFIX} The background tasks you were waiting "
        "for have finished. Here are the results:\n"
        + "\n".join(f"- {s}" for s in summaries)
        + "\nPlease continue with the next steps in the plan."
    )

    logger.info(
        "All tasks ready for session %s, auto-resuming architect",
        session_id,
    )

    from rhesis.backend.jobs.architect.chat import architect_chat_task

    architect_chat_task.apply_async(
        kwargs={
            "session_id": session_id,
            "user_message": message,
            "auto_approve": context.get("auto_approve"),
        },
        headers={
            "organization_id": context.get("org_id") or "",
            "user_id": context.get("user_id") or "",
            "project_id": context.get("project_id") or "",
        },
    )
