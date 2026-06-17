import pytest
from fastapi import HTTPException

from rhesis.backend.app.routers.tools import _validate_mcp_test_connection_request


def test_mcp_test_connection_validates_shortcut_credentials():
    with pytest.raises(HTTPException) as exc_info:
        _validate_mcp_test_connection_request("shortcut", {}, None)

    assert exc_info.value.status_code == 400
    assert "SHORTCUT_API_TOKEN" in exc_info.value.detail


def test_mcp_test_connection_skips_when_credentials_omitted():
    _validate_mcp_test_connection_request("shortcut", None, None)
