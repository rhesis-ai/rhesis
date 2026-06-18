"""
Unit tests for _resolve_generation_model used by generate_and_save_test_set.

Verifies that:
- With no model_id, the user's default is resolved
  (get_generation_model_with_override called with model_id=None)
- With a model_id, that override is passed through
- A missing user raises ValueError (no silent fallback to the default model)
"""

from unittest.mock import MagicMock, patch

import pytest


def _make_mock_task():
    """Create a minimal mock Celery task with required methods."""
    task = MagicMock()
    task.log_with_context = MagicMock()
    return task


def _mock_db_session(mock_get_db, mock_db):
    """Wire the get_db_with_tenant_variables context manager to yield mock_db."""
    mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)


@pytest.mark.unit
class TestResolveGenerationModel:
    """Tests for _resolve_generation_model."""

    @patch("rhesis.backend.tasks.test_set.get_generation_model_with_override")
    @patch("rhesis.backend.app.crud.get_user")
    @patch("rhesis.backend.tasks.test_set.get_db_with_tenant_variables")
    def test_resolves_user_default_when_no_model_id(
        self, mock_get_db, mock_get_user, mock_override
    ):
        from rhesis.backend.tasks.test_set import _resolve_generation_model

        task = _make_mock_task()
        mock_user = MagicMock()
        mock_get_user.return_value = mock_user
        mock_db = MagicMock()
        _mock_db_session(mock_get_db, mock_db)
        mock_override.return_value = "user-default-model"

        result = _resolve_generation_model(task, "org-1", "user-1", "project-1")

        mock_override.assert_called_once_with(mock_db, mock_user, model_id=None)
        assert result == "user-default-model"

    @patch("rhesis.backend.tasks.test_set.get_generation_model_with_override")
    @patch("rhesis.backend.app.crud.get_user")
    @patch("rhesis.backend.tasks.test_set.get_db_with_tenant_variables")
    def test_passes_through_override_model_id(
        self, mock_get_db, mock_get_user, mock_override
    ):
        from rhesis.backend.tasks.test_set import _resolve_generation_model

        task = _make_mock_task()
        mock_user = MagicMock()
        mock_get_user.return_value = mock_user
        mock_db = MagicMock()
        _mock_db_session(mock_get_db, mock_db)
        mock_override.return_value = "override-model"

        result = _resolve_generation_model(
            task, "org-1", "user-1", "project-1", "model-uuid-789"
        )

        mock_override.assert_called_once_with(
            mock_db, mock_user, model_id="model-uuid-789"
        )
        assert result == "override-model"

    @patch("rhesis.backend.tasks.test_set.get_generation_model_with_override")
    @patch("rhesis.backend.app.crud.get_user")
    @patch("rhesis.backend.tasks.test_set.get_db_with_tenant_variables")
    def test_passes_project_id_to_session(
        self, mock_get_db, mock_get_user, mock_override
    ):
        from rhesis.backend.tasks.test_set import _resolve_generation_model

        task = _make_mock_task()
        mock_get_user.return_value = MagicMock()
        mock_db = MagicMock()
        _mock_db_session(mock_get_db, mock_db)
        mock_override.return_value = "user-default-model"

        _resolve_generation_model(task, "org-1", "user-1", "project-1")

        mock_get_db.assert_called_once_with("org-1", "user-1", "project-1")

    @patch("rhesis.backend.app.crud.get_user")
    @patch("rhesis.backend.tasks.test_set.get_db_with_tenant_variables")
    def test_raises_when_user_not_found(self, mock_get_db, mock_get_user):
        from rhesis.backend.tasks.test_set import _resolve_generation_model

        task = _make_mock_task()
        mock_get_user.return_value = None
        mock_db = MagicMock()
        _mock_db_session(mock_get_db, mock_db)

        with pytest.raises(ValueError, match="User not found"):
            _resolve_generation_model(task, "org-1", "user-1", "project-1")
