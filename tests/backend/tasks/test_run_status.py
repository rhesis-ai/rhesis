"""
Tests for test run status management.

Verifies:
1. RunStatus enum includes Queued status
2. create_test_run defaults to Queued status
3. create_test_run supports explicit initial_status for backward compat
4. update_test_run_status handles Queued -> Progress transition
"""

from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from rhesis.backend.tasks.enums import RunStatus
from rhesis.backend.tasks.execution.run import create_test_run, update_test_run_status


class TestRunStatusEnum:
    """Test RunStatus enum values."""

    def test_queued_status_exists(self):
        assert RunStatus.QUEUED.value == "Queued"

    def test_progress_status_exists(self):
        assert RunStatus.PROGRESS.value == "Progress"

    def test_all_statuses_present(self):
        expected = {"Queued", "Progress", "Completed", "Partial", "Failed"}
        actual = {s.value for s in RunStatus}
        assert actual == expected


def _make_test_config(test_set_id=None):
    """Create a mock test configuration."""
    config = Mock()
    config.id = uuid4()
    config.organization_id = uuid4()
    config.user_id = uuid4()
    config.test_set_id = test_set_id or uuid4()
    return config


def _mock_session_with_test_count(count=5):
    """Create a mock session that returns a test count query."""
    session = MagicMock()
    (
        session.query.return_value.select_from.return_value.filter.return_value.scalar.return_value
    ) = count
    return session


class TestCreateTestRun:
    """Test create_test_run function."""

    @patch("rhesis.backend.tasks.execution.run.crud")
    @patch("rhesis.backend.tasks.execution.run.get_or_create_status")
    def test_defaults_to_queued_status(self, mock_get_status, mock_crud):
        """Test that create_test_run uses Queued as default status."""
        mock_status = Mock()
        mock_status.id = uuid4()
        mock_get_status.return_value = mock_status

        mock_test_config = _make_test_config()
        mock_crud.create_test_run.return_value = Mock()
        mock_crud.schemas.TestRunCreate = MagicMock()

        session = _mock_session_with_test_count()
        create_test_run(session, mock_test_config)

        mock_get_status.assert_called_once_with(
            session,
            "Queued",
            "TestRun",
            organization_id=str(mock_test_config.organization_id),
        )

    @patch("rhesis.backend.tasks.execution.run.crud")
    @patch("rhesis.backend.tasks.execution.run.get_or_create_status")
    def test_explicit_progress_status(self, mock_get_status, mock_crud):
        """Test backward compat: create_test_run with explicit PROGRESS."""
        mock_status = Mock()
        mock_status.id = uuid4()
        mock_get_status.return_value = mock_status

        mock_test_config = _make_test_config()
        mock_crud.create_test_run.return_value = Mock()
        mock_crud.schemas.TestRunCreate = MagicMock()

        session = _mock_session_with_test_count()
        create_test_run(session, mock_test_config, initial_status=RunStatus.PROGRESS)

        mock_get_status.assert_called_once_with(
            session,
            "Progress",
            "TestRun",
            organization_id=str(mock_test_config.organization_id),
        )

    @patch("rhesis.backend.tasks.execution.run.crud")
    @patch("rhesis.backend.tasks.execution.run.get_or_create_status")
    def test_queued_does_not_set_started_at(self, mock_get_status, mock_crud):
        """Queued runs should not have started_at in attributes."""
        mock_status = Mock()
        mock_status.id = uuid4()
        mock_get_status.return_value = mock_status

        mock_test_config = _make_test_config()
        mock_crud.create_test_run.return_value = Mock()
        mock_crud.schemas.TestRunCreate = MagicMock()

        session = _mock_session_with_test_count(5)
        create_test_run(session, mock_test_config)

        call_kwargs = mock_crud.schemas.TestRunCreate.call_args.kwargs
        assert "started_at" not in call_kwargs["attributes"]
        assert call_kwargs["attributes"]["task_state"] == "Queued"
        assert call_kwargs["attributes"]["total_tests"] == 5

    @patch("rhesis.backend.tasks.execution.run.crud")
    @patch("rhesis.backend.tasks.execution.run.get_or_create_status")
    def test_progress_sets_started_at(self, mock_get_status, mock_crud):
        """Progress runs should have started_at in attributes."""
        mock_status = Mock()
        mock_status.id = uuid4()
        mock_get_status.return_value = mock_status

        mock_test_config = _make_test_config()
        mock_crud.create_test_run.return_value = Mock()
        mock_crud.schemas.TestRunCreate = MagicMock()

        session = _mock_session_with_test_count()
        create_test_run(session, mock_test_config, initial_status=RunStatus.PROGRESS)

        call_kwargs = mock_crud.schemas.TestRunCreate.call_args.kwargs
        assert "started_at" in call_kwargs["attributes"]
        assert call_kwargs["attributes"]["task_state"] == "Progress"

    @patch("rhesis.backend.tasks.execution.run.crud")
    @patch("rhesis.backend.tasks.execution.run.get_or_create_status")
    def test_task_info_optional(self, mock_get_status, mock_crud):
        """create_test_run should work without task_info."""
        mock_status = Mock()
        mock_status.id = uuid4()
        mock_get_status.return_value = mock_status

        mock_test_config = _make_test_config()
        mock_test_run = Mock()
        mock_crud.create_test_run.return_value = mock_test_run
        mock_crud.schemas.TestRunCreate = MagicMock()

        session = _mock_session_with_test_count()
        result = create_test_run(session, mock_test_config)

        assert result == mock_test_run
        call_kwargs = mock_crud.schemas.TestRunCreate.call_args.kwargs
        assert "task_id" not in call_kwargs["attributes"]

    @patch("rhesis.backend.tasks.execution.run.crud")
    @patch("rhesis.backend.tasks.execution.run.get_or_create_status")
    def test_total_tests_stored_in_attributes(self, mock_get_status, mock_crud):
        """total_tests should be set from test set count."""
        mock_status = Mock()
        mock_status.id = uuid4()
        mock_get_status.return_value = mock_status

        mock_test_config = _make_test_config()
        mock_crud.create_test_run.return_value = Mock()
        mock_crud.schemas.TestRunCreate = MagicMock()

        session = _mock_session_with_test_count(12)
        create_test_run(session, mock_test_config)

        call_kwargs = mock_crud.schemas.TestRunCreate.call_args.kwargs
        assert call_kwargs["attributes"]["total_tests"] == 12


