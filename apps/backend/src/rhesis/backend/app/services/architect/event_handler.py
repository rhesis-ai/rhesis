"""WebSocket event handler for the Architect agent streaming pipeline."""

import logging
from typing import Any, Dict, Optional

from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    EventType,
    WebSocketMessage,
)
from rhesis.backend.app.services.websocket.publisher import publish_event
from rhesis.sdk.agents.errors import format_user_facing_error

logger = logging.getLogger(__name__)

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


class WebSocketEventHandler:
    """Bridges AgentEventHandler to WebSocket streaming via Redis pub/sub."""

    def __init__(self, session_id: str):
        self.channel = f"architect:{session_id}"
        self._target = ChannelTarget(channel=self.channel)

    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        publish_event(
            WebSocketMessage(type=event_type, payload=payload),
            self._target,
        )

    async def on_agent_start(self, *, query: str, **kw: Any) -> None:
        self.publish(
            EventType.ARCHITECT_THINKING,
            {"status": "started", "query": query[:200]},
        )

    async def on_iteration_start(self, *, iteration: int, **kw: Any) -> None:
        self.publish(
            EventType.ARCHITECT_THINKING,
            {"iteration": iteration, "status": "thinking"},
        )

    async def on_tool_start(
        self,
        *,
        tool_name: str,
        arguments: Dict[str, Any],
        reasoning: Optional[str] = None,
        **kw: Any,
    ) -> None:
        payload = {
            "tool": tool_name,
            "description": _tool_description(tool_name, arguments),
            "args": _safe_preview(arguments),
        }
        if reasoning:
            payload["reasoning"] = reasoning
        self.publish(EventType.ARCHITECT_TOOL_START, payload)

    async def on_tool_end(self, *, tool_name: str, result: Any, **kw: Any) -> None:
        success = getattr(result, "success", True)
        content = getattr(result, "content", "")
        duration_ms = getattr(result, "duration_ms", None)
        payload: Dict[str, Any] = {
            "tool": tool_name,
            "description": _tool_description(tool_name, {}),
            "success": success,
            "preview": str(content)[:300],
        }
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        self.publish(EventType.ARCHITECT_TOOL_END, payload)

    async def on_mode_change(self, *, old_mode: str, new_mode: str, **kw: Any) -> None:
        self.publish(
            EventType.ARCHITECT_MODE_CHANGE,
            {"old_mode": old_mode, "new_mode": new_mode},
        )

    async def on_plan_update(self, *, plan: Any, **kw: Any) -> None:
        plan_md = plan.to_markdown() if hasattr(plan, "to_markdown") else str(plan)
        self.publish(EventType.ARCHITECT_PLAN_UPDATE, {"plan": plan_md})

    async def on_stream_start(self, *, needs_confirmation: bool = False, **kw: Any) -> None:
        self.publish(
            EventType.ARCHITECT_STREAM_START,
            {"needs_confirmation": needs_confirmation},
        )

    async def on_text_chunk(self, *, chunk: str, **kw: Any) -> None:
        self.publish(EventType.ARCHITECT_TEXT_CHUNK, {"chunk": chunk})

    async def on_stream_end(
        self,
        *,
        content: str,
        error: Optional[str] = None,
        **kw: Any,
    ) -> None:
        friendly_error = format_user_facing_error(error) if error else None
        self.publish(
            EventType.ARCHITECT_STREAM_END,
            {"content": content, "error": friendly_error},
        )

    async def on_agent_end(self, *, result: Any, **kw: Any) -> None:
        pass  # handled after chat_async returns

    async def on_error(self, *, error: Exception, **kw: Any) -> None:
        self.publish(
            EventType.ARCHITECT_ERROR,
            {
                "error": format_user_facing_error(error),
                "error_type": type(error).__name__,
            },
        )
