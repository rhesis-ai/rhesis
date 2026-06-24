import pytest
from fastapi import HTTPException

from rhesis.backend.app.routers.tools import (
    _ensure_mcp_saved_credential_override,
    _validate_mcp_test_connection_request,
)


def test_mcp_test_connection_validates_asana_credentials():
    with pytest.raises(HTTPException) as exc_info:
        _validate_mcp_test_connection_request("asana", {}, None)

    assert exc_info.value.status_code == 400
    assert "ASANA_ACCESS_TOKEN" in exc_info.value.detail


def test_mcp_test_connection_validates_asana_workspace_gid():
    with pytest.raises(HTTPException) as exc_info:
        _validate_mcp_test_connection_request(
            "asana",
            {"ASANA_ACCESS_TOKEN": "token"},
            {"workspace_gid": "   "},
        )

    assert exc_info.value.status_code == 400
    assert "workspace_gid" in exc_info.value.detail


def test_mcp_test_connection_validates_shortcut_credentials():
    with pytest.raises(HTTPException) as exc_info:
        _validate_mcp_test_connection_request("shortcut", {}, None)

    assert exc_info.value.status_code == 400
    assert "SHORTCUT_API_TOKEN" in exc_info.value.detail


def test_mcp_test_connection_validates_linear_credentials():
    with pytest.raises(HTTPException) as exc_info:
        _validate_mcp_test_connection_request("linear", {}, None)

    assert exc_info.value.status_code == 400
    assert "LINEAR_API_TOKEN" in exc_info.value.detail


def test_mcp_test_connection_validates_azure_devops_credentials():
    with pytest.raises(HTTPException) as exc_info:
        _validate_mcp_test_connection_request("azure_devops", {}, {"project": "P"})

    assert exc_info.value.status_code == 400
    assert "AZURE_DEVOPS_ORG" in exc_info.value.detail


def test_mcp_test_connection_validates_azure_devops_project():
    with pytest.raises(HTTPException) as exc_info:
        _validate_mcp_test_connection_request(
            "azure_devops",
            {
                "AZURE_DEVOPS_ORG": "contoso",
                "AZURE_DEVOPS_EMAIL": "user@example.com",
                "AZURE_DEVOPS_PAT": "token",
            },
            {"project": "   "},
        )

    assert exc_info.value.status_code == 400
    assert "project" in exc_info.value.detail


def test_mcp_test_connection_skips_when_credentials_omitted():
    _validate_mcp_test_connection_request("asana", None, None)
    _validate_mcp_test_connection_request("shortcut", None, None)
    _validate_mcp_test_connection_request("linear", None, None)
    _validate_mcp_test_connection_request("azure_devops", None, None)


def test_saved_credential_override_rejects_rest_providers():
    with pytest.raises(HTTPException) as exc_info:
        _ensure_mcp_saved_credential_override("github")

    assert exc_info.value.status_code == 400
    assert "MCP providers" in exc_info.value.detail


def test_saved_credential_override_allows_mcp_providers():
    _ensure_mcp_saved_credential_override("azure_devops")
    _ensure_mcp_saved_credential_override("gitlab")
    _ensure_mcp_saved_credential_override("linear")
