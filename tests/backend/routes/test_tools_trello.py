import pytest
from fastapi import HTTPException

from rhesis.backend.app.routers.tools import (
    _validate_trello_credentials,
    _validate_trello_workspace_gid,
)


def test_validate_trello_credentials_requires_api_key_and_token():
    with pytest.raises(HTTPException) as exc_info:
        _validate_trello_credentials({})
    assert exc_info.value.status_code == 400
    assert "TRELLO_API_KEY" in exc_info.value.detail or "TRELLO_TOKEN" in exc_info.value.detail

    with pytest.raises(HTTPException) as exc_info:
        _validate_trello_credentials({"TRELLO_API_KEY": "key123"})
    assert exc_info.value.status_code == 400
    assert "TRELLO_TOKEN" in exc_info.value.detail

    with pytest.raises(HTTPException) as exc_info:
        _validate_trello_credentials({"TRELLO_TOKEN": "token123"})
    assert exc_info.value.status_code == 400
    assert "TRELLO_API_KEY" in exc_info.value.detail

    # Valid credentials should not raise
    _validate_trello_credentials({
        "TRELLO_API_KEY": "key123",
        "TRELLO_TOKEN": "token123",
    })


def test_validate_trello_workspace_gid_rejects_empty_string():
    with pytest.raises(HTTPException) as exc_info:
        _validate_trello_workspace_gid({"workspace_gid": "   "})
    assert exc_info.value.status_code == 400
    assert "workspace_gid" in exc_info.value.detail


def test_validate_trello_workspace_gid_allows_missing_key():
    _validate_trello_workspace_gid({})
    _validate_trello_workspace_gid(None)
