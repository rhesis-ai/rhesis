"""Unit tests for Azure DevOps org normalization."""

import pytest

from rhesis.backend.app.services.tool.azure_devops import normalize_azure_devops_org


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("contoso", "contoso"),
        ("https://dev.azure.com/contoso", "contoso"),
        ("https://dev.azure.com/contoso/MyProject", "contoso"),
        ("dev.azure.com/contoso", "contoso"),
        ("dev.azure.com/contoso/MyProject", "contoso"),
        ("https://contoso.visualstudio.com", "contoso"),
        ("contoso.visualstudio.com", "contoso"),
    ],
)
def test_normalize_azure_devops_org_accepts_common_shapes(value, expected):
    assert normalize_azure_devops_org(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "contoso/extra",
    ],
)
def test_normalize_azure_devops_org_rejects_invalid_paths(value):
    with pytest.raises(ValueError, match="single organization name"):
        normalize_azure_devops_org(value)
