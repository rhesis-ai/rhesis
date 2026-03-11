"""
Tests for GarakDynamicGenerator service.

These are pure-unit tests — no garak, no database, no Celery required.
All garak I/O is replaced by in-process GarakProbeInfo objects constructed
directly from test data.
"""

from unittest.mock import MagicMock

import pytest

from rhesis.backend.app.services.garak.dynamic import GarakDynamicGenerator
from rhesis.backend.app.services.garak.probes.models import GarakProbeInfo
from rhesis.backend.app.services.garak.tag_catalog import GarakTagCatalog

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_probe(
    module_name="fitd",
    class_name="FITD",
    description="Transform queries from benign to harmful",
    tags=None,
    prompt_count=0,
) -> GarakProbeInfo:
    return GarakProbeInfo(
        module_name=module_name,
        class_name=class_name,
        full_name=f"{module_name}.{class_name}",
        description=description,
        tags=tags or ["owasp:llm01", "owasp:llm02", "owasp:llm05"],
        prompts=[],
        prompt_count=prompt_count,
        detector=None,
        is_dynamic=prompt_count == 0,
    )


def _mock_catalog(**overrides) -> GarakTagCatalog:
    """Build a mock catalog with configurable get_description / get_topic."""
    catalog = MagicMock(spec=GarakTagCatalog)

    desc_map = {
        "owasp:llm01": "LLM01: Prompt Injection — adversarial prompt manipulation",
        "owasp:llm05": "LLM05: Supply Chain — third-party risks",
        "owasp:llm02": "LLM02: Insecure Output — output validation",
    }
    topic_map = {
        "quality:Behavioral:ContentSafety:Toxicity": "Toxicity",
        "payload:jailbreak": "Jailbreak",
    }

    desc_map.update(overrides.get("descriptions", {}))
    topic_map.update(overrides.get("topics", {}))

    catalog.get_description.side_effect = lambda tag: desc_map.get(tag)
    catalog.get_topic.side_effect = lambda tag: topic_map.get(tag)
    return catalog


# ---------------------------------------------------------------------------
# GarakDynamicGenerator.build_generation_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildGenerationConfig:
    def test_returns_generation_config(self):
        from rhesis.backend.app.schemas.services import GenerationConfig

        generator = GarakDynamicGenerator(catalog=_mock_catalog())
        probe = make_probe()
        config = generator.build_generation_config(probe)

        assert isinstance(config, GenerationConfig)

    def test_generation_prompt_contains_goal(self):
        generator = GarakDynamicGenerator(catalog=_mock_catalog())
        probe = make_probe(description="Make the model say something toxic")
        config = generator.build_generation_config(probe)

        assert probe.description in config.generation_prompt

    def test_generation_prompt_includes_tag_descriptions(self):
        generator = GarakDynamicGenerator(catalog=_mock_catalog())
        probe = make_probe(tags=["owasp:llm01", "owasp:llm05"])
        config = generator.build_generation_config(probe)

        assert "LLM01" in config.generation_prompt
        assert "LLM05" in config.generation_prompt

    def test_generation_prompt_has_adversarial_instruction(self):
        generator = GarakDynamicGenerator(catalog=_mock_catalog())
        config = generator.build_generation_config(make_probe())

        assert "adversarial" in config.generation_prompt.lower()

    def test_unknown_tags_do_not_appear_in_prompt(self):
        generator = GarakDynamicGenerator(catalog=_mock_catalog())
        probe = make_probe(tags=["unknown:tag:xyz"])
        config = generator.build_generation_config(probe)

        assert "unknown:tag:xyz" not in config.generation_prompt

    def test_behaviors_and_categories_populated_from_taxonomy(self):
        generator = GarakDynamicGenerator(catalog=_mock_catalog())
        config = generator.build_generation_config(make_probe(module_name="fitd"))

        assert config.behaviors is None or all(isinstance(b, str) for b in config.behaviors)
        assert config.categories is None or all(isinstance(c, str) for c in config.categories)

    def test_quality_tags_produce_topics(self):
        generator = GarakDynamicGenerator(catalog=_mock_catalog())
        probe = make_probe(tags=["quality:Behavioral:ContentSafety:Toxicity"])
        config = generator.build_generation_config(probe)

        assert config.topics is not None
        assert "Toxicity" in config.topics

    def test_no_tags_produces_valid_config(self):
        generator = GarakDynamicGenerator(catalog=_mock_catalog())
        probe = make_probe(tags=[])
        config = generator.build_generation_config(probe)

        assert config.generation_prompt
        assert config.topics is None or config.topics == []

    def test_catalog_get_description_called_for_each_tag(self):
        catalog = _mock_catalog()
        generator = GarakDynamicGenerator(catalog=catalog)
        tags = ["owasp:llm01", "owasp:llm05"]
        generator.build_generation_config(make_probe(tags=tags))

        for tag in tags:
            catalog.get_description.assert_any_call(tag)

    def test_catalog_get_topic_called_for_each_tag(self):
        catalog = _mock_catalog()
        generator = GarakDynamicGenerator(catalog=catalog)
        tags = ["quality:Behavioral:ContentSafety:Toxicity", "payload:jailbreak"]
        generator.build_generation_config(make_probe(tags=tags))

        for tag in tags:
            catalog.get_topic.assert_any_call(tag)


