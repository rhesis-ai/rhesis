"""Celery task for Architect agent conversations.

Loads session state from DB, runs the ArchitectAgent, streams events
via Redis pub/sub, and persists the final response + updated state.
"""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    EventType,
    WebSocketMessage,
)
from rhesis.backend.app.services.websocket.publisher import publish_event
from rhesis.backend.tasks.base import SilentTask
from rhesis.backend.worker import app

logger = logging.getLogger(__name__)


class WebSocketEventHandler:
    """Bridges AgentEventHandler to WebSocket streaming via Redis pub/sub."""

    def __init__(self, session_id: str):
        self.channel = f"architect:{session_id}"
        self._target = ChannelTarget(channel=self.channel)

    def _publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        publish_event(
            WebSocketMessage(type=event_type, payload=payload),
            self._target,
        )

    async def on_agent_start(self, *, query: str, **kw: Any) -> None:
        self._publish(
            EventType.ARCHITECT_THINKING,
            {"status": "started", "query": query[:200]},
        )

    async def on_iteration_start(self, *, iteration: int, **kw: Any) -> None:
        self._publish(
            EventType.ARCHITECT_THINKING,
            {"iteration": iteration, "status": "thinking"},
        )

    async def on_tool_start(self, *, tool_name: str, arguments: Dict[str, Any], **kw: Any) -> None:
        self._publish(
            EventType.ARCHITECT_TOOL_START,
            {"tool": tool_name, "args": _safe_preview(arguments)},
        )

    async def on_tool_end(self, *, tool_name: str, result: Any, **kw: Any) -> None:
        success = getattr(result, "success", True)
        content = getattr(result, "content", "")
        self._publish(
            EventType.ARCHITECT_TOOL_END,
            {
                "tool": tool_name,
                "success": success,
                "preview": str(content)[:300],
            },
        )

    async def on_mode_change(self, *, old_mode: str, new_mode: str, **kw: Any) -> None:
        self._publish(
            EventType.ARCHITECT_MODE_CHANGE,
            {"old_mode": old_mode, "new_mode": new_mode},
        )

    async def on_plan_update(self, *, plan: Any, **kw: Any) -> None:
        plan_md = plan.to_markdown() if hasattr(plan, "to_markdown") else str(plan)
        self._publish(
            EventType.ARCHITECT_PLAN_UPDATE,
            {"plan": plan_md},
        )

    async def on_agent_end(self, *, result: Any, **kw: Any) -> None:
        pass  # handled after chat_async returns

    async def on_error(self, *, error: Exception, **kw: Any) -> None:
        self._publish(
            EventType.ARCHITECT_ERROR,
            {"error": str(error), "error_type": type(error).__name__},
        )


