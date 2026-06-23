import pytest
from fastapi import HTTPException

from rhesis.backend.app.routers.tools import _validate_linear_credentials


def test_validate_linear_credentials_requires_api_token():
    with pytest.raises(HTTPException) as exc_info:
        _validate_linear_credentials({})

    assert exc_info.value.status_code == 400
    assert "LINEAR_API_TOKEN" in exc_info.value.detail


def test_validate_linear_credentials_accepts_token():
    _validate_linear_credentials({"LINEAR_API_TOKEN": "token"})
