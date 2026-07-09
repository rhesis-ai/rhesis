import pytest

from rhesis.backend.app.schemas.services import TestToolConnectionRequest


def test_test_connection_request_allows_saved_tool_credential_override():
    request = TestToolConnectionRequest.model_validate(
        {
            "tool_id": "11111111-1111-1111-1111-111111111111",
            "credentials": {"AZURE_DEVOPS_PAT": "new-token"},
            "tool_metadata": {"project": "MyProject"},
        }
    )

    assert request.tool_id is not None
    assert request.credentials == {"AZURE_DEVOPS_PAT": "new-token"}


def test_test_connection_request_rejects_tool_id_with_provider_type_id():
    with pytest.raises(ValueError, match="provider_type_id"):
        TestToolConnectionRequest.model_validate(
            {
                "tool_id": "11111111-1111-1111-1111-111111111111",
                "provider_type_id": "22222222-2222-2222-2222-222222222222",
                "credentials": {"AZURE_DEVOPS_PAT": "new-token"},
            }
        )
