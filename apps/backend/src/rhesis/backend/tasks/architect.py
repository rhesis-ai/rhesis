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

    async def on_tool_start(
        self, *, tool_name: str, arguments: Dict[str, Any], reasoning: Optional[str] = None, **kw: Any
    ) -> None:
        payload = {
            "tool": tool_name,
            "description": _tool_description(tool_name, arguments),
            "args": _safe_preview(arguments),
        }
        if reasoning:
            payload["reasoning"] = reasoning

        self._publish(
            EventType.ARCHITECT_TOOL_START,
            payload,
        )

    async def on_tool_end(self, *, tool_name: str, result: Any, **kw: Any) -> None:
        success = getattr(result, "success", True)
        content = getattr(result, "content", "")
        self._publish(
            EventType.ARCHITECT_TOOL_END,
            {
                "tool": tool_name,
                "description": _tool_description(tool_name, {}),
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

    async def on_stream_start(self, *, needs_confirmation: bool = False, **kw: Any) -> None:
        self._publish(
            EventType.ARCHITECT_STREAM_START,
            {"needs_confirmation": needs_confirmation},
        )

    async def on_text_chunk(self, *, chunk: str, **kw: Any) -> None:
        self._publish(
            EventType.ARCHITECT_TEXT_CHUNK,
            {"chunk": chunk},
        )

    async def on_stream_end(
        self,
        *,
        content: str,
        error: Optional[str] = None,
        **kw: Any,
    ) -> None:
        self._publish(
            EventType.ARCHITECT_STREAM_END,
            {"content": content, "error": error},
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
            session_has_title = bool(db_session.title)

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

        # Endpoint exploration tool — uses a target factory that
        # calls EndpointService directly, no HTTP round-trip.
        from rhesis.sdk.agents.tools import ExploreEndpointTool

        explore_tool = ExploreEndpointTool(
            target_factory=_make_target_factory(org_id, user_id),
            model=model,
        )

        agent = ArchitectAgent(
            model=model,
            tools=[tool_provider, explore_tool],
            event_handlers=[ws_handler],
            max_iterations=saved_agent_state.get("max_iterations", 15),
            verbose=False,
        )

        # Restore state
        agent._mode = saved_mode
        agent._conversation_history = conversation_history

        if saved_agent_state.get("discovery_state"):
            agent._discovery_state = saved_agent_state["discovery_state"]

        if saved_agent_state.get("guard_state"):
            agent.guard_state = saved_agent_state["guard_state"]

        if saved_plan_data:
            from rhesis.sdk.agents.architect.plan import ArchitectPlan

            try:
                agent._plan = ArchitectPlan.model_validate(saved_plan_data)
            except Exception:
                logger.warning("Failed to restore plan from saved data")

        # 3. Run the agent
        processed_attachments = _process_attachments(attachments)
        response = asyncio.run(agent.chat_async(user_message, attachments=processed_attachments))

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
                "discovery_state": agent.discovery_state,
                "guard_state": agent.guard_state,
            }

            # Auto-generate title from first message if not set
            title_update = {}
            if not session_has_title and user_message:
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
                    "needs_confirmation": agent.needs_confirmation,
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


_tool_labels: Optional[Dict[str, str]] = None


def _get_tool_labels() -> Dict[str, str]:
    """Load tool labels from YAML, cached after first call."""
    global _tool_labels
    if _tool_labels is None:
        from rhesis.backend.app.mcp_server.tools import load_tool_labels

        _tool_labels = load_tool_labels()
    return _tool_labels


def _tool_description(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Generate a human-readable description of a tool call."""
    labels = _get_tool_labels()
    base = labels.get(tool_name, tool_name.replace("_", " ").title())

    # Add context from arguments when available
    name = arguments.get("name", "")
    prompt = arguments.get("prompt", "")
    if name:
        return f"{base}: {name}"
    if prompt:
        preview = prompt[:80].rstrip()
        if len(prompt) > 80:
            preview += "..."
        return f"{base}: {preview}"
    return base


def _safe_preview(obj: Any, max_len: int = 200) -> Dict[str, Any]:
    """Create a safe preview of arguments for streaming."""
    if isinstance(obj, dict):
        return {
            k: str(v)[:max_len] if not isinstance(v, (int, float, bool)) else v
            for k, v in obj.items()
        }
    return {"value": str(obj)[:max_len]}


def _process_attachments(
    attachments: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Process raw attachments from the WebSocket payload.

    - ``mentions`` are passed through as-is (already resolved by the frontend).
    - ``files`` have their base64 ``data`` decoded and text extracted via
      the SDK's ``DocumentExtractor`` (MarkItDown).  The binary ``data``
      field is replaced with an extracted ``content`` string.
    """
    if not attachments:
        return None

    result: Dict[str, Any] = {}

    mentions = attachments.get("mentions")
    if mentions:
        result["mentions"] = mentions

    files = attachments.get("files")
    if files:
        from rhesis.sdk.services.extractor import DocumentExtractor

        extractor = DocumentExtractor()
        processed_files = []
        for f in files:
            filename = f.get("filename", "file")
            try:
                import base64

                raw_bytes = base64.b64decode(f.get("data", ""))
                content = extractor.extract_from_bytes(raw_bytes, filename)
            except Exception as exc:
                logger.warning("Failed to extract text from %s: %s", filename, exc)
                content = f"[Could not extract text from {filename}: {exc}]"
            processed_files.append(
                {
                    "filename": filename,
                    "content_type": f.get("content_type", ""),
                    "content": content,
                }
            )
        result["files"] = processed_files

    return result if result else None


def _make_target_factory(org_id: str, user_id: str):
    """Build a target factory that invokes endpoints via EndpointService.

    Returns a callable ``(endpoint_id) -> LocalEndpointTarget`` that
    the ``ExploreEndpointTool`` uses to create targets at call time.
    Each target calls the service layer directly — no HTTP, no SDK
    client, no delegation token.
    """
    import asyncio as _asyncio

    from rhesis.backend.app.services.endpoint.service import EndpointService
    from rhesis.sdk.agents.targets import LocalEndpointTarget

    svc = EndpointService()

    def _invoke(endpoint_id: str, input_data: dict) -> dict:
        with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
            return _asyncio.run(
                svc.invoke_endpoint(
                    db,
                    endpoint_id,
                    input_data,
                    organization_id=org_id,
                    user_id=str(user_id),
                )
            )

    def factory(endpoint_id: str) -> LocalEndpointTarget:
        name = endpoint_id
        description = ""
        try:
            from rhesis.backend.app import crud

            with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
                ep = crud.get_endpoint(db, endpoint_id, organization_id=org_id, user_id=user_id)
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
