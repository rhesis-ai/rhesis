"""Architect chat orchestration pipeline.

The ``@endpoint``-decorated ``run_architect_turn`` registers the function
with the SDK connector so it can be invoked via the Playground and test
runs.  The Celery task (``architect_chat_task``) calls it directly,
constructing an :class:`~rhesis.sdk.context.EndpointContext` to carry
tenant identity.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel

from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.schemas.websocket import EventType
from rhesis.backend.app.services.architect.attachments import process_attachments
from rhesis.backend.app.services.architect.event_handler import WebSocketEventHandler
from rhesis.backend.app.services.mcp.agents import get_agent_event_handlers
from rhesis.backend.app.utils import observability as _observability  # noqa: F401
from rhesis.sdk.context import EndpointContext
from rhesis.sdk.decorators import endpoint, observe

logger = logging.getLogger(__name__)


class ArchitectChatResult(BaseModel):
    """Typed result returned by one architect chat turn."""

    content: str
    session_id: str
    mode: str
    needs_confirmation: bool
    auto_approve_all: bool
    awaiting_task: bool
    plan: Optional[str]
    pending_tasks: List[Dict[str, Any]]


@observe()
async def prepare_and_load_session(
    organization_id: str,
    user_id: str,
    message: str,
    attachments: Optional[Dict[str, Any]],
    persist_user_message: bool,
    session_id: Optional[str],
    project_id: Optional[str] = None,
) -> tuple[str, Dict[str, Any]]:
    """Create or validate the session and load its full state in one DB context.

    Returns ``(resolved_session_id, session_data)`` where ``session_data``
    contains conversation_history, mode, plan_data, agent_state, and
    session_has_title.
    """
    from rhesis.backend.app import crud, schemas

    with get_db_with_tenant_variables(organization_id, user_id, project_id or "") as db:
        if session_id:
            db_session = crud.get_architect_session_detail(
                db,
                session_id=UUID(session_id),
                organization_id=organization_id,
                user_id=user_id,
            )
            if not db_session:
                raise ValueError(f"Session {session_id} not found")
            resolved_session_id = session_id
        else:
            db_session = crud.create_architect_session(
                db=db,
                session=schemas.ArchitectSessionCreate(
                    title=message[:100].strip() if message else None,
                    mode="discovery",
                ),
                organization_id=organization_id,
                user_id=user_id,
            )
            resolved_session_id = str(db_session.id)

        if persist_user_message:
            crud.create_architect_message(
                db=db,
                message=schemas.ArchitectMessageCreate(
                    session_id=resolved_session_id,
                    role="user",
                    content=message,
                    attachments=attachments,
                ),
                organization_id=organization_id,
                user_id=user_id,
            )

        if session_id:
            conversation_history = [
                {"role": m.role, "content": m.content}
                for m in db_session.messages
                if m.role in ("user", "assistant", "system") and m.content
            ]
            # Strip the last user message — it's the one being processed now.
            if conversation_history and conversation_history[-1]["role"] == "user":
                conversation_history = conversation_history[:-1]
        else:
            conversation_history = []

        session_data = {
            "conversation_history": conversation_history,
            "mode": db_session.mode or "discovery",
            "plan_data": db_session.plan_data,
            "agent_state": db_session.agent_state or {},
            "session_has_title": bool(db_session.title),
        }

    return resolved_session_id, session_data


@observe()
async def build_agent(
    session_data: Dict[str, Any],
    session_id: str,
    organization_id: str,
    user_id: str,
    auto_approve: Optional[bool],
    project_id: Optional[str] = None,
) -> tuple[Any, WebSocketEventHandler]:
    """Build the ArchitectAgent with tools and restore saved session state."""
    from rhesis.backend.app import crud
    from rhesis.backend.app.auth.token_utils import create_service_delegation_token
    from rhesis.backend.app.main import app as fastapi_app
    from rhesis.backend.app.mcp_server.local_tools import LocalToolProvider
    from rhesis.backend.app.utils.user_model_utils import get_user_generation_model
    from rhesis.sdk.agents.architect.agent import ArchitectAgent
    from rhesis.sdk.agents.architect.state import ArchitectAgentStateSnapshot
    from rhesis.sdk.agents.tools import ExploreEndpointTool

    with get_db_with_tenant_variables(organization_id, user_id, project_id or "") as db:
        user = crud.get_user_by_id(db, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        if not user.is_active:
            raise ValueError(f"User {user_id} is inactive")
        delegation_token = create_service_delegation_token(user, "backend")
        model = get_user_generation_model(db, user)

    agent_state = session_data["agent_state"]
    snapshot = ArchitectAgentStateSnapshot(
        mode=session_data["mode"],
        conversation_history=session_data["conversation_history"],
        discovery_state=agent_state.get("discovery_state") or {},
        guard_state=agent_state.get("guard_state") or {},
        id_to_name=agent_state.get("id_to_name") or {},
        plan_data=session_data["plan_data"],
        max_iterations=agent_state.get("max_iterations", 15),
        pending_tasks=agent_state.get("pending_tasks") or [],
    )

    tool_provider = LocalToolProvider(fastapi_app, delegation_token, project_id=project_id)
    explore_tool = ExploreEndpointTool(
        target_factory=_make_target_factory(organization_id, user_id, project_id),
        model=model,
    )
    ws_handler = WebSocketEventHandler(session_id)
    tracing_handlers = get_agent_event_handlers(
        model_name=getattr(model, "model_name", None) or str(model),
        agent_name="architect",
    )

    agent = ArchitectAgent(
        model=model,
        tools=[tool_provider, explore_tool],
        event_handlers=[ws_handler, *tracing_handlers],
        max_iterations=snapshot.max_iterations,
        verbose=False,
    )
    agent.restore_state(snapshot)

    if auto_approve is not None:
        agent.auto_approve_all = auto_approve

    return agent, ws_handler


async def _handle_auto_resume(
    session_id: str,
    organization_id: str,
    user_id: str,
    user_message: str,
    ws_handler: WebSocketEventHandler,
    project_id: Optional[str] = None,
) -> None:
    """Persist auto-resume system messages and notify streaming start.

    No-ops on ordinary turns; only fires for ``[TASK_COMPLETED]`` messages.
    """
    if not user_message.startswith("[TASK_COMPLETED]"):
        return

    from rhesis.backend.app import crud, schemas

    with get_db_with_tenant_variables(organization_id, user_id, project_id or "") as db:
        crud.create_architect_message(
            db=db,
            message=schemas.ArchitectMessageCreate(
                session_id=session_id,
                role="system",
                content=user_message,
            ),
            organization_id=organization_id,
            user_id=user_id,
        )

    ws_handler.publish(
        EventType.ARCHITECT_STREAM_START,
        {"needs_confirmation": False},
    )


@observe()
async def run_chat(
    agent: Any,
    message: str,
    attachments: Optional[Dict[str, Any]],
) -> str:
    """Run one architect chat turn."""
    return await agent.chat_async(message, attachments=attachments)


@observe()
async def persist_state(
    agent: Any,
    response: str,
    session_id: str,
    organization_id: str,
    user_id: str,
    session_has_title: bool,
    user_message: str,
    project_id: Optional[str] = None,
) -> None:
    """Save assistant message and updated architect session state.

    Also stamps the conversation's root trace_id on ``agent_state`` so
    subsequent turns can reuse it for coherent multi-turn tracing.
    """
    from rhesis.backend.app import crud, schemas
    from rhesis.sdk.telemetry.context import get_root_trace_id

    snapshot = agent.dump_state()
    root_trace_id = get_root_trace_id()

    with get_db_with_tenant_variables(organization_id, user_id, project_id or "") as db:
        crud.create_architect_message(
            db=db,
            message=schemas.ArchitectMessageCreate(
                session_id=session_id,
                role="assistant",
                content=response,
            ),
            organization_id=organization_id,
            user_id=user_id,
        )

        agent_state = {
            "max_iterations": snapshot.max_iterations,
            "discovery_state": snapshot.discovery_state,
            "guard_state": snapshot.guard_state,
            "pending_tasks": snapshot.pending_tasks,
            "id_to_name": snapshot.id_to_name,
        }
        if root_trace_id:
            # Read on the next turn by ``architect_chat_task`` and bound via
            # ``conversation_telemetry_context`` so the SDK tracer reuses the
            # same trace_id, giving the UI one coherent trace per session.
            agent_state["conversation_trace_id"] = root_trace_id

        title_update = {}
        if not session_has_title and user_message:
            title_update["title"] = user_message[:100].strip()

        crud.update_architect_session(
            db=db,
            session_id=UUID(session_id),
            session=schemas.ArchitectSessionUpdate(
                mode=snapshot.mode,
                plan_data=snapshot.plan_data,
                agent_state=agent_state,
                **title_update,
            ),
            organization_id=organization_id,
            user_id=user_id,
        )


def _make_target_factory(org_id: str, user_id: str, project_id: Optional[str] = None):
    """Build a target factory that invokes endpoints via EndpointService."""
    from rhesis.backend.app.services.endpoint.service import EndpointService
    from rhesis.sdk.agents.targets import LocalEndpointTarget

    svc = EndpointService()

    def _invoke(endpoint_id: str, input_data: dict) -> dict:
        with get_db_with_tenant_variables(org_id or "", user_id or "", project_id or "") as db:
            return asyncio.run(
                svc.invoke_endpoint(
                    db,
                    endpoint_id,
                    input_data,
                    organization_id=org_id,
                    user_id=str(user_id),
                    project_id=project_id,
                )
            )

    def factory(endpoint_id: str) -> LocalEndpointTarget:
        name = endpoint_id
        description = ""
        try:
            from rhesis.backend.app import crud

            with get_db_with_tenant_variables(org_id or "", user_id or "", project_id or "") as db:
                ep = crud.get_endpoint(
                    db, endpoint_id, organization_id=org_id, user_id=user_id, project_id=project_id
                )
                if ep:
                    name = ep.name or endpoint_id
                    description = ep.description or ""
        except Exception:
            logger.debug("Could not load endpoint name for %s", endpoint_id)

        return LocalEndpointTarget(
            endpoint_id=endpoint_id,
            invoke_fn=_invoke,
            name=name,
            endpoint_description=description,
        )

    return factory


@endpoint(
    name="architect_chat",
    request_mapping={
        "message": "{{ input }}",
        "session_id": "{{ session_id }}",
    },
    response_mapping={
        "output": "$.content",
        "session_id": "$.session_id",
        "mode": "$.mode",
        "needs_confirmation": "$.needs_confirmation",
        "plan": "$.plan",
    },
)
async def run_architect_turn(
    message: str,
    ctx: EndpointContext,
    session_id: Optional[str] = None,
    attachments: Optional[Dict[str, Any]] = None,
    auto_approve: Optional[bool] = None,
    persist_user_message: bool = True,
    project_id: Optional[str] = None,
) -> ArchitectChatResult:
    """Process one architect chat turn.

    Called directly by ``architect_chat_task`` (Celery) for the Architect
    screen, and invocable via the SDK connector (Playground / test runs)
    through the ``@endpoint`` registration.

    Tenant identity is carried by ``ctx`` (:class:`EndpointContext`),
    which the executor injects automatically when the function is
    invoked via the connector.  Direct callers (Celery) construct it
    explicitly.
    """
    organization_id = ctx.organization_id
    user_id = ctx.user_id

    if not user_id:
        raise ValueError("user_id is required for run_architect_turn")

    session_id, session_data = await prepare_and_load_session(
        organization_id,
        user_id,
        message,
        attachments,
        persist_user_message,
        session_id,
        project_id=project_id,
    )
    processed_attachments = process_attachments(attachments)
    agent, ws_handler = await build_agent(
        session_data,
        session_id,
        organization_id,
        user_id,
        auto_approve,
        project_id=project_id,
    )
    await _handle_auto_resume(
        session_id, organization_id, user_id, message, ws_handler, project_id=project_id
    )
    response = await run_chat(agent, message, processed_attachments)
    await persist_state(
        agent,
        response,
        session_id,
        organization_id,
        user_id,
        session_data["session_has_title"],
        message,
        project_id=project_id,
    )

    return ArchitectChatResult(
        content=response,
        session_id=session_id,
        mode=agent.mode,
        needs_confirmation=agent.needs_confirmation,
        auto_approve_all=agent.auto_approve_all,
        awaiting_task=bool(agent.pending_tasks),
        plan=(
            agent.plan.to_markdown() if agent.plan and hasattr(agent.plan, "to_markdown") else None
        ),
        pending_tasks=agent.pending_tasks,
    )