@app.task(
    base=SilentTask,
    name="rhesis.backend.tasks.architect.architect_chat_task",
    bind=True,
    max_retries=1,
    soft_time_limit=300,
    time_limit=360,
)
def architect_chat_task(
    self,
    session_id: str,
    user_message: str,
    attachments: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Process a single architect chat turn.

    1. Load session from DB (history, plan, mode, agent_state)
    2. Reconstruct ArchitectAgent with saved state
    3. Run agent with WebSocket event handler for streaming
    4. Persist response + updated state to DB
    5. Publish final ARCHITECT_RESPONSE event
    """
    org_id, user_id = self.get_tenant_context()
    channel = f"architect:{session_id}"
    target = ChannelTarget(channel=channel)

    self.log_with_context(
        "info",
        "Starting architect chat task",
        session_id=session_id,
    )

    try:
        from rhesis.backend.app import crud, schemas

        # 1. Load session
        with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
            db_session = crud.get_architect_session_detail(
                db,
                session_id=UUID(session_id),
                organization_id=org_id,
                user_id=user_id,
            )
            if not db_session:
                raise ValueError(f"Session {session_id} not found")

            # Extract state for agent reconstruction
            conversation_history = [
                {"role": m.role, "content": m.content}
                for m in db_session.messages
                if m.role in ("user", "assistant") and m.content
            ]
            # Remove the last user message (it's the one we're processing)
            if conversation_history and conversation_history[-1]["role"] == "user":
                conversation_history = conversation_history[:-1]

            saved_mode = db_session.mode or "discovery"
            saved_plan_data = db_session.plan_data
            saved_agent_state = db_session.agent_state or {}

        # 2. Construct agent with tools and event handler
        ws_handler = WebSocketEventHandler(session_id)

        import asyncio

        from rhesis.backend.app.auth.token_utils import (
            create_service_delegation_token,
        )
        from rhesis.backend.app.main import app as fastapi_app
        from rhesis.backend.app.mcp_server.local_tools import (
            LocalToolProvider,
        )

        # Resolve user, model, and delegation token for tool auth.
        from rhesis.backend.app.utils.user_model_utils import (
            get_user_generation_model,
        )
        from rhesis.sdk.agents.architect.agent import ArchitectAgent

        with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
            user = crud.get_user_by_id(db, user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            if not user.is_active:
                raise ValueError(f"User {user_id} is inactive")
            delegation_token = create_service_delegation_token(user, "backend")
            model = get_user_generation_model(db, user)

        # In-process tool provider — calls FastAPI routes via ASGI
        # transport, no MCP protocol or external HTTP needed.
        tool_provider = LocalToolProvider(fastapi_app, delegation_token)

        agent = ArchitectAgent(
            model=model,
            tools=[tool_provider],
            event_handlers=[ws_handler],
            max_iterations=saved_agent_state.get("max_iterations", 15),
            verbose=False,
        )

        # Restore state
        agent._mode = saved_mode
        agent._conversation_history = conversation_history

        if saved_plan_data:
            from rhesis.sdk.agents.architect.plan import ArchitectPlan

            try:
                agent._plan = ArchitectPlan.model_validate(saved_plan_data)
            except Exception:
                logger.warning("Failed to restore plan from saved data")

        # 3. Run the agent
        response = asyncio.run(agent.chat_async(user_message))

        # 4. Persist response + state
        with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
            # Save assistant message
            crud.create_architect_message(
                db=db,
                message=schemas.ArchitectMessageCreate(
                    session_id=session_id,
                    role="assistant",
                    content=response,
                ),
                organization_id=org_id,
                user_id=user_id,
            )

            # Update session state
            plan_data = None
            if agent.plan:
                try:
                    plan_data = agent.plan.model_dump()
                except Exception:
                    pass

            agent_state = {
                "max_iterations": agent.max_iterations,
            }

            # Auto-generate title from first message if not set
            title_update = {}
            if not db_session.title and user_message:
                title_update["title"] = user_message[:100].strip()

            crud.update_architect_session(
                db=db,
                session_id=UUID(session_id),
                session=schemas.ArchitectSessionUpdate(
                    mode=agent.mode,
                    plan_data=plan_data,
                    agent_state=agent_state,
                    **title_update,
                ),
                organization_id=org_id,
                user_id=user_id,
            )

        # 5. Publish final response
        publish_event(
            WebSocketMessage(
                type=EventType.ARCHITECT_RESPONSE,
                payload={
                    "session_id": session_id,
                    "content": response,
                    "mode": agent.mode,
                    "plan": (
                        agent.plan.to_markdown()
                        if agent.plan and hasattr(agent.plan, "to_markdown")
                        else None
                    ),
                },
            ),
            target,
        )

        self.log_with_context(
            "info",
            "Architect chat task completed",
            session_id=session_id,
            response_length=len(response),
        )

        return {
            "session_id": session_id,
            "response_length": len(response),
            "mode": agent.mode,
        }

    except Exception as e:
        logger.error(f"Architect task failed: {e}", exc_info=True)
        publish_event(
            WebSocketMessage(
                type=EventType.ARCHITECT_ERROR,
                payload={
                    "session_id": session_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ),
            target,
        )
        raise


def _safe_preview(obj: Any, max_len: int = 200) -> Dict[str, Any]:
    """Create a safe preview of arguments for streaming."""
    if isinstance(obj, dict):
        return {
            k: str(v)[:max_len] if not isinstance(v, (int, float, bool)) else v
            for k, v in obj.items()
        }
    return {"value": str(obj)[:max_len]}
