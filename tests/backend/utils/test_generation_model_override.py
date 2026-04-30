"""
Unit tests for get_generation_model_with_override in user_model_utils.

Verifies the per-request model_id override logic:
- When model_id is None, delegates to get_user_generation_model (user default)
- When model_id is provided, calls _fetch_and_configure_model with the right args
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL
from rhesis.backend.app.models.user import User


@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    user = Mock(spec=User)
    user.id = "user-123"
    user.email = "test@example.com"
    user.organization_id = "org-456"
    user.is_active = True
    user.is_verified = True
    return user


@pytest.mark.unit
class TestGetGenerationModelWithOverride:
    """Tests for the model_id override branching logic."""

    @patch("rhesis.backend.app.utils.user_model_utils.get_user_generation_model")
    def test_no_override_delegates_to_user_default(
        self, mock_get_user_model, mock_db, mock_user
    ):
        from rhesis.backend.app.utils.user_model_utils import (
            get_generation_model_with_override,
        )

        mock_get_user_model.return_value = "default-model"

        result = get_generation_model_with_override(mock_db, mock_user, model_id=None)

        mock_get_user_model.assert_called_once_with(mock_db, mock_user)
        assert result == "default-model"

    @patch("rhesis.backend.app.utils.user_model_utils._fetch_and_configure_model")
    def test_override_calls_fetch_and_configure(
        self, mock_fetch, mock_db, mock_user
    ):
        from rhesis.backend.app.utils.user_model_utils import (
            get_generation_model_with_override,
        )

        mock_llm = Mock()
        mock_fetch.return_value = mock_llm

        result = get_generation_model_with_override(
            mock_db, mock_user, model_id="model-789"
        )

        mock_fetch.assert_called_once_with(
            db=mock_db,
            model_id="model-789",
            organization_id=str(mock_user.organization_id),
            default_model=DEFAULT_GENERATION_MODEL,
            user=mock_user,
        )
        assert result is mock_llm

    @patch("rhesis.backend.app.utils.user_model_utils.get_user_generation_model")
    def test_empty_string_model_id_delegates_to_default(
        self, mock_get_user_model, mock_db, mock_user
    ):
        """Empty string is falsy, so should fall back to user default."""
        from rhesis.backend.app.utils.user_model_utils import (
            get_generation_model_with_override,
        )

        mock_get_user_model.return_value = "default-model"

        result = get_generation_model_with_override(mock_db, mock_user, model_id="")

        mock_get_user_model.assert_called_once_with(mock_db, mock_user)
        assert result == "default-model"

    @patch("rhesis.backend.app.utils.user_model_utils._fetch_and_configure_model")
    def test_override_uses_user_org_for_security(
        self, mock_fetch, mock_db, mock_user
    ):
        """model_id override must always use user.organization_id, not accept an external one."""
        from rhesis.backend.app.utils.user_model_utils import (
            get_generation_model_with_override,
        )

        mock_user.organization_id = "secure-org-id"
        mock_fetch.return_value = "configured-model"

        get_generation_model_with_override(
            mock_db, mock_user, model_id="any-model-id"
        )

        call_kwargs = mock_fetch.call_args[1]
        assert call_kwargs["organization_id"] == "secure-org-id"
