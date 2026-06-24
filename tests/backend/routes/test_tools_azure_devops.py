import pytest
from fastapi import HTTPException

from rhesis.backend.app.services.tool.azure_devops import (
    normalize_azure_devops_org,
    prepare_azure_devops_credentials,
)
from rhesis.backend.app.services.tool.credential_merge import (
    merge_azure_devops_credentials_on_update,
    resolve_mcp_test_connection_credentials,
)
from rhesis.backend.app.routers.tools import (
    _validate_azure_devops_credentials,
    _validate_azure_devops_project,
)


def test_normalize_azure_devops_org_from_dev_azure_url():
    assert (
        normalize_azure_devops_org("https://dev.azure.com/contoso/MyProject")
        == "contoso"
    )


def test_normalize_azure_devops_org_from_visualstudio_url():
    assert (
        normalize_azure_devops_org("https://contoso.visualstudio.com")
        == "contoso"
    )


def test_normalize_azure_devops_org_rejects_slash_without_url():
    with pytest.raises(ValueError, match="single organization name"):
        normalize_azure_devops_org("contoso/extra")


def test_validate_azure_devops_credentials_requires_org():
    with pytest.raises(HTTPException) as exc_info:
        _validate_azure_devops_credentials(
            {
                "AZURE_DEVOPS_EMAIL": "user@example.com",
                "AZURE_DEVOPS_PAT": "token",
            }
        )

    assert exc_info.value.status_code == 400
    assert "AZURE_DEVOPS_ORG" in exc_info.value.detail


def test_validate_azure_devops_credentials_requires_email():
    with pytest.raises(HTTPException) as exc_info:
        _validate_azure_devops_credentials(
            {"AZURE_DEVOPS_ORG": "contoso", "AZURE_DEVOPS_PAT": "token"}
        )

    assert exc_info.value.status_code == 400
    assert "AZURE_DEVOPS_EMAIL" in exc_info.value.detail


def test_validate_azure_devops_credentials_requires_pat():
    with pytest.raises(HTTPException) as exc_info:
        _validate_azure_devops_credentials(
            {
                "AZURE_DEVOPS_ORG": "contoso",
                "AZURE_DEVOPS_EMAIL": "user@example.com",
            }
        )

    assert exc_info.value.status_code == 400
    assert "AZURE_DEVOPS_PAT" in exc_info.value.detail


def test_validate_azure_devops_credentials_normalizes_dev_azure_url():
    _validate_azure_devops_credentials(
        {
            "AZURE_DEVOPS_ORG": "https://dev.azure.com/contoso",
            "AZURE_DEVOPS_EMAIL": "user@example.com",
            "AZURE_DEVOPS_PAT": "token",
        }
    )


def test_validate_azure_devops_credentials_rejects_invalid_org_path():
    with pytest.raises(HTTPException) as exc_info:
        _validate_azure_devops_credentials(
            {
                "AZURE_DEVOPS_ORG": "contoso/extra",
                "AZURE_DEVOPS_EMAIL": "user@example.com",
                "AZURE_DEVOPS_PAT": "token",
            }
        )

    assert exc_info.value.status_code == 400
    assert "single organization name" in exc_info.value.detail


def test_validate_azure_devops_credentials_accepts_full_credentials():
    _validate_azure_devops_credentials(
        {
            "AZURE_DEVOPS_ORG": "contoso",
            "AZURE_DEVOPS_EMAIL": "user@example.com",
            "AZURE_DEVOPS_PAT": "token",
        }
    )


def test_prepare_azure_devops_credentials_normalizes_org():
    prepared = prepare_azure_devops_credentials(
        {
            "AZURE_DEVOPS_ORG": "https://contoso.visualstudio.com",
            "AZURE_DEVOPS_EMAIL": "user@example.com",
            "AZURE_DEVOPS_PAT": "token",
        }
    )

    assert prepared["AZURE_DEVOPS_ORG"] == "contoso"


def test_prepare_azure_devops_credentials_strips_email_and_pat():
    prepared = prepare_azure_devops_credentials(
        {
            "AZURE_DEVOPS_ORG": "contoso",
            "AZURE_DEVOPS_EMAIL": "  user@example.com  ",
            "AZURE_DEVOPS_PAT": "  token  ",
        }
    )

    assert prepared["AZURE_DEVOPS_EMAIL"] == "user@example.com"
    assert prepared["AZURE_DEVOPS_PAT"] == "token"


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


def test_merge_azure_devops_credentials_preserves_org_and_email():
    merged = merge_azure_devops_credentials_on_update(
        (
            '{"AZURE_DEVOPS_ORG": "contoso", "AZURE_DEVOPS_EMAIL": '
            '"user@example.com", "AZURE_DEVOPS_PAT": "old"}'
        ),
        {"AZURE_DEVOPS_PAT": "new"},
    )

    assert merged["AZURE_DEVOPS_ORG"] == "contoso"
    assert merged["AZURE_DEVOPS_EMAIL"] == "user@example.com"
    assert merged["AZURE_DEVOPS_PAT"] == "new"


def test_merge_azure_devops_credentials_keeps_incoming_org():
    merged = merge_azure_devops_credentials_on_update(
        (
            '{"AZURE_DEVOPS_ORG": "old-org", "AZURE_DEVOPS_EMAIL": '
            '"user@example.com", "AZURE_DEVOPS_PAT": "old"}'
        ),
        {
            "AZURE_DEVOPS_ORG": "new-org",
            "AZURE_DEVOPS_PAT": "new",
        },
    )

    assert merged["AZURE_DEVOPS_ORG"] == "new-org"


def test_resolve_mcp_test_connection_credentials_merges_and_normalizes_org():
    merged = resolve_mcp_test_connection_credentials(
        "azure_devops",
        (
            '{"AZURE_DEVOPS_ORG": "contoso", "AZURE_DEVOPS_EMAIL": '
            '"user@example.com", "AZURE_DEVOPS_PAT": "old"}'
        ),
        {
            "AZURE_DEVOPS_ORG": "https://dev.azure.com/new-org",
            "AZURE_DEVOPS_PAT": "new",
        },
    )

    assert merged["AZURE_DEVOPS_ORG"] == "new-org"
    assert merged["AZURE_DEVOPS_EMAIL"] == "user@example.com"
    assert merged["AZURE_DEVOPS_PAT"] == "new"
