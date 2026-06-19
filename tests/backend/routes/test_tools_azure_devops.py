import pytest
from fastapi import HTTPException

from rhesis.backend.app.routers.tools import (
    _merge_azure_devops_credentials_on_update,
    _validate_azure_devops_credentials,
    _validate_azure_devops_project,
)


def test_validate_azure_devops_credentials_requires_org_url():
    with pytest.raises(HTTPException) as exc_info:
        _validate_azure_devops_credentials({"AZURE_DEVOPS_PAT": "token"})

    assert exc_info.value.status_code == 400
    assert "AZURE_DEVOPS_ORG_URL" in exc_info.value.detail


def test_validate_azure_devops_credentials_requires_pat():
    with pytest.raises(HTTPException) as exc_info:
        _validate_azure_devops_credentials({"AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/org"})

    assert exc_info.value.status_code == 400
    assert "AZURE_DEVOPS_PAT" in exc_info.value.detail


def test_validate_azure_devops_credentials_accepts_full_credentials():
    _validate_azure_devops_credentials(
        {
            "AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/org",
            "AZURE_DEVOPS_PAT": "token",
        }
    )


def test_validate_azure_devops_project_requires_metadata():
    with pytest.raises(HTTPException) as exc_info:
        _validate_azure_devops_project(None)

    assert exc_info.value.status_code == 400
    assert "project" in exc_info.value.detail


def test_validate_azure_devops_project_rejects_empty_string():
    with pytest.raises(HTTPException) as exc_info:
        _validate_azure_devops_project({"project": "   "})

    assert exc_info.value.status_code == 400
    assert "project" in exc_info.value.detail


def test_validate_azure_devops_project_accepts_non_empty_string():
    _validate_azure_devops_project({"project": "MyProject"})


def test_merge_azure_devops_credentials_preserves_org_url():
    merged = _merge_azure_devops_credentials_on_update(
        '{"AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/org", "AZURE_DEVOPS_PAT": "old"}',
        {"AZURE_DEVOPS_PAT": "new"},
    )

    assert merged["AZURE_DEVOPS_ORG_URL"] == "https://dev.azure.com/org"
    assert merged["AZURE_DEVOPS_PAT"] == "new"


def test_merge_azure_devops_credentials_keeps_incoming_org_url():
    merged = _merge_azure_devops_credentials_on_update(
        '{"AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/old", "AZURE_DEVOPS_PAT": "old"}',
        {
            "AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/new",
            "AZURE_DEVOPS_PAT": "new",
        },
    )

    assert merged["AZURE_DEVOPS_ORG_URL"] == "https://dev.azure.com/new"
