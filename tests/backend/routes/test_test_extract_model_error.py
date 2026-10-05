"""Save-as-test (``POST /tests/extract-from-conversation``) returns the shared model error code."""

from unittest.mock import patch

import pytest
from fastapi import status

from rhesis.backend.app.utils.model_errors import MODEL_NOT_CONFIGURED, ModelConfigurationError

_RESOLVE = "rhesis.backend.app.utils.user_model_utils.resolve_model"
_BODY = {
    "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
    "test_type": "Single-Turn",
}


@pytest.mark.integration
class TestExtractFromConversationModelError:
    def test_deployment_default_unbuildable_returns_code(self, authenticated_client):
        with patch(_RESOLVE, side_effect=ValueError("RHESIS_API_KEY is not set")):
            response = authenticated_client.post("/tests/extract-from-conversation", json=_BODY)

        # Same status as before; the code and the Models page hint are what is new.
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        detail = response.json()["detail"]
        assert detail["error_code"] == MODEL_NOT_CONFIGURED
        assert "Models page" in detail["message"]
        assert "RHESIS_API_KEY" not in detail["message"]
        assert "DEFAULT_GENERATION_MODEL" in detail["deployment_hint"]

    def test_own_model_error_is_worded_like_execute(self, authenticated_client):
        error = ModelConfigurationError("Your configured model 'Mine' needs an API key")
        with patch(_RESOLVE, side_effect=error):
            response = authenticated_client.post("/tests/extract-from-conversation", json=_BODY)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        detail = response.json()["detail"]
        assert detail["error_code"] == MODEL_NOT_CONFIGURED
        assert detail["message"] == (
            "Cannot create a test from this conversation due to a problem with your "
            "configured model: Your configured model 'Mine' needs an API key. Please check "
            "your model settings in the Models page."
        )

    def test_bad_input_is_still_a_plain_400(self, authenticated_client):
        body = {"messages": [{"role": "assistant", "content": "hello"}], "test_type": "Single-Turn"}
        response = authenticated_client.post("/tests/extract-from-conversation", json=body)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert isinstance(response.json()["detail"], str)
