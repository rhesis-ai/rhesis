"""Tests for Architect session create with optional initial_message."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.schemas.architect import ArchitectSessionCreate
from rhesis.backend.app.services.architect.session_start import (
    start_session_with_message,
)


@pytest.mark.unit
class TestArchitectSessionCreateSchema:
    def test_initial_message_optional(self):
        create = ArchitectSessionCreate(title="Hello")
        assert create.initial_message is None

    def test_initial_message_accepted(self):
        create = ArchitectSessionCreate(
            title="Insights summary",
            initial_message="Summarize insights for the Insights page",
        )
        assert create.initial_message.startswith("Summarize insights")


@pytest.mark.unit
class TestStartSessionWithMessage:
    def test_persists_message_and_dispatches_celery(self):
        db = MagicMock()
        session_id = uuid4()
        project_id = uuid4()
        db_session = MagicMock()
        db_session.id = session_id
        db_session.project_id = project_id

        with (
            patch(
                "rhesis.backend.app.services.architect.session_start.crud"
            ) as mock_crud,
            patch(
                "rhesis.backend.tasks.architect.architect_chat_task"
            ) as mock_task,
        ):
            start_session_with_message(
                db=db,
                db_session=db_session,
                user_message="Summarize insights\ntest results",
                organization_id=str(uuid4()),
                user_id=str(uuid4()),
            )

            mock_crud.create_architect_message.assert_called_once()
            message_arg = mock_crud.create_architect_message.call_args.kwargs[
                "message"
            ]
            assert message_arg.role == "user"
            assert message_arg.content.startswith("Summarize insights")
            assert str(message_arg.session_id) == str(session_id)
            assert str(message_arg.project_id) == str(project_id)

            mock_task.apply_async.assert_called_once()
            kwargs = mock_task.apply_async.call_args.kwargs["kwargs"]
            assert kwargs["session_id"] == str(session_id)
            assert "Summarize insights" in kwargs["user_message"]
            headers = mock_task.apply_async.call_args.kwargs["headers"]
            assert headers["project_id"] == str(project_id)
