"""Celery task for async endpoint exploration via Penelope.

Runs ``ExploreEndpointTool`` (backed by ``BackendEndpointTarget``) as a
background task so that external MCP clients can trigger exploration and
poll the result via ``GET /jobs/{task_id}``.

Follows the same async/polling pattern as ``generate_and_save_test_set``
and ``execute_test_configuration``.
"""

import json
import logging
import time
from typing import Any, Dict, List, Literal, Optional

from rhesis.backend.app import crud
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.utils.user_model_utils import get_user_generation_model
from rhesis.backend.celery.core import app
from rhesis.backend.tasks.architect.progress import publish_task_progress
from rhesis.backend.tasks.base import SilentTask
from rhesis.backend.tasks.endpoint.target import make_target_factory

# ExploreEndpointTool is imported lazily inside the task to avoid pulling
# litellm → gRPC into the Celery main process before forking.

logger = logging.getLogger(__name__)

ExplorationStrategy = Literal[
    "domain_probing",
    "capability_mapping",
    "boundary_discovery",
    "comprehensive",
]


@app.task(
    base=SilentTask,
    name="rhesis.backend.tasks.endpoint.explore.run_exploration_task",
    bind=True,
    display_name="Explore Endpoint",
)
def run_exploration_task(
    self,
    endpoint_id: str,
    strategy: Optional[ExplorationStrategy] = None,
    goal: Optional[str] = None,
    instructions: Optional[str] = None,
    scenario: Optional[str] = None,
    restrictions: Optional[str] = None,
    previous_findings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Explore an endpoint using Penelope and return structured findings.

    Args:
        endpoint_id: UUID of the endpoint to explore.
        strategy: Named exploration strategy or ``"comprehensive"`` to run
            all three strategies in sequence.  Either ``strategy`` or
            ``goal`` is required.
        goal: What to learn about the endpoint.  Required when no strategy
            is specified.
        instructions: Optional step-by-step probing instructions.
        scenario: Optional persona / situational context for Penelope.
        restrictions: Optional constraints to verify during exploration.
        previous_findings: Structured findings from a prior run; strategies
            build on them automatically.

    Returns:
        JSON-serializable dict containing the exploration findings,
        conversation summary, strategy used, duration, and endpoint_id.

    Raises:
        RuntimeError: When the exploration tool reports failure, so Celery
            marks the task ``FAILURE`` and ``get_job_status`` surfaces the
            error.
    """
    org_id, user_id, project_id = self.get_tenant_context()

    task_id = self.request.id or ""

    def _emit(
        status: str,
        label: str,
        *,
        step: Optional[int] = None,
        total: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Publish a progress event when the task is awaited by an architect.

        Resolves the architect session lazily on every call. The
        ``arch:task:<id>`` Redis key is set by ``register_awaiting_tasks``
        which runs near the END of the architect's turn — after the
        agent has dispatched this task. By the time we reach this call
        site (even ``"started"`` typically lands a beat later), the key
        is usually present. ``publish_task_progress`` silently no-ops
        when the key isn't (yet) there, so a missed start is harmless.
        """
        if not task_id:
            return
        publish_task_progress(
            task_id=task_id,
            status=status,
            label=label,
            step=step,
            total=total,
            duration_ms=duration_ms,
        )

    def _step(
        status: str,
        kind: str = "progress",
        *,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Update Celery task state and emit an architect progress event.

        Keeps the Celery ``meta`` status in sync with the WebSocket label
        so both the job-status API and the live chat bubble stay consistent.
        """
        self.update_state(
            state="PROGRESS",
            meta={"status": status, "endpoint_id": endpoint_id},
        )
        _emit(kind, status, duration_ms=duration_ms)

    label = strategy or "custom goal"
    _step(f"Starting exploration ({label})", "started")
    logger.info(
        "run_exploration_task started",
        extra={"endpoint_id": endpoint_id, "strategy": strategy, "org_id": org_id},
    )

    with get_db_with_tenant_variables(org_id or "", user_id or "", project_id or "") as db:
        user = crud.get_user(db, user_id=user_id)
        if user is None:
            raise RuntimeError(f"User {user_id} not found")
        model = get_user_generation_model(db, user)

    # Exploration: open a *separate* DB session that stays alive for the
    # entire multi-turn conversation, then create BackendEndpointTarget
    # instances from it via make_target_factory.
    _step("Connecting to endpoint")

    from rhesis.sdk.agents.tools import ExploreEndpointTool
    from rhesis.sdk.async_utils import run_sync

    start = time.monotonic()

    with get_db_with_tenant_variables(org_id or "", user_id or "", project_id or "") as db:
        target_factory = make_target_factory(
            org_id=org_id, user_id=user_id, db=db, project_id=project_id
        )

        tool = ExploreEndpointTool(
            target_factory=target_factory,
            model=model,
        )

        if strategy == "comprehensive":
            _step(
                "Running comprehensive exploration "
                "(domain probing + capability mapping + boundary discovery)"
            )
        elif strategy:
            _step(f"Running {strategy.replace('_', ' ')} strategy")
        else:
            _step("Exploring endpoint with custom goal")

        # Always attach the per-turn handler. It funnels through ``_emit``,
        # which itself no-ops when no architect session is awaiting this
        # task — so the handler is a cheap pass-through for non-architect
        # callers and avoids the start-of-task race that would otherwise
        # silently drop the entire progress trail.
        event_handlers: List[Any] = [_PenelopeProgressHandler(_emit)]

        result = run_sync(
            tool.execute(
                endpoint_id=endpoint_id,
                strategy=strategy,
                goal=goal or "",
                instructions=instructions,
                scenario=scenario,
                restrictions=restrictions,
                previous_findings=previous_findings,
                _event_handlers=event_handlers,
            )
        )

    duration_ms = int((time.monotonic() - start) * 1000)

    if not result.success:
        error_msg = result.error or "Exploration failed with no details"
        logger.error(
            "run_exploration_task failed: %s",
            error_msg,
            extra={"endpoint_id": endpoint_id, "strategy": strategy},
        )
        _step(f"Exploration failed: {error_msg}", "failed", duration_ms=duration_ms)
        raise RuntimeError(error_msg)

    # Parse the content JSON returned by ExploreEndpointTool.
    try:
        findings = json.loads(result.content) if isinstance(result.content, str) else result.content
    except (json.JSONDecodeError, TypeError):
        findings = {"raw": result.content}

    output = {
        "endpoint_id": endpoint_id,
        "strategy": strategy,
        "goal": goal,
        "duration_ms": duration_ms,
        **findings,
    }

    logger.info(
        "run_exploration_task completed",
        extra={
            "endpoint_id": endpoint_id,
            "strategy": strategy,
            "duration_ms": duration_ms,
            "org_id": org_id,
        },
    )
    _step(f"Exploration completed ({label})", "completed", duration_ms=duration_ms)
    return output


class _PenelopeProgressHandler:
    """Forward Penelope per-turn tool events as architect progress events.

    Penelope calls ``on_tool_start`` / ``on_tool_end`` for each probe
    sent to the target during exploration.  We surface those as
    user-friendly progress events on the architect session so the
    "Working…" spinner is accompanied by what the worker is actually
    doing right now (e.g. "Asking endpoint: 'What can you do?'").

    Only the user-facing send/receive turns are surfaced; analysis and
    bookkeeping tools are skipped to keep the trail readable.
    """

    # Penelope tool names worth surfacing to the user.  Other tools
    # (reasoning, scoring, internal bookkeeping) are intentionally
    # skipped — they'd add noise without telling the user anything
    # they care about.
    _USER_FACING_TOOLS = {"send_message_to_target"}

    def __init__(self, emit: Any) -> None:
        self._emit = emit
        self._turn = 0

    async def on_tool_start(
        self,
        *,
        tool_name: str,
        arguments: Dict[str, Any],
        reasoning: Optional[str] = None,
        **_: Any,
    ) -> None:
        if tool_name not in self._USER_FACING_TOOLS:
            return
        self._turn += 1
        message = arguments.get("message") if isinstance(arguments, dict) else None
        snippet = _truncate(str(message)) if message else ""
        label = f"Turn {self._turn}: probing endpoint"
        if snippet:
            label = f"Turn {self._turn}: {snippet}"
        self._emit("progress", label, step=self._turn)

    async def on_tool_end(
        self,
        *,
        tool_name: str,
        result: Any,
        **_: Any,
    ) -> None:
        # Penelope's send_message_to_target completes for every turn —
        # we already announced the start, no need to re-emit on end.
        return


def _truncate(text: str, limit: int = 80) -> str:
    """Trim ``text`` to ``limit`` chars, appending an ellipsis if cut."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
