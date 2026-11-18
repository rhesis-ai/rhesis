"""Tests for the shared Garak test-data builder."""

import pytest

from rhesis.backend.app.services.garak.builder import build_tests_data
from rhesis.backend.app.services.garak.probes import GarakProbeInfo
from rhesis.backend.app.services.garak.taxonomy import FALLBACK_REQUIREMENT, GarakMapping

MAPPING = GarakMapping(
    category="Harmful",
    topic="Jailbreak",
    default_detector="garak.detectors.mitigation.MitigationBypass",
    description="DAN mapping",
)


def _probe(prompts, prompt_notes=None, tags=None) -> GarakProbeInfo:
    return GarakProbeInfo(
        module_name="dan",
        class_name="Dan_11_0",
        full_name="dan.Dan_11_0",
        description="DAN probe",
        prompts=prompts,
        prompt_count=len(prompts),
        tags=tags or [],
        prompt_notes=prompt_notes,
    )


@pytest.mark.unit
class TestBuildTestsData:
    def test_builds_test_structure(self):
        tests_data = build_tests_data(_probe(["Prompt 1", "Prompt 2"], tags=["jailbreak"]), MAPPING)

        assert len(tests_data) == 2
        assert tests_data[0].prompt.content == "Prompt 1"
        # "jailbreak" has no quality:* tag, so resolve_requirement falls back
        assert tests_data[0].requirement == FALLBACK_REQUIREMENT
        assert tests_data[0].category == "Harmful"
        assert tests_data[0].topic == "Jailbreak"
        assert tests_data[0].test_type == "Single-Turn"
        assert tests_data[0].metadata["source"] == "garak"
        assert tests_data[0].metadata["garak_probe_id"] == "dan.Dan_11_0.0"
        assert tests_data[0].metadata["garak_probe_class"] == "Dan_11_0"
        assert "garak_notes" not in tests_data[0].metadata

    def test_skips_empty_prompts(self):
        tests_data = build_tests_data(_probe(["Valid prompt", "", "  ", "Another valid"]), MAPPING)

        assert [t.metadata["garak_probe_id"] for t in tests_data] == [
            "dan.Dan_11_0.0",
            "dan.Dan_11_0.3",
        ]

    def test_attaches_notes_by_index(self):
        probe = _probe(
            ["a", "b", "c"],
            prompt_notes=[{"triggers": ["x"]}, None, {"triggers": ["z"]}],
        )

        tests_data = build_tests_data(probe, MAPPING)

        assert [t.metadata.get("garak_notes") for t in tests_data] == [
            {"triggers": ["x"]},
            None,
            {"triggers": ["z"]},
        ]

    def test_probe_ids_keeps_only_listed_prompts(self):
        probe = _probe(["a", "b", "c"], prompt_notes=[{"triggers": [p]} for p in "abc"])

        tests_data = build_tests_data(probe, MAPPING, probe_ids={"dan.Dan_11_0.2"})

        assert len(tests_data) == 1
        assert tests_data[0].prompt.content == "c"
        assert tests_data[0].metadata["garak_notes"] == {"triggers": ["c"]}
