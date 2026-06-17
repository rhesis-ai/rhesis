import pytest
from fastapi import HTTPException

from rhesis.backend.app.routers.tools import (
    _validate_shortcut_credentials,
    _validate_shortcut_workflow_id,
)


def test_validate_shortcut_credentials_requires_token():
    with pytest.raises(HTTPException) as exc_info:
        _validate_shortcut_credentials({})

    assert exc_info.value.status_code == 400
    assert "SHORTCUT_API_TOKEN" in exc_info.value.detail


def test_validate_shortcut_workflow_id_rejects_empty_string():
    with pytest.raises(HTTPException) as exc_info:
        _validate_shortcut_workflow_id({"workflow_id": "   "})

    assert exc_info.value.status_code == 400
    assert "workflow_id" in exc_info.value.detail


def test_validate_shortcut_workflow_id_allows_missing_key():
    _validate_shortcut_workflow_id({})
    _validate_shortcut_workflow_id(None)