# ---------------------------------------------------------------------------
# GarakDynamicGenerator.build_probe_metadata
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildProbeMetadata:
    def test_metadata_contains_required_keys(self):
        generator = GarakDynamicGenerator(catalog=_mock_catalog())
        probe = make_probe()
        metadata = generator.build_probe_metadata(probe)

        required_keys = [
            "source",
            "garak_module",
            "garak_probe_class",
            "garak_probe_full_name",
            "garak_goal",
            "garak_tags",
            "garak_is_dynamic",
        ]
        for key in required_keys:
            assert key in metadata, f"Missing key: {key}"

    def test_source_is_garak_dynamic(self):
        gen = GarakDynamicGenerator(catalog=_mock_catalog())
        metadata = gen.build_probe_metadata(make_probe())
        assert metadata["source"] == "garak_dynamic"

    def test_garak_tags_are_preserved(self):
        tags = ["owasp:llm01", "owasp:llm02", "owasp:llm05"]
        probe = make_probe(tags=tags)
        gen = GarakDynamicGenerator(catalog=_mock_catalog())
        metadata = gen.build_probe_metadata(probe)

        assert metadata["garak_tags"] == tags

    def test_is_dynamic_flag_is_true(self):
        gen = GarakDynamicGenerator(catalog=_mock_catalog())
        metadata = gen.build_probe_metadata(make_probe(prompt_count=0))
        assert metadata["garak_is_dynamic"] is True

    def test_full_name_matches_probe(self):
        probe = make_probe(module_name="atkgen", class_name="Tox")
        gen = GarakDynamicGenerator(catalog=_mock_catalog())
        metadata = gen.build_probe_metadata(probe)
        assert metadata["garak_probe_full_name"] == "atkgen.Tox"

    def test_metadata_for_fitd_probe(self):
        probe = make_probe(
            module_name="fitd",
            class_name="FITD",
            description="Transform queries from benign to harmful",
            tags=["owasp:llm01", "owasp:llm02", "owasp:llm05"],
        )
        gen = GarakDynamicGenerator(catalog=_mock_catalog())
        metadata = gen.build_probe_metadata(probe)

        assert "owasp:llm01" in metadata["garak_tags"]
        assert "owasp:llm02" in metadata["garak_tags"]
        assert "owasp:llm05" in metadata["garak_tags"]
        assert metadata["garak_module"] == "fitd"


# ---------------------------------------------------------------------------
# GarakDynamicGenerator.build (combined)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuild:
    def test_build_returns_tuple(self):
        from rhesis.backend.app.schemas.services import GenerationConfig

        generator = GarakDynamicGenerator(catalog=_mock_catalog())
        config, metadata = generator.build(make_probe())

        assert isinstance(config, GenerationConfig)
        assert isinstance(metadata, dict)

    def test_build_consistent_with_individual_methods(self):
        generator = GarakDynamicGenerator(catalog=_mock_catalog())
        probe = make_probe(tags=["owasp:llm01"])

        config_a = generator.build_generation_config(probe)
        meta_a = generator.build_probe_metadata(probe)
        config_b, meta_b = generator.build(probe)

        assert config_a.generation_prompt == config_b.generation_prompt
        assert meta_a == meta_b


# ---------------------------------------------------------------------------
# GarakDynamicGenerator static helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStaticHelpers:
    def test_is_dynamic_true_when_zero_prompts(self):
        probe = make_probe(prompt_count=0)
        assert GarakDynamicGenerator.is_dynamic(probe) is True

    def test_is_dynamic_false_when_has_prompts(self):
        probe = make_probe(prompt_count=5)
        assert GarakDynamicGenerator.is_dynamic(probe) is False

    def test_describe_probe_returns_string(self):
        result = GarakDynamicGenerator.describe_probe(make_probe())
        assert isinstance(result, str) and result


# ---------------------------------------------------------------------------
# Probe model is_dynamic flag
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProbeModelIsDynamic:
    """Ensure the is_dynamic field behaves correctly on the dataclass."""

    def test_default_is_false(self):
        probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN probe",
        )
        assert probe.is_dynamic is False

    def test_can_be_set_to_true(self):
        probe = GarakProbeInfo(
            module_name="fitd",
            class_name="FITD",
            full_name="fitd.FITD",
            description="FITD probe",
            is_dynamic=True,
        )
        assert probe.is_dynamic is True
