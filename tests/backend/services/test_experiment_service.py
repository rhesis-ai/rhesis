"""Unit tests for experiment service helpers.

Covers the shape and behaviour of
:func:`rhesis.backend.app.services.experiment.apply_parameter_snapshot_to_run_attributes`
after it was reshaped to also surface the resolved experiment UUID as a
first-class field (so the caller can stamp the FK column on the new
:class:`~rhesis.backend.app.models.test_run.TestRun.experiment_id`).
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from rhesis.backend.app.services.experiment import (
    ParameterSnapshot,
    apply_parameter_snapshot_to_run_attributes,
    experiment_summary_dict_from_run_attributes,
)


class TestParameterSnapshotNoRef:
    """``apply_parameter_snapshot_to_run_attributes`` when no ``parameters_ref``."""

    def test_no_parameters_ref_returns_passthrough(self):
        """No ref means: leave attributes alone and emit ``experiment_id=None``."""
        test_config = MagicMock()
        test_config.attributes = None

        result = apply_parameter_snapshot_to_run_attributes(
            db=MagicMock(),
            test_config=test_config,
            attributes={"total_tests": 5},
            organization_id="org-1",
            user_id="user-1",
        )

        assert isinstance(result, ParameterSnapshot)
        assert result.attributes == {"total_tests": 5}
        assert result.experiment_id is None

    def test_empty_attributes_dict_returns_passthrough(self):
        """Empty cfg attributes dict is treated the same as missing."""
        test_config = MagicMock()
        test_config.attributes = {}

        result = apply_parameter_snapshot_to_run_attributes(
            db=MagicMock(),
            test_config=test_config,
            attributes={"total_tests": 0},
            organization_id="org-1",
            user_id="user-1",
        )

        assert result.attributes == {"total_tests": 0}
        assert result.experiment_id is None

    def test_non_dict_parameters_ref_returns_passthrough(self):
        """Defensive: a malformed ``parameters_ref`` short-circuits to passthrough."""
        test_config = MagicMock()
        test_config.attributes = {"parameters_ref": "not-a-dict"}

        result = apply_parameter_snapshot_to_run_attributes(
            db=MagicMock(),
            test_config=test_config,
            attributes={"x": 1},
            organization_id="org-1",
            user_id="user-1",
        )

        assert result.experiment_id is None
        assert result.attributes == {"x": 1}


class TestParameterSnapshotWithRef:
    """``apply_parameter_snapshot_to_run_attributes`` when a ref resolves."""

    def test_resolves_experiment_id_and_merges_snapshot(self):
        """A populated ``parameters_ref`` produces ``ParameterSnapshot``
        with the experiment UUID on the FK side and the merged snapshot
        keys in ``attributes``.
        """
        exp_uuid = uuid.uuid4()

        test_config = MagicMock()
        test_config.attributes = {
            "parameters_ref": {
                "experiment_id": str(exp_uuid),
                "version": "v_abc",
            }
        }
        test_config.endpoint_id = uuid.uuid4()

        mock_endpoint = MagicMock()
        mock_endpoint.project_id = uuid.uuid4()

        mock_project = MagicMock()
        mock_resolved = MagicMock()
        mock_resolved.experiment_id = exp_uuid
        mock_resolved.version = "v_abc"
        mock_resolved.source = "version"
        mock_resolved.source_environment = None
        mock_resolved.schema_.model_dump.return_value = {"fields": []}
        mock_resolved.values = {}

        mock_exp_row = MagicMock()
        mock_exp_row.name = "Greenfield"
        mock_exp_row.visibility = "shared"

        db = MagicMock()
        db.get.side_effect = [mock_endpoint, mock_exp_row]

        with (
            patch(
                "rhesis.backend.app.services.experiment.crud.get_project",
                return_value=mock_project,
            ),
            patch(
                "rhesis.backend.app.services.experiment.resolve_parameters",
                return_value=mock_resolved,
            ),
            patch(
                "rhesis.backend.app.services.experiment."
                "unwrap_parameter_values_for_wire",
                return_value={"model": "gpt-4o"},
            ),
        ):
            result = apply_parameter_snapshot_to_run_attributes(
                db=db,
                test_config=test_config,
                attributes={"total_tests": 3},
                organization_id="org-1",
                user_id="user-1",
            )

        assert isinstance(result, ParameterSnapshot)
        # FK side: real UUID, not a stringified copy of attributes.
        assert result.experiment_id == exp_uuid
        # JSONB side: snapshot keys are present.
        assert result.attributes["total_tests"] == 3
        assert result.attributes["parameter_experiment_id"] == str(exp_uuid)
        assert result.attributes["parameter_experiment_name"] == "Greenfield"
        assert result.attributes["parameter_experiment_visibility"] == "shared"
        assert result.attributes["parameter_version"] == "v_abc"
        assert result.attributes["parameters"] == {"model": "gpt-4o"}


class TestExperimentSummaryFromAttributes:
    """The summary helper still reads from the immutable JSONB snapshot."""

    def test_summary_reads_from_attributes(self):
        exp_id = str(uuid.uuid4())
        attrs = {
            "parameter_experiment_id": exp_id,
            "parameter_experiment_name": "Greenfield",
            "parameter_version": "v_abc",
            "parameter_source_environment": "production",
            "parameter_experiment_visibility": "shared",
        }
        summary = experiment_summary_dict_from_run_attributes(attrs)
        assert summary == {
            "id": exp_id,
            "name": "Greenfield",
            "version": "v_abc",
            "source_environment": "production",
            "visibility": "shared",
        }

    def test_summary_is_none_without_experiment_id(self):
        assert (
            experiment_summary_dict_from_run_attributes(
                {"parameter_version": "v"}
            )
            is None
        )

    def test_summary_is_none_for_empty_attributes(self):
        assert experiment_summary_dict_from_run_attributes(None) is None
        assert experiment_summary_dict_from_run_attributes({}) is None
