import pytest
from fastapi import HTTPException

from rhesis.backend.app.routers.tools import (
    _validate_asana_credentials,
    _validate_asana_workspace_gid,
)


def test_validate_asana_credentials_requires_token():
    with pytest.raises(HTTPException) as exc_info:
        _validate_asana_credentials({})

    assert exc_info.value.status_code == 400
    assert "ASANA_ACCESS_TOKEN" in exc_info.value.detail


def test_validate_asana_workspace_gid_rejects_empty_string():
    with pytest.raises(HTTPException) as exc_info:
        _validate_asana_workspace_gid({"workspace_gid": "   "})

    assert exc_info.value.status_code == 400
    assert "workspace_gid" in exc_info.value.detail


def test_validate_asana_workspace_gid_allows_missing_key():
    _validate_asana_workspace_gid({})
    _validate_asana_workspace_gid(None)