class TestUpdateTestRunStatus:
    """Test update_test_run_status with Queued status."""

    @patch("rhesis.backend.tasks.execution.run.crud")
    @patch("rhesis.backend.tasks.execution.run.get_or_create_status")
    def test_queued_to_progress_transition(self, mock_get_status, mock_crud):
        """Test transitioning a test run from Queued to Progress."""
        mock_status = Mock()
        mock_status.id = uuid4()
        mock_get_status.return_value = mock_status

        mock_test_run = Mock()
        mock_test_run.id = uuid4()
        mock_test_run.organization_id = uuid4()
        mock_test_run.user_id = uuid4()
        mock_test_run.attributes = {"task_state": "Queued"}

        mock_crud.schemas.TestRunUpdate = MagicMock()

        session = MagicMock()
        update_test_run_status(session, mock_test_run, RunStatus.PROGRESS.value)

        assert mock_test_run.attributes["task_state"] == "Progress"
        assert mock_test_run.attributes["status"] == "Progress"
        assert "completed_at" not in mock_test_run.attributes

    @patch("rhesis.backend.tasks.execution.run.crud")
    @patch("rhesis.backend.tasks.execution.run.get_or_create_status")
    def test_queued_status_no_completed_at(self, mock_get_status, mock_crud):
        """Setting status to Queued should not add completed_at."""
        mock_status = Mock()
        mock_status.id = uuid4()
        mock_get_status.return_value = mock_status

        mock_test_run = Mock()
        mock_test_run.id = uuid4()
        mock_test_run.organization_id = uuid4()
        mock_test_run.user_id = uuid4()
        mock_test_run.attributes = {}

        mock_crud.schemas.TestRunUpdate = MagicMock()

        session = MagicMock()
        update_test_run_status(session, mock_test_run, RunStatus.QUEUED.value)

        assert mock_test_run.attributes["task_state"] == "Queued"
        assert "completed_at" not in mock_test_run.attributes
