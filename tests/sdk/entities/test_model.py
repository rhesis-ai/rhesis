import os
from unittest.mock import MagicMock, patch

import pytest

os.environ["RHESIS_BASE_URL"] = "http://test:8000"

from rhesis.sdk.entities.model import Model, Models  # noqa: E402


@pytest.fixture
def mock_list_providers():
    """Mock list_providers to return a fixed list of providers."""
    with patch.object(
        Models, "list_providers", return_value=["openai", "anthropic", "gemini"]
    ) as mock:
        yield mock


def test_model_push_raises_error_when_provider_not_provided(mock_list_providers):
    """Test that pushing a model without a provider raises ValueError."""
    model = Model(
        name="Test Model",
        model_name="gpt-4",
        key="sk-test-key",
    )

    with pytest.raises(ValueError) as exc_info:
        model.push()

    assert "Provider is required" in str(exc_info.value)
    assert "openai" in str(exc_info.value)
    assert "anthropic" in str(exc_info.value)
    assert "gemini" in str(exc_info.value)


@patch("requests.request")
def test_model_push_raises_error_when_unsupported_provider(mock_request, mock_list_providers):
    """Test that pushing a model with an unsupported provider raises ValueError."""
    # Mock the API response to return empty list (provider not found)
    mock_request.return_value.json.return_value = []

    model = Model(
        name="Test Model",
        provider="unsupported_provider",
        model_name="some-model",
        key="test-key",
    )

    with pytest.raises(ValueError) as exc_info:
        model.push()

    assert "Unsupported provider 'unsupported_provider'" in str(exc_info.value)
    assert "openai" in str(exc_info.value)
    assert "anthropic" in str(exc_info.value)
    assert "gemini" in str(exc_info.value)


@patch("requests.request")
def test_model_push_succeeds_with_valid_provider(mock_request):
    """Test that pushing a model with a valid provider succeeds."""
    # Mock the provider lookup response
    mock_request.return_value.json.side_effect = [
        # First call: provider lookup returns a valid provider
        [{"id": "provider-uuid-123", "type_value": "openai", "type_name": "ProviderType"}],
        # Second call: model creation response
        {"id": "model-uuid-456", "name": "Test Model", "provider_type_id": "provider-uuid-123"},
    ]

    model = Model(
        name="Test Model",
        provider="openai",
        model_name="gpt-4",
        key="sk-test-key",
    )

    result = model.push()

    assert result is not None
    assert model.provider_type_id == "provider-uuid-123"


# ================================================================
# Tests for set_default_execution()
# ================================================================


class TestSetDefaultExecution:
    """Tests for Model.set_default_execution()."""

    @patch("requests.request")
    def test_set_default_execution_sends_correct_payload(self, mock_request):
        """PATCH is sent with the execution model settings payload."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response

        model = Model(id="model-123", name="Test Model")
        model.set_default_execution()

        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        assert kwargs["method"] == "PATCH"
        assert "settings" in kwargs["url"]
        assert kwargs["json"] == {
            "models": {"execution": {"model_id": "model-123"}}
        }

    def test_set_default_execution_without_id_raises(self):
        """ValueError when model has no ID."""
        model = Model(name="Unsaved Model")
        with pytest.raises(ValueError, match="Model must be saved before setting as default"):
            model.set_default_execution()
