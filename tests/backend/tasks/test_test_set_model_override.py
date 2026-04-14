"""
Unit tests for the model_id override helpers used by generate_and_save_test_set.

Verifies that:
- _get_model_for_user calls get_user_generation_model (user default path)
- _get_override_model calls get_generation_model_with_override (per-request override)
"""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL


def _make_mock_task():
    """Create a minimal mock Celery task with required methods."""
    task = MagicMock()
    task.log_with_context = MagicMock()
    return task


@pytest.mark.unit
class TestGetModelForUser:
    """Tests for _get_model_for_user (the user-default path)."""

    @patch("rhesis.backend.app.utils.user_model_utils.get_user_generation_model")
    @patch("rhesis.backend.app.crud.get_user")
    @patch("rhesis.backend.tasks.test_set.get_db_with_tenant_variables")
    def test_calls_get_user_generation_model(
        self, mock_get_db, mock_get_user, mock_gen_model
    ):
        from rhesis.backend.tasks.test_set import _get_model_for_user

        task = _make_mock_task()
        mock_user = MagicMock()
        mock_get_user.return_value = mock_user
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_gen_model.return_value = "user-default-model"

        result = _get_model_for_user(task, "org-1", "user-1")

        mock_gen_model.assert_called_once_with(mock_db, mock_user)
        assert result == "user-default-model"

    @patch("rhesis.backend.app.crud.get_user")
    @patch("rhesis.backend.tasks.test_set.get_db_with_tenant_variables")
    def test_falls_back_when_user_not_found(self, mock_get_db, mock_get_user):
        from rhesis.backend.tasks.test_set import _get_model_for_user

        task = _make_mock_task()
        mock_get_user.return_value = None
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = _get_model_for_user(task, "org-1", "user-1")

        assert result == DEFAULT_GENERATION_MODEL


@pytest.mark.unit
class TestGetOverrideModel:
    """Tests for _get_override_model (the per-request override path)."""

    @patch(
        "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
    )
    @patch("rhesis.backend.app.crud.get_user")
    @patch("rhesis.backend.tasks.test_set.get_db_with_tenant_variables")
    def test_calls_get_generation_model_with_override(
        self, mock_get_db, mock_get_user, mock_override
    ):
        from rhesis.backend.tasks.test_set import _get_override_model

        task = _make_mock_task()
        mock_user = MagicMock()
        mock_get_user.return_value = mock_user
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_override.return_value = "override-model"

        result = _get_override_model(task, "org-1", "user-1", "model-uuid-789")

        mock_override.assert_called_once_with(
            mock_db, mock_user, model_id="model-uuid-789"
        )
        assert result == "override-model"

    @patch("rhesis.backend.app.crud.get_user")
    @patch("rhesis.backend.tasks.test_set.get_db_with_tenant_variables")
    def test_falls_back_when_user_not_found(self, mock_get_db, mock_get_user):
        from rhesis.backend.tasks.test_set import _get_override_model

        task = _make_mock_task()
        mock_get_user.return_value = None
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = _get_override_model(task, "org-1", "user-1", "model-uuid-789")

        assert result == DEFAULT_GENERATION_MODEL
