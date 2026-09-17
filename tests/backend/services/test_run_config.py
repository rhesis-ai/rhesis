"""Tests for the run configuration snapshot.

The invariant under test: a finished run reports the options it actually executed with,
and editing or re-executing its TestConfiguration afterwards cannot change that.
"""

import uuid
from unittest.mock import Mock

import pytest

from rhesis.backend.app.services.run_config import (
    RUN_CONFIG_KEY,
    SNAPSHOT_KEYS,
    record_resolved_evaluation_model,
    snapshot_run_config,
)


def _config(attributes):
    config = Mock()
    config.attributes = attributes
    return config


class TestSnapshotRunConfig:
    def test_copies_the_displayed_options(self):
        attributes = {}
        snapshot_run_config(
            test_config=_config(
                {
                    "execution_mode": "Sequential",
                    "is_rescore": True,
                    "metrics_source": "requirement",
                    "run_preflight_checks": False,
                }
            ),
            attributes=attributes,
        )

        assert attributes[RUN_CONFIG_KEY] == {
            "execution_mode": "Sequential",
            "is_rescore": True,
            "metrics_source": "requirement",
            "run_preflight_checks": False,
        }

    def test_ignores_routing_and_bookkeeping_keys(self):
        """The snapshot is an allowlist, not a copy of the whole attributes bag."""
        attributes = {}
        snapshot_run_config(
            test_config=_config(
                {
                    "execution_mode": "Parallel",
                    "parameters_ref": {"experiment_id": "x"},
                    "batch_id": "b1",
                    "reference_test_run_id": str(uuid.uuid4()),
                }
            ),
            attributes=attributes,
        )

        assert attributes[RUN_CONFIG_KEY] == {"execution_mode": "Parallel"}

    def test_preserves_false_and_empty_values(self):
        """`run_preflight_checks: False` is the whole point; it must not be dropped."""
        attributes = {}
        snapshot_run_config(
            test_config=_config({"run_preflight_checks": False, "metrics": []}),
            attributes=attributes,
        )

        assert attributes[RUN_CONFIG_KEY] == {
            "run_preflight_checks": False,
            "metrics": [],
        }

    @pytest.mark.parametrize("config_attributes", [None, {}, {"unrelated": 1}])
    def test_writes_nothing_when_there_is_nothing_to_record(self, config_attributes):
        """No key means "fall back to the live join", which old runs rely on."""
        attributes = {}
        snapshot_run_config(test_config=_config(config_attributes), attributes=attributes)
        assert attributes == {}

    def test_preserves_existing_run_attributes(self):
        attributes = {"total_tests": 7}
        snapshot_run_config(
            test_config=_config({"execution_mode": "Parallel"}), attributes=attributes
        )
        assert attributes["total_tests"] == 7

    def test_snapshot_is_detached_from_the_configuration(self):
        """Editing the configuration afterwards must not reach through into the run."""
        config_attributes = {"execution_mode": "Parallel"}
        attributes = {}
        snapshot_run_config(test_config=_config(config_attributes), attributes=attributes)

        config_attributes["execution_mode"] = "Sequential"

        assert attributes[RUN_CONFIG_KEY]["execution_mode"] == "Parallel"

    def test_evaluation_model_id_is_snapshotted(self):
        assert "evaluation_model_id" in SNAPSHOT_KEYS


class TestRecordResolvedEvaluationModel:
    def _run(self, attributes=None):
        test_run = Mock()
        test_run.id = uuid.uuid4()
        test_run.organization_id = uuid.uuid4()
        test_run.user_id = uuid.uuid4()
        test_run.attributes = attributes
        return test_run

    def _patch_update(self, monkeypatch):
        captured = {}

        def _fake_update(session, run_id, payload, **kwargs):
            captured["attributes"] = payload.attributes
            return Mock()

        monkeypatch.setattr("rhesis.backend.app.crud.test_run.update_test_run", _fake_update)
        return captured

    def test_writes_the_name_into_the_snapshot(self, monkeypatch):
        captured = self._patch_update(monkeypatch)
        test_run = self._run({RUN_CONFIG_KEY: {"execution_mode": "Parallel"}})

        record_resolved_evaluation_model(Mock(), test_run=test_run, model_name="gpt-4o")

        assert captured["attributes"][RUN_CONFIG_KEY] == {
            "execution_mode": "Parallel",
            "evaluation_model_name": "gpt-4o",
        }

    def test_creates_the_snapshot_when_the_run_has_none(self, monkeypatch):
        captured = self._patch_update(monkeypatch)

        record_resolved_evaluation_model(Mock(), test_run=self._run(), model_name="gpt-4o")

        assert captured["attributes"][RUN_CONFIG_KEY] == {"evaluation_model_name": "gpt-4o"}

    def test_no_name_is_a_no_op(self, monkeypatch):
        captured = self._patch_update(monkeypatch)

        record_resolved_evaluation_model(Mock(), test_run=self._run(), model_name=None)

        assert captured == {}

    def test_skips_the_write_when_the_name_is_unchanged(self, monkeypatch):
        """Both execution paths may reach this; the second one should not write again."""
        captured = self._patch_update(monkeypatch)
        test_run = self._run({RUN_CONFIG_KEY: {"evaluation_model_name": "gpt-4o"}})

        record_resolved_evaluation_model(Mock(), test_run=test_run, model_name="gpt-4o")

        assert captured == {}

    def test_a_failure_does_not_stop_the_run(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise RuntimeError("db down")

        monkeypatch.setattr("rhesis.backend.app.crud.test_run.update_test_run", _boom)

        record_resolved_evaluation_model(Mock(), test_run=self._run(), model_name="gpt-4o")
