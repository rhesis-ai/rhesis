"""Tests for the version-of-the-system-under-test snapshot.

The point of the snapshot is that a finished run keeps reporting the version that actually
produced its results, even after the endpoint is edited. Most of these tests are about that
invariant and about the run never being blocked by a bad value.
"""

import uuid
from unittest.mock import Mock

from rhesis.backend.app.services.version_info import (
    SOURCE_ENDPOINT,
    SOURCE_RESCORE,
    SOURCE_RESPONSE,
    VERSION_INFO_KEY,
    VERSION_INFO_SOURCE_KEY,
    apply_reported_version_info,
    apply_version_snapshot_to_run_attributes,
    version_info_from_run_attributes,
)


def _config(*, version_info=None, attributes=None, endpoint_id=uuid.uuid4()):
    """A test configuration whose endpoint carries ``version_info``."""
    endpoint = Mock()
    endpoint.version_info = version_info
    config = Mock()
    config.endpoint_id = endpoint_id
    config.attributes = attributes
    db = Mock()
    db.get.return_value = endpoint
    return db, config


class TestStaticSnapshot:
    def test_records_configured_version(self):
        db, config = _config(version_info={"prompt_version": "v3.2"})
        attributes = {}

        apply_version_snapshot_to_run_attributes(db, test_config=config, attributes=attributes)

        assert attributes[VERSION_INFO_KEY] == {"prompt_version": "v3.2"}
        assert attributes[VERSION_INFO_SOURCE_KEY] == SOURCE_ENDPOINT

    def test_writes_nothing_when_endpoint_has_no_version(self):
        db, config = _config(version_info=None)
        attributes = {}

        apply_version_snapshot_to_run_attributes(db, test_config=config, attributes=attributes)

        assert attributes == {}

    def test_writes_nothing_for_empty_object(self):
        """An empty dict is 'not configured', not a version worth showing."""
        db, config = _config(version_info={})
        attributes = {}

        apply_version_snapshot_to_run_attributes(db, test_config=config, attributes=attributes)

        assert VERSION_INFO_KEY not in attributes

    def test_invalid_stored_value_is_dropped_not_raised(self):
        """A bad row must not stop the run from being created."""
        too_deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": 1}}}}}}}}}
        db, config = _config(version_info=too_deep)
        attributes = {}

        apply_version_snapshot_to_run_attributes(db, test_config=config, attributes=attributes)

        assert VERSION_INFO_KEY not in attributes

    def test_preserves_existing_attributes(self):
        db, config = _config(version_info={"v": "1"})
        attributes = {"total_tests": 7}

        apply_version_snapshot_to_run_attributes(db, test_config=config, attributes=attributes)

        assert attributes["total_tests"] == 7

    def test_no_endpoint_id_is_a_no_op(self):
        db, config = _config()
        config.endpoint_id = None
        attributes = {}

        apply_version_snapshot_to_run_attributes(db, test_config=config, attributes=attributes)

        assert attributes == {}


class TestRescoreCarryOver:
    """A rescore invokes no endpoint, so it must inherit, never re-read."""

    def test_carries_version_from_reference_run(self):
        reference = Mock()
        reference.attributes = {
            VERSION_INFO_KEY: {"prompt_version": "v1"},
            VERSION_INFO_SOURCE_KEY: SOURCE_RESPONSE,
        }
        db = Mock()
        db.get.return_value = reference
        config = Mock()
        config.endpoint_id = uuid.uuid4()
        config.attributes = {"is_rescore": True, "reference_test_run_id": str(uuid.uuid4())}
        attributes = {}

        apply_version_snapshot_to_run_attributes(db, test_config=config, attributes=attributes)

        assert attributes[VERSION_INFO_KEY] == {"prompt_version": "v1"}
        assert attributes[VERSION_INFO_SOURCE_KEY] == SOURCE_RESCORE

    def test_does_not_fall_back_to_the_endpoint(self):
        """The endpoint may have moved on since; its version never produced these outputs."""
        reference = Mock()
        reference.attributes = {}
        db = Mock()
        db.get.return_value = reference
        config = Mock()
        config.endpoint_id = uuid.uuid4()
        config.attributes = {"is_rescore": True, "reference_test_run_id": str(uuid.uuid4())}
        attributes = {}

        apply_version_snapshot_to_run_attributes(db, test_config=config, attributes=attributes)

        assert VERSION_INFO_KEY not in attributes

    def test_malformed_reference_id_is_survivable(self):
        db = Mock()
        config = Mock()
        config.endpoint_id = uuid.uuid4()
        config.attributes = {"is_rescore": True, "reference_test_run_id": "not-a-uuid"}
        attributes = {}

        apply_version_snapshot_to_run_attributes(db, test_config=config, attributes=attributes)

        assert VERSION_INFO_KEY not in attributes


