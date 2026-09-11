"""Tests for _merge_timeout_into_metadata in endpoint CRUD."""

from unittest.mock import Mock

from rhesis.backend.app.crud.endpoint import _merge_timeout_into_metadata


class TestMergeTimeoutIntoMetadata:
    def test_sets_timeout_in_empty_metadata(self):
        ep = Mock()
        ep.endpoint_metadata = None
        _merge_timeout_into_metadata(ep, 60)
        assert ep.endpoint_metadata == {"timeout_seconds": 60}

    def test_merges_without_overwriting_other_keys(self):
        ep = Mock()
        ep.endpoint_metadata = {"sdk_connection": {"function_name": "fn"}}
        _merge_timeout_into_metadata(ep, 120)
        assert ep.endpoint_metadata == {
            "sdk_connection": {"function_name": "fn"},
            "timeout_seconds": 120,
        }

    def test_overwrites_existing_timeout(self):
        ep = Mock()
        ep.endpoint_metadata = {"timeout_seconds": 30}
        _merge_timeout_into_metadata(ep, 90)
        assert ep.endpoint_metadata == {"timeout_seconds": 90}

    def test_none_timeout_is_noop(self):
        ep = Mock()
        ep.endpoint_metadata = {"timeout_seconds": 30}
        _merge_timeout_into_metadata(ep, None)
        assert ep.endpoint_metadata == {"timeout_seconds": 30}
