import json
import uuid
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from rhesis.backend.app.routers.tools import (
    _merge_gitlab_credentials_on_update,
    _validate_gitlab_credentials,
    _validate_gitlab_project,
    _validate_provider_type_switch,
)


def test_validate_gitlab_credentials_requires_token():
    with pytest.raises(HTTPException) as exc_info:
        _validate_gitlab_credentials({})

    assert exc_info.value.status_code == 400
    assert "GITLAB_PERSONAL_ACCESS_TOKEN" in exc_info.value.detail


def test_validate_gitlab_project_requires_namespace():
    with pytest.raises(HTTPException) as exc_info:
        _validate_gitlab_project({})

    assert exc_info.value.status_code == 400
    assert "project" in exc_info.value.detail


def test_validate_gitlab_project_rejects_invalid_namespace():
    with pytest.raises(HTTPException) as exc_info:
        _validate_gitlab_project({"project": {"namespace": "invalid"}})

    assert exc_info.value.status_code == 400
    assert "namespace" in exc_info.value.detail


def test_validate_gitlab_project_accepts_group_project():
    _validate_gitlab_project({"project": {"namespace": "my-group/my-project"}})


def test_merge_gitlab_credentials_preserves_existing_api_url():
    existing = json.dumps(
        {
            "GITLAB_PERSONAL_ACCESS_TOKEN": "old-token",
            "GITLAB_API_URL": "https://gitlab.example.com/api/v4",
        }
    )
    incoming = {"GITLAB_PERSONAL_ACCESS_TOKEN": "new-token"}

    merged = _merge_gitlab_credentials_on_update(existing, incoming)

    assert merged["GITLAB_PERSONAL_ACCESS_TOKEN"] == "new-token"
    assert merged["GITLAB_API_URL"] == "https://gitlab.example.com/api/v4"


def test_merge_gitlab_credentials_prefers_incoming_api_url():
    existing = json.dumps(
        {
            "GITLAB_PERSONAL_ACCESS_TOKEN": "old-token",
            "GITLAB_API_URL": "https://gitlab.example.com/api/v4",
        }
    )
    incoming = {
        "GITLAB_PERSONAL_ACCESS_TOKEN": "new-token",
        "GITLAB_API_URL": "https://gitlab.new.example.com/api/v4",
    }

    merged = _merge_gitlab_credentials_on_update(existing, incoming)

    assert merged["GITLAB_API_URL"] == "https://gitlab.new.example.com/api/v4"


def test_validate_provider_type_switch_requires_credentials_and_metadata():
    existing_tool = Mock()
    existing_tool.tool_provider_type_id = uuid.uuid4()

    new_provider_type_id = uuid.uuid4()
    provider_type = Mock()
    provider_type.type_value = "gitlab"

    tool_update = Mock()
    tool_update.tool_provider_type_id = new_provider_type_id
    tool_update.credentials = None
    tool_update.tool_metadata = {"project": {"namespace": "group/project"}}

    with pytest.raises(HTTPException) as exc_info:
        _validate_provider_type_switch(existing_tool, tool_update, provider_type)

    assert exc_info.value.status_code == 400
    assert "credentials" in exc_info.value.detail
