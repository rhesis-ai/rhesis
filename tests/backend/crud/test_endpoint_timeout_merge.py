"""Tests for _set_metadata_timeout in endpoint CRUD."""

from unittest.mock import Mock

from rhesis.backend.app.crud.endpoint import _set_metadata_timeout


class TestSetMetadataTimeout:
    def test_sets_timeout_in_empty_metadata(self):
        ep = Mock()
        ep.endpoint_metadata = None
        _set_metadata_timeout(ep, 60)
        assert ep.endpoint_metadata == {"timeout_seconds": 60}

    def test_merges_without_overwriting_other_keys(self):
        ep = Mock()
        ep.endpoint_metadata = {"sdk_connection": {"function_name": "fn"}}
        _set_metadata_timeout(ep, 120)
        assert ep.endpoint_metadata == {
            "sdk_connection": {"function_name": "fn"},
            "timeout_seconds": 120,
        }

    def test_overwrites_existing_timeout(self):
        ep = Mock()
        ep.endpoint_metadata = {"timeout_seconds": 30}
        _set_metadata_timeout(ep, 90)
        assert ep.endpoint_metadata == {"timeout_seconds": 90}

    def test_none_clears_timeout(self):
        ep = Mock()
        ep.endpoint_metadata = {"timeout_seconds": 30, "sdk_connection": {"function_name": "fn"}}
        _set_metadata_timeout(ep, None)
        assert ep.endpoint_metadata == {"sdk_connection": {"function_name": "fn"}}
        assert "timeout_seconds" not in ep.endpoint_metadata

    def test_none_on_empty_metadata_is_noop(self):
        ep = Mock()
        ep.endpoint_metadata = None
        _set_metadata_timeout(ep, None)
        assert ep.endpoint_metadata == {}
