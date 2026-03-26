"""Tests for the architect WebSocket message handler."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.schemas.websocket import (
    ConnectionTarget,
    EventType,
    WebSocketMessage,
)
from rhesis.backend.app.services.websocket.handlers.architect import (
    _send_architect_error,
    handle_architect_message,
)


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = MagicMock()
    user.id = uuid4()
    user.organization_id = uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_manager():
    """Create a mock WebSocketManager."""
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    return manager


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestArchitectHandlerValidation:
    @pytest.mark.asyncio
    async def test_missing_session_id(self, mock_manager, mock_user):
        message = WebSocketMessage(
            type=EventType.ARCHITECT_MESSAGE,
            correlation_id="corr-1",
            payload={"message": "hello"},
        )

        await handle_architect_message(mock_manager, "conn-1", mock_user, message)

        mock_manager.broadcast.assert_called_once()
        msg = mock_manager.broadcast.call_args[0][0]
        assert msg.type == EventType.ARCHITECT_ERROR
        assert "session_id" in msg.payload["error"]

    @pytest.mark.asyncio
    async def test_missing_message(self, mock_manager, mock_user):
        message = WebSocketMessage(
            type=EventType.ARCHITECT_MESSAGE,
            correlation_id="corr-1",
            payload={"session_id": "sess-123"},
        )

        await handle_architect_message(mock_manager, "conn-1", mock_user, message)

        mock_manager.broadcast.assert_called_once()
        msg = mock_manager.broadcast.call_args[0][0]
        assert msg.type == EventType.ARCHITECT_ERROR
        assert "message" in msg.payload["error"]

    @pytest.mark.asyncio
    async def test_empty_payload(self, mock_manager, mock_user):
        message = WebSocketMessage(
            type=EventType.ARCHITECT_MESSAGE,
            correlation_id="corr-1",
            payload={},
        )

        await handle_architect_message(mock_manager, "conn-1", mock_user, message)

        mock_manager.broadcast.assert_called_once()
        msg = mock_manager.broadcast.call_args[0][0]
        assert msg.type == EventType.ARCHITECT_ERROR

    @pytest.mark.asyncio
    async def test_none_payload(self, mock_manager, mock_user):
        message = WebSocketMessage(
            type=EventType.ARCHITECT_MESSAGE,
            correlation_id="corr-1",
            payload=None,
        )

        await handle_architect_message(mock_manager, "conn-1", mock_user, message)

        mock_manager.broadcast.assert_called_once()
        msg = mock_manager.broadcast.call_args[0][0]
        assert msg.type == EventType.ARCHITECT_ERROR


# ---------------------------------------------------------------------------
# Successful dispatch
# ---------------------------------------------------------------------------


class TestArchitectHandlerSuccess:
    @pytest.mark.asyncio
    async def test_persists_message_and_dispatches_task(self, mock_manager, mock_user):
        session_id = "sess-abc"
        message = WebSocketMessage(
            type=EventType.ARCHITECT_MESSAGE,
            correlation_id="corr-1",
            payload={"session_id": session_id, "message": "test me"},
        )

        with patch(
            "rhesis.backend.app.services.websocket.handlers.architect.get_db_with_tenant_variables"
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

            mock_crud = MagicMock()
            mock_task = MagicMock()

            with (
                patch(
                    "rhesis.backend.app.crud",
                    mock_crud,
                ),
                patch(
                    "rhesis.backend.app.schemas",
                ),
                patch(
                    "rhesis.backend.tasks.architect.architect_chat_task",
                    mock_task,
                ),
            ):
                await handle_architect_message(mock_manager, "conn-1", mock_user, message)

                # Verify message persisted
                mock_crud.create_architect_message.assert_called_once()
                call_kwargs = mock_crud.create_architect_message.call_args[1]
                assert call_kwargs["organization_id"] == str(mock_user.organization_id)

                # Verify Celery task dispatched
                mock_task.apply_async.assert_called_once()
                task_kwargs = mock_task.apply_async.call_args[1]
                assert task_kwargs["kwargs"]["session_id"] == session_id
                assert task_kwargs["kwargs"]["user_message"] == "test me"
                assert task_kwargs["headers"]["organization_id"] == str(mock_user.organization_id)
                assert task_kwargs["headers"]["user_id"] == str(mock_user.id)

        # Verify acknowledgement sent
        mock_manager.broadcast.assert_called_once()
        ack_msg = mock_manager.broadcast.call_args[0][0]
        ack_target = mock_manager.broadcast.call_args[0][1]

        assert ack_msg.type == EventType.ARCHITECT_THINKING
        assert ack_msg.correlation_id == "corr-1"
        assert ack_msg.payload["session_id"] == session_id
        assert isinstance(ack_target, ConnectionTarget)
        assert ack_target.connection_id == "conn-1"

    @pytest.mark.asyncio
    async def test_auto_approve_forwarded_to_celery(self, mock_manager, mock_user):
        message = WebSocketMessage(
            type=EventType.ARCHITECT_MESSAGE,
            correlation_id="corr-1",
            payload={
                "session_id": "sess-1",
                "message": "go ahead",
                "auto_approve": True,
            },
        )

        with patch(
            "rhesis.backend.app.services.websocket.handlers.architect.get_db_with_tenant_variables"
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

            mock_task = MagicMock()

            with (
                patch("rhesis.backend.app.crud", MagicMock()),
                patch("rhesis.backend.app.schemas"),
                patch(
                    "rhesis.backend.tasks.architect.architect_chat_task",
                    mock_task,
                ),
            ):
                await handle_architect_message(mock_manager, "conn-1", mock_user, message)

                task_kwargs = mock_task.apply_async.call_args[1]
                assert task_kwargs["kwargs"]["auto_approve"] is True

    @pytest.mark.asyncio
    async def test_auto_approve_absent_sends_none(self, mock_manager, mock_user):
        message = WebSocketMessage(
            type=EventType.ARCHITECT_MESSAGE,
            correlation_id="corr-1",
            payload={
                "session_id": "sess-1",
                "message": "hello",
            },
        )

        with patch(
            "rhesis.backend.app.services.websocket.handlers.architect.get_db_with_tenant_variables"
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

            mock_task = MagicMock()

            with (
                patch("rhesis.backend.app.crud", MagicMock()),
                patch("rhesis.backend.app.schemas"),
                patch(
                    "rhesis.backend.tasks.architect.architect_chat_task",
                    mock_task,
                ),
            ):
                await handle_architect_message(mock_manager, "conn-1", mock_user, message)

                task_kwargs = mock_task.apply_async.call_args[1]
                assert task_kwargs["kwargs"]["auto_approve"] is None

    @pytest.mark.asyncio
    async def test_attachments_forwarded(self, mock_manager, mock_user):
        attachments = {"files": ["doc.pdf"]}
        message = WebSocketMessage(
            type=EventType.ARCHITECT_MESSAGE,
            correlation_id="corr-1",
            payload={
                "session_id": "sess-1",
                "message": "analyze this",
                "attachments": attachments,
            },
        )

        with patch(
            "rhesis.backend.app.services.websocket.handlers.architect.get_db_with_tenant_variables"
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

            mock_task = MagicMock()

            with (
                patch(
                    "rhesis.backend.app.crud",
                    MagicMock(),
                ),
                patch(
                    "rhesis.backend.app.schemas",
                ),
                patch(
                    "rhesis.backend.tasks.architect.architect_chat_task",
                    mock_task,
                ),
            ):
                await handle_architect_message(mock_manager, "conn-1", mock_user, message)

                task_kwargs = mock_task.apply_async.call_args[1]
                assert task_kwargs["kwargs"]["attachments"] == attachments


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestArchitectHandlerErrors:
    @pytest.mark.asyncio
    async def test_db_error_sends_architect_error(self, mock_manager, mock_user):
        message = WebSocketMessage(
            type=EventType.ARCHITECT_MESSAGE,
            correlation_id="corr-1",
            payload={"session_id": "sess-1", "message": "hi"},
        )

        with patch(
            "rhesis.backend.app.services.websocket.handlers.architect.get_db_with_tenant_variables"
        ) as mock_get_db:
            mock_get_db.return_value.__enter__ = MagicMock(side_effect=RuntimeError("DB down"))
            mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

            await handle_architect_message(mock_manager, "conn-1", mock_user, message)

        mock_manager.broadcast.assert_called_once()
        msg = mock_manager.broadcast.call_args[0][0]
        assert msg.type == EventType.ARCHITECT_ERROR
        assert "DB down" in msg.payload["error"]
        assert msg.payload["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_correlation_id_preserved_on_error(self, mock_manager, mock_user):
        message = WebSocketMessage(
            type=EventType.ARCHITECT_MESSAGE,
            correlation_id="my-corr-id",
            payload={"session_id": "sess-1", "message": "hi"},
        )

        with patch(
            "rhesis.backend.app.services.websocket.handlers.architect.get_db_with_tenant_variables"
        ) as mock_get_db:
            mock_get_db.return_value.__enter__ = MagicMock(side_effect=Exception("fail"))
            mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

            await handle_architect_message(mock_manager, "conn-1", mock_user, message)

        msg = mock_manager.broadcast.call_args[0][0]
        assert msg.correlation_id == "my-corr-id"


# ---------------------------------------------------------------------------
# _send_architect_error helper
# ---------------------------------------------------------------------------


class TestSendArchitectError:
    @pytest.mark.asyncio
    async def test_sends_error_message(self, mock_manager):
        await _send_architect_error(mock_manager, "conn-1", "corr-1", "bad request")

        mock_manager.broadcast.assert_called_once()
        msg = mock_manager.broadcast.call_args[0][0]
        target = mock_manager.broadcast.call_args[0][1]

        assert msg.type == EventType.ARCHITECT_ERROR
        assert msg.correlation_id == "corr-1"
        assert msg.payload["error"] == "bad request"
        assert msg.payload["error_type"] == "Error"
        assert isinstance(target, ConnectionTarget)
        assert target.connection_id == "conn-1"

    @pytest.mark.asyncio
    async def test_custom_error_type(self, mock_manager):
        await _send_architect_error(
            mock_manager,
            "conn-1",
            None,
            "not found",
            error_type="NotFoundError",
        )

        msg = mock_manager.broadcast.call_args[0][0]
        assert msg.payload["error_type"] == "NotFoundError"
        assert msg.correlation_id is None

    @pytest.mark.asyncio
    async def test_targets_connection(self, mock_manager):
        await _send_architect_error(mock_manager, "conn-42", "corr-1", "err")

        target = mock_manager.broadcast.call_args[0][1]
        assert isinstance(target, ConnectionTarget)
        assert target.connection_id == "conn-42"
