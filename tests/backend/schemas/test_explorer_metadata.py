"""Tests for the explorer JSONB metadata schemas.

Covers the contract every call site in crud/explorer.py and services/explorer/* relies
on: parse_* is total (never raises, even on garak-shaped or garbage input), dumping via
model_dump(mode="json", exclude_none=True) drops None fields rather than writing them as
null, and the lenient coercion matches the manual .get()/isinstance() checks these models
replace.
"""

import uuid

import pytest

from rhesis.backend.app.schemas.explorer_metadata import (
    TOPIC_MARKER_LABEL,
    ExplorerAdaptiveSettings,
    ExplorerTestMetadata,
    ExplorerTestSetAttributes,
    parse_explorer_adaptive_settings,
    parse_explorer_test_metadata,
    parse_explorer_test_set_attributes,
)


@pytest.mark.unit
class TestParseExplorerTestMetadataIsTotal:
    """parse_explorer_test_metadata never raises, whatever it's handed."""

    @pytest.mark.parametrize("raw", [None, {}])
    def test_none_and_empty_dict_give_defaults(self, raw):
        meta = parse_explorer_test_metadata(raw)

        assert meta == ExplorerTestMetadata()

    def test_garbage_shaped_input_does_not_raise(self):
        meta = parse_explorer_test_metadata(
            {
                "label": 12345,
                "labeler": {"nested": "object"},
                "model_score": ["not", "a", "number"],
                "metrics": "not even a dict",
                "evaluation": "also not a list",
            }
        )

        assert meta.label == ""
        assert meta.model_score == 0.0
        assert meta.metrics is None
        assert meta.evaluation is None

    def test_garak_shaped_row_does_not_raise(self):
        """test_metadata also carries garak sync/import data on the same column."""
        meta = parse_explorer_test_metadata(
            {"source": "garak", "garak_probe_id": "abc123", "garak_notes": "some notes"}
        )

        assert meta.label == ""
        assert meta.output is None

    def test_non_mapping_input_does_not_raise(self):
        assert parse_explorer_test_metadata("not a mapping at all") == ExplorerTestMetadata()


@pytest.mark.unit
class TestExplorerTestMetadataRoundTrip:
    """Foreign/unknown keys and None-vs-absent semantics survive a parse -> dump round trip."""

    def test_foreign_keys_survive_round_trip(self):
        raw = {"label": "pass", "source": "garak", "garak_probe_id": "abc123"}
        meta = parse_explorer_test_metadata(raw)
        dumped = meta.model_dump(mode="json", exclude_none=True)

        assert dumped["source"] == "garak"
        assert dumped["garak_probe_id"] == "abc123"
        assert dumped["label"] == "pass"

    def test_none_fields_dump_to_absent_keys_not_null(self):
        dumped = ExplorerTestMetadata().model_dump(mode="json", exclude_none=True)

        assert "output" not in dumped
        assert "labeler" not in dumped
        assert "metrics" not in dumped
        assert "evaluation" not in dumped
        # non-None defaults still serialize.
        assert dumped["label"] == ""
        assert dumped["model_score"] == 0.0

    def test_present_empty_string_survives_as_empty_not_absent(self):
        meta = parse_explorer_test_metadata({"output": "", "labeler": ""})
        dumped = meta.model_dump(mode="json", exclude_none=True)

        assert dumped["output"] == ""
        assert dumped["labeler"] == ""


@pytest.mark.unit
class TestExplorerTestMetadataLabelCoercion:
    @pytest.mark.parametrize("label", ["", "topic_marker", "pass", "fail", "error"])
    def test_valid_labels_pass_through(self, label):
        assert parse_explorer_test_metadata({"label": label}).label == label

    @pytest.mark.parametrize("raw", ["unknown", 123, None, {}])
    def test_invalid_labels_normalize_to_empty(self, raw):
        assert parse_explorer_test_metadata({"label": raw}).label == ""


@pytest.mark.unit
class TestExplorerTestMetadataModelScoreCoercion:
    @pytest.mark.parametrize("raw", ["not a number", None, {}, []])
    def test_unparseable_scores_default_to_zero(self, raw):
        assert parse_explorer_test_metadata({"model_score": raw}).model_score == 0.0

    def test_numeric_string_coerces(self):
        assert parse_explorer_test_metadata({"model_score": "0.5"}).model_score == 0.5


