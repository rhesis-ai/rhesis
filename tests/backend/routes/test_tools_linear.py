import pytest
from fastapi import HTTPException

from rhesis.backend.app.routers.tools import (
    _validate_linear_credentials,
    _validate_linear_team_id,
)


def test_validate_linear_credentials_requires_api_key():
    with pytest.raises(HTTPException) as exc_info:
        _validate_linear_credentials({})

    assert exc_info.value.status_code == 400
    assert "LINEAR_API_KEY" in exc_info.value.detail


def test_validate_linear_team_id_rejects_empty_string():
    with pytest.raises(HTTPException) as exc_info:
        _validate_linear_team_id({"team_id": "   "})

    assert exc_info.value.status_code == 400
    assert "team_id" in exc_info.value.detail


def test_validate_linear_team_id_allows_missing_key():
    _validate_linear_team_id({})
    _validate_linear_team_id(None)
