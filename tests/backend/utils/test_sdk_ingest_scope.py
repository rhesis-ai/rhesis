"""sdk_ingest_scope resolves the tenant the backend's own SDK spans land in."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from rhesis.backend.app.utils import observability

_CLIENT = "rhesis.sdk.decorators._state.get_default_client"


@pytest.fixture(autouse=True)
def _fresh_scopes(monkeypatch):
    monkeypatch.setattr(observability, "_ingest_scopes", {})


@pytest.mark.integration
def test_resolves_org_of_api_key_owner(rhesis_api_key, test_org_id):
    client = SimpleNamespace(
        api_key=rhesis_api_key, project_id="12340000-0000-4000-8000-00000000abcd"
    )
    with patch(_CLIENT, return_value=client):
        assert observability.sdk_ingest_scope() == (
            test_org_id,
            "12340000-0000-4000-8000-00000000abcd",
        )


@pytest.mark.integration
def test_unknown_key_has_no_scope():
    client = SimpleNamespace(
        api_key="rh-not-a-key-on-this-instance", project_id="12340000-0000-4000-8000-00000000abcd"
    )
    with patch(_CLIENT, return_value=client):
        assert observability.sdk_ingest_scope() is None


@pytest.mark.unit
def test_no_client_or_project_has_no_scope():
    with patch(_CLIENT, return_value=None):
        assert observability.sdk_ingest_scope() is None
    with patch(_CLIENT, return_value=SimpleNamespace(api_key="rh-x", project_id=None)):
        assert observability.sdk_ingest_scope() is None