@pytest.mark.unit
class TestExplorerTestMetadataMetricsCoercion:
    def test_a_malformed_entry_is_dropped_while_siblings_survive(self):
        meta = parse_explorer_test_metadata(
            {
                "metrics": {
                    "Good": {"score": 0.9, "is_successful": True},
                    "Malformed": "not a dict",
                    "MissingRequired": {"reason": "no score or is_successful"},
                }
            }
        )

        assert set(meta.metrics) == {"Good"}
        assert meta.metrics["Good"].score == 0.9
        assert meta.metrics["Good"].is_successful is True

    def test_non_dict_metrics_value_normalizes_to_none(self):
        assert parse_explorer_test_metadata({"metrics": "nope"}).metrics is None

    def test_all_entries_dropped_normalizes_to_none(self):
        meta = parse_explorer_test_metadata({"metrics": {"Bad": "nope"}})

        assert meta.metrics is None


@pytest.mark.unit
class TestExplorerTestMetadataEvaluationCoercion:
    def test_non_dict_entries_are_dropped(self):
        meta = parse_explorer_test_metadata(
            {
                "evaluation": [
                    {"label": "pass", "labeler": "MetricA", "model_score": 1.0},
                    "not a dict",
                    None,
                ]
            }
        )

        assert len(meta.evaluation) == 1
        assert meta.evaluation[0].labeler == "MetricA"

    def test_non_list_normalizes_to_none(self):
        assert parse_explorer_test_metadata({"evaluation": "nope"}).evaluation is None


@pytest.mark.unit
class TestTopicMarker:
    def test_topic_marker_shape(self):
        meta = ExplorerTestMetadata.topic_marker(labeler="user")

        assert meta.label == TOPIC_MARKER_LABEL
        assert meta.labeler == "user"
        assert meta.output == ""
        assert meta.is_topic_marker is True

    def test_default_labeler(self):
        assert ExplorerTestMetadata.topic_marker().labeler == "user"

    def test_is_topic_marker_false_for_other_labels(self):
        assert parse_explorer_test_metadata({"label": "pass"}).is_topic_marker is False


@pytest.mark.unit
class TestExplorerAdaptiveSettings:
    def test_valid_uuid_string_parses(self):
        endpoint_id = uuid.uuid4()
        settings = parse_explorer_adaptive_settings({"default_endpoint_id": str(endpoint_id)})

        assert settings.default_endpoint_id == endpoint_id

    @pytest.mark.parametrize("raw", ["", "not-a-uuid", None, 12345])
    def test_blank_or_unparseable_normalizes_to_none(self, raw):
        assert (
            parse_explorer_adaptive_settings({"default_endpoint_id": raw}).default_endpoint_id
            is None
        )

    def test_none_and_empty_dict_give_defaults(self):
        assert parse_explorer_adaptive_settings(None) == ExplorerAdaptiveSettings()
        assert parse_explorer_adaptive_settings({}) == ExplorerAdaptiveSettings()

    def test_foreign_keys_survive_round_trip(self):
        settings = parse_explorer_adaptive_settings({"kept": "yes", "default_endpoint_id": None})
        dumped = settings.model_dump(mode="json", exclude_none=True)

        assert dumped == {"kept": "yes"}

    def test_garbage_input_does_not_raise(self):
        assert (
            parse_explorer_adaptive_settings("not a mapping at all") == ExplorerAdaptiveSettings()
        )


@pytest.mark.unit
class TestExplorerTestSetAttributes:
    def test_is_explorer_true_when_behavior_present(self):
        attrs = parse_explorer_test_set_attributes(
            {"metadata": {"behaviors": ["Adaptive Testing", "Safety"]}}
        )

        assert attrs.is_explorer is True

    def test_is_explorer_false_without_marker_behavior(self):
        attrs = parse_explorer_test_set_attributes({"metadata": {"behaviors": ["Safety"]}})

        assert attrs.is_explorer is False

    def test_is_explorer_false_when_metadata_absent(self):
        assert parse_explorer_test_set_attributes({}).is_explorer is False
        assert parse_explorer_test_set_attributes(None).is_explorer is False

    def test_default_endpoint_id_reads_through_adaptive_settings(self):
        endpoint_id = uuid.uuid4()
        attrs = parse_explorer_test_set_attributes(
            {"adaptive_settings": {"default_endpoint_id": str(endpoint_id)}}
        )

        assert attrs.default_endpoint_id == endpoint_id

    def test_default_endpoint_id_none_when_adaptive_settings_absent(self):
        assert parse_explorer_test_set_attributes({}).default_endpoint_id is None

    def test_garak_shaped_attributes_do_not_raise(self):
        """attributes also carries garak's own shape on the same column."""
        attrs = parse_explorer_test_set_attributes(
            {"source": "garak", "garak_module": "dan", "garak_probe_class": "Dan_11_0"}
        )

        assert attrs.is_explorer is False
        assert attrs.default_endpoint_id is None

    def test_garbage_input_does_not_raise(self):
        assert parse_explorer_test_set_attributes("nope") == ExplorerTestSetAttributes()
