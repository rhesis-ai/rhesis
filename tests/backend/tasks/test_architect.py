"""Tests for the architect Celery task and WebSocketEventHandler."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    EventType,
)
from rhesis.backend.tasks.architect import (
    WebSocketEventHandler,
    _safe_preview,
    _tool_description,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session_id():
    return "test-session-123"


@pytest.fixture
def handler(session_id):
    return WebSocketEventHandler(session_id)


# ---------------------------------------------------------------------------
# WebSocketEventHandler — construction
# ---------------------------------------------------------------------------


class TestWebSocketEventHandlerInit:
    def test_channel_set(self, handler, session_id):
        assert handler.channel == f"architect:{session_id}"

    def test_target_is_channel(self, handler, session_id):
        assert isinstance(handler._target, ChannelTarget)
        assert handler._target.channel == f"architect:{session_id}"


# ---------------------------------------------------------------------------
# WebSocketEventHandler — event methods
# ---------------------------------------------------------------------------


class TestWebSocketEventHandlerEvents:
    """Each async handler should call _publish with the right event type."""

    @pytest.mark.asyncio
    async def test_on_agent_start(self, handler):
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_agent_start(query="hello world")

        mock_pub.assert_called_once()
        event_type, payload = mock_pub.call_args[0]
        assert event_type == EventType.ARCHITECT_THINKING
        assert payload["query"] == "hello world"
        assert payload["status"] == "started"

    @pytest.mark.asyncio
    async def test_on_agent_start_truncates_query(self, handler):
        long_query = "x" * 500
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_agent_start(query=long_query)

        payload = mock_pub.call_args[0][1]
        assert len(payload["query"]) == 200

    @pytest.mark.asyncio
    async def test_on_iteration_start(self, handler):
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_iteration_start(iteration=3)

        event_type, payload = mock_pub.call_args[0]
        assert event_type == EventType.ARCHITECT_THINKING
        assert payload["iteration"] == 3
        assert payload["status"] == "thinking"

    @pytest.mark.asyncio
    async def test_on_tool_start(self, handler):
        with patch.object(handler, "_publish") as mock_pub:
            with patch(
                "rhesis.backend.tasks.architect._tool_description",
                return_value="List tests",
            ):
                await handler.on_tool_start(
                    tool_name="list_tests",
                    arguments={"name": "safety"},
                )

        event_type, payload = mock_pub.call_args[0]
        assert event_type == EventType.ARCHITECT_TOOL_START
        assert payload["tool"] == "list_tests"
        assert "description" in payload
        assert "args" in payload

    @pytest.mark.asyncio
    async def test_on_tool_end_success(self, handler):
        result = MagicMock(success=True, content="found 5 items")
        with patch.object(handler, "_publish") as mock_pub:
            with patch(
                "rhesis.backend.tasks.architect._tool_description",
                return_value="List tests",
            ):
                await handler.on_tool_end(tool_name="list_tests", result=result)

        event_type, payload = mock_pub.call_args[0]
        assert event_type == EventType.ARCHITECT_TOOL_END
        assert payload["tool"] == "list_tests"
        assert payload["success"] is True
        assert "found 5 items" in payload["preview"]

    @pytest.mark.asyncio
    async def test_on_tool_end_failure(self, handler):
        result = MagicMock(success=False, content="error occurred")
        with patch.object(handler, "_publish") as mock_pub:
            with patch(
                "rhesis.backend.tasks.architect._tool_description",
                return_value="List tests",
            ):
                await handler.on_tool_end(tool_name="list_tests", result=result)

        payload = mock_pub.call_args[0][1]
        assert payload["success"] is False

    @pytest.mark.asyncio
    async def test_on_mode_change(self, handler):
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_mode_change(old_mode="discovery", new_mode="planning")

        event_type, payload = mock_pub.call_args[0]
        assert event_type == EventType.ARCHITECT_MODE_CHANGE
        assert payload["old_mode"] == "discovery"
        assert payload["new_mode"] == "planning"

    @pytest.mark.asyncio
    async def test_on_plan_update_with_markdown(self, handler):
        plan = MagicMock()
        plan.to_markdown.return_value = "# Plan\n- step 1"
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_plan_update(plan=plan)

        event_type, payload = mock_pub.call_args[0]
        assert event_type == EventType.ARCHITECT_PLAN_UPDATE
        assert payload["plan"] == "# Plan\n- step 1"

    @pytest.mark.asyncio
    async def test_on_plan_update_without_markdown(self, handler):
        plan = "plain string plan"
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_plan_update(plan=plan)

        payload = mock_pub.call_args[0][1]
        assert payload["plan"] == "plain string plan"

    @pytest.mark.asyncio
    async def test_on_error(self, handler):
        err = ValueError("something broke")
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_error(error=err)

        event_type, payload = mock_pub.call_args[0]
        assert event_type == EventType.ARCHITECT_ERROR
        assert payload["error"] == "something broke"
        assert payload["error_type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_on_agent_end_is_noop(self, handler):
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_agent_end(result="done")

        mock_pub.assert_not_called()


# ---------------------------------------------------------------------------
# Streaming event handlers
# ---------------------------------------------------------------------------


class TestWebSocketEventHandlerStreaming:
    @pytest.mark.asyncio
    async def test_on_stream_start(self, handler):
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_stream_start(needs_confirmation=True)

        event_type, payload = mock_pub.call_args[0]
        assert event_type == EventType.ARCHITECT_STREAM_START
        assert payload["needs_confirmation"] is True

    @pytest.mark.asyncio
    async def test_on_stream_start_default(self, handler):
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_stream_start()

        payload = mock_pub.call_args[0][1]
        assert payload["needs_confirmation"] is False

    @pytest.mark.asyncio
    async def test_on_text_chunk(self, handler):
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_text_chunk(chunk="Hello ")

        event_type, payload = mock_pub.call_args[0]
        assert event_type == EventType.ARCHITECT_TEXT_CHUNK
        assert payload["chunk"] == "Hello "

    @pytest.mark.asyncio
    async def test_on_stream_end_success(self, handler):
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_stream_end(content="full response text")

        event_type, payload = mock_pub.call_args[0]
        assert event_type == EventType.ARCHITECT_STREAM_END
        assert payload["content"] == "full response text"
        assert payload["error"] is None

    @pytest.mark.asyncio
    async def test_on_stream_end_with_error(self, handler):
        with patch.object(handler, "_publish") as mock_pub:
            await handler.on_stream_end(content="partial", error="LLM timeout")

        payload = mock_pub.call_args[0][1]
        assert payload["content"] == "partial"
        assert payload["error"] == "LLM timeout"


# ---------------------------------------------------------------------------
# _publish integration
# ---------------------------------------------------------------------------


class TestPublishIntegration:
    def test_publish_calls_publish_event(self, handler):
        with patch("rhesis.backend.tasks.architect.publish_event") as mock_pe:
            handler._publish(EventType.ARCHITECT_THINKING, {"status": "ok"})

        mock_pe.assert_called_once()
        msg, target = mock_pe.call_args[0]
        assert msg.type == EventType.ARCHITECT_THINKING
        assert msg.payload == {"status": "ok"}
        assert isinstance(target, ChannelTarget)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestToolDescription:
    def test_with_label_and_name(self):
        with patch(
            "rhesis.backend.tasks.architect._get_tool_labels",
            return_value={"create_test": "Create test"},
        ):
            desc = _tool_description("create_test", {"name": "safety suite"})

        assert desc == "Create test: safety suite"

    def test_with_label_and_prompt(self):
        with patch(
            "rhesis.backend.tasks.architect._get_tool_labels",
            return_value={"search": "Search"},
        ):
            desc = _tool_description("search", {"prompt": "find safety tests"})

        assert desc == "Search: find safety tests"

    def test_long_prompt_truncated(self):
        long_prompt = "a" * 200
        with patch(
            "rhesis.backend.tasks.architect._get_tool_labels",
            return_value={"search": "Search"},
        ):
            desc = _tool_description("search", {"prompt": long_prompt})

        # 80 chars + "..."
        assert desc == f"Search: {'a' * 80}..."

    def test_fallback_label(self):
        with patch(
            "rhesis.backend.tasks.architect._get_tool_labels",
            return_value={},
        ):
            desc = _tool_description("list_test_sets", {})

        assert desc == "List Test Sets"

    def test_name_takes_priority_over_prompt(self):
        with patch(
            "rhesis.backend.tasks.architect._get_tool_labels",
            return_value={"t": "T"},
        ):
            desc = _tool_description("t", {"name": "my-name", "prompt": "my-prompt"})

        assert desc == "T: my-name"


class TestSafePreview:
    def test_dict_input(self):
        result = _safe_preview({"key": "value", "num": 42})
        assert result == {"key": "value", "num": 42}

    def test_long_string_truncated(self):
        result = _safe_preview({"data": "x" * 500}, max_len=100)
        assert len(result["data"]) == 100

    def test_non_dict_input(self):
        result = _safe_preview("plain string")
        assert "value" in result
        assert result["value"] == "plain string"

    def test_bool_preserved(self):
        result = _safe_preview({"flag": True})
        assert result["flag"] is True
