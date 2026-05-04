"""Celery task for async endpoint exploration via Penelope.

Runs ``ExploreEndpointTool`` (backed by ``BackendEndpointTarget``) as a
background task so that external MCP clients can trigger exploration and
poll the result via ``GET /jobs/{task_id}``.

Follows the same async/polling pattern as ``generate_and_save_test_set``
and ``execute_test_configuration``.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Literal, Optional

from rhesis.backend.app import crud
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.utils.user_model_utils import get_user_generation_model
from rhesis.backend.celery.core import app
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
    org_id, user_id = self.get_tenant_context()

    label = strategy or "custom goal"
    self.update_state(
        state="PROGRESS",
        meta={"status": f"Starting exploration ({label})", "endpoint_id": endpoint_id},
    )
    logger.info(
        "run_exploration_task started",
        extra={"endpoint_id": endpoint_id, "strategy": strategy, "org_id": org_id},
    )

    with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
        user = crud.get_user(db, user_id=user_id)
        if user is None:
            raise RuntimeError(f"User {user_id} not found")
        model = get_user_generation_model(db, user)

    # Exploration: open a *separate* DB session that stays alive for the
    # entire multi-turn conversation, then create BackendEndpointTarget
    # instances from it via make_target_factory.
    self.update_state(
        state="PROGRESS",
        meta={"status": "Connecting to endpoint", "endpoint_id": endpoint_id},
    )

    from rhesis.sdk.agents.tools import ExploreEndpointTool

    start = time.monotonic()

    with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
        target_factory = make_target_factory(org_id=org_id, user_id=user_id, db=db)

        tool = ExploreEndpointTool(
            target_factory=target_factory,
            model=model,
        )

        if strategy == "comprehensive":
            self.update_state(
                state="PROGRESS",
                meta={
                    "status": "Running comprehensive exploration (domain probing + "
                    "capability mapping + boundary discovery)",
                    "endpoint_id": endpoint_id,
                },
            )
        elif strategy:
            self.update_state(
                state="PROGRESS",
                meta={
                    "status": f"Running {strategy.replace('_', ' ')} strategy",
                    "endpoint_id": endpoint_id,
                },
            )
        else:
            self.update_state(
                state="PROGRESS",
                meta={
                    "status": "Exploring endpoint with custom goal",
                    "endpoint_id": endpoint_id,
                },
            )

        result = asyncio.run(
            tool.execute(
                endpoint_id=endpoint_id,
                strategy=strategy,
                goal=goal or "",
                instructions=instructions,
                scenario=scenario,
                restrictions=restrictions,
                previous_findings=previous_findings,
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
    return output