class TestReportedOverride:
    def _run(self):
        test_run = Mock()
        test_run.id = uuid.uuid4()
        test_run.organization_id = uuid.uuid4()
        return test_run

    def test_reported_version_overrides_the_snapshot(self, monkeypatch):
        monkeypatch.setattr(
            "rhesis.backend.app.crud.test_result.get_first_reported_version_info",
            lambda *a, **k: {"prompt_version": "v9"},
        )
        attributes = {
            VERSION_INFO_KEY: {"prompt_version": "v3"},
            VERSION_INFO_SOURCE_KEY: SOURCE_ENDPOINT,
        }

        apply_reported_version_info(Mock(), test_run=self._run(), attributes=attributes)

        assert attributes[VERSION_INFO_KEY] == {"prompt_version": "v9"}
        assert attributes[VERSION_INFO_SOURCE_KEY] == SOURCE_RESPONSE

    def test_snapshot_survives_when_nothing_was_reported(self, monkeypatch):
        """Only ever sets -- never blanks what creation recorded."""
        monkeypatch.setattr(
            "rhesis.backend.app.crud.test_result.get_first_reported_version_info",
            lambda *a, **k: None,
        )
        attributes = {
            VERSION_INFO_KEY: {"prompt_version": "v3"},
            VERSION_INFO_SOURCE_KEY: SOURCE_ENDPOINT,
        }

        apply_reported_version_info(Mock(), test_run=self._run(), attributes=attributes)

        assert attributes[VERSION_INFO_KEY] == {"prompt_version": "v3"}
        assert attributes[VERSION_INFO_SOURCE_KEY] == SOURCE_ENDPOINT

    def test_oversize_reported_value_is_ignored(self, monkeypatch):
        """The reported value comes from the client's own server -- it is the less trusted one."""
        monkeypatch.setattr(
            "rhesis.backend.app.crud.test_result.get_first_reported_version_info",
            lambda *a, **k: {"blob": "x" * 20_000},
        )
        attributes = {
            VERSION_INFO_KEY: {"prompt_version": "v3"},
            VERSION_INFO_SOURCE_KEY: SOURCE_ENDPOINT,
        }

        apply_reported_version_info(Mock(), test_run=self._run(), attributes=attributes)

        assert attributes[VERSION_INFO_KEY] == {"prompt_version": "v3"}


class TestReadShape:
    def test_returns_value_and_source(self):
        assert version_info_from_run_attributes(
            {VERSION_INFO_KEY: {"v": "1"}, VERSION_INFO_SOURCE_KEY: SOURCE_RESPONSE}
        ) == {"value": {"v": "1"}, "source": SOURCE_RESPONSE}

    def test_defaults_source_to_endpoint(self):
        result = version_info_from_run_attributes({VERSION_INFO_KEY: {"v": "1"}})
        assert result["source"] == SOURCE_ENDPOINT

    def test_none_for_missing_or_unusable(self):
        assert version_info_from_run_attributes(None) is None
        assert version_info_from_run_attributes({}) is None
        assert version_info_from_run_attributes({VERSION_INFO_KEY: {}}) is None
        assert version_info_from_run_attributes({VERSION_INFO_KEY: "v1"}) is None
