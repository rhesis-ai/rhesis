"""Tests for GarakTaxonomy service."""

import pytest

from rhesis.backend.app.services.garak.taxonomy import GarakMapping, GarakTaxonomy


@pytest.mark.unit
@pytest.mark.service
class TestGarakMapping:
    """Tests for the GarakMapping dataclass."""

    def test_garak_mapping_creation(self):
        """Test creating a GarakMapping instance."""
        mapping = GarakMapping(
            category="Harmful",
            topic="Jailbreak",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Test mapping",
        )

        assert mapping.category == "Harmful"
        assert mapping.topic == "Jailbreak"
        assert mapping.behavior == "Robustness"
        assert mapping.default_detector == "garak.detectors.mitigation.MitigationBypass"
        assert mapping.description == "Test mapping"


@pytest.mark.unit
@pytest.mark.service
class TestGarakTaxonomyMappings:
    """Tests for module mappings."""

    def test_dan_module_mapping(self):
        """Test DAN module mapping."""
        mapping = GarakTaxonomy.get_mapping("dan")

        assert mapping.category == "Harmful"
        assert mapping.topic == "Jailbreak"
        assert mapping.behavior == "Robustness"
        assert mapping.default_detector == "garak.detectors.mitigation.MitigationBypass"

    def test_encoding_module_mapping(self):
        """Test encoding module mapping."""
        mapping = GarakTaxonomy.get_mapping("encoding")

        assert mapping.category == "Harmful"
        assert mapping.topic == "Encoding Bypass"
        assert mapping.default_detector == "garak.detectors.mitigation.MitigationBypass"

    def test_promptinject_module_mapping(self):
        """Test promptinject module mapping."""
        mapping = GarakTaxonomy.get_mapping("promptinject")

        assert mapping.category == "Harmful"
        assert mapping.topic == "Prompt Injection"
        assert mapping.behavior == "Compliance"

    def test_continuation_module_mapping(self):
        """Test continuation module mapping."""
        mapping = GarakTaxonomy.get_mapping("continuation")

        assert mapping.default_detector == "garak.detectors.continuation.Continuation"

    def test_misleading_module_mapping(self):
        """Test misleading module mapping."""
        mapping = GarakTaxonomy.get_mapping("misleading")

        assert mapping.topic == "Misinformation"
        assert mapping.behavior == "Reliability"

    def test_toxicity_module_mapping(self):
        """Test realtoxicityprompts module mapping."""
        mapping = GarakTaxonomy.get_mapping("realtoxicityprompts")

        assert mapping.topic == "Toxicity"
        assert mapping.default_detector == "garak.detectors.toxicity.ToxicityDetector"

    def test_malwaregen_module_mapping(self):
        """Test malwaregen module mapping."""
        mapping = GarakTaxonomy.get_mapping("malwaregen")

        assert mapping.topic == "Malware Generation"
        assert mapping.default_detector == "garak.detectors.malwaregen.MalwareGenDetector"

    def test_xss_module_mapping(self):
        """Test XSS module mapping."""
        mapping = GarakTaxonomy.get_mapping("xss")

        assert mapping.topic == "XSS"
        assert mapping.default_detector == "garak.detectors.xss.XSSDetector"

    def test_snowball_module_mapping(self):
        """Test snowball module mapping."""
        mapping = GarakTaxonomy.get_mapping("snowball")

        assert mapping.topic == "Factual Errors"
        assert mapping.behavior == "Reliability"
        assert mapping.default_detector == "garak.detectors.snowball.SnowballDetector"

    def test_donotanswer_module_mapping(self):
        """Test donotanswer module mapping."""
        mapping = GarakTaxonomy.get_mapping("donotanswer")

        assert mapping.topic == "Refusal Bypass"
        assert mapping.default_detector == "garak.detectors.donotanswer.DoNotAnswerDetector"

    def test_leakreplay_module_mapping(self):
        """Test leakreplay module mapping."""
        mapping = GarakTaxonomy.get_mapping("leakreplay")

        assert mapping.topic == "Data Leakage"
        assert mapping.default_detector == "garak.detectors.leakreplay.LeakReplayDetector"


@pytest.mark.unit
@pytest.mark.service
class TestGarakTaxonomyDefaultMapping:
    """Tests for default mapping behavior."""

    def test_unknown_module_returns_default(self):
        """Test that unknown modules return the default mapping."""
        mapping = GarakTaxonomy.get_mapping("unknown_module")

        assert mapping.category == "Harmful"
        assert mapping.topic == "Security Testing"
        assert mapping.behavior == "Robustness"
        assert mapping.default_detector == "garak.detectors.mitigation.MitigationBypass"

    def test_default_mapping_attributes(self):
        """Test default mapping has all required attributes."""
        mapping = GarakTaxonomy.DEFAULT_MAPPING

        assert mapping.category is not None
        assert mapping.topic is not None
        assert mapping.behavior is not None
        assert mapping.default_detector is not None
        assert mapping.description is not None


@pytest.mark.unit
@pytest.mark.service
class TestGarakTaxonomyHelpers:
    """Tests for taxonomy helper methods."""

    def test_get_category(self):
        """Test get_category helper."""
        category = GarakTaxonomy.get_category("dan")
        assert category == "Harmful"

    def test_get_topic(self):
        """Test get_topic helper."""
        topic = GarakTaxonomy.get_topic("dan")
        assert topic == "Jailbreak"

    def test_get_behavior(self):
        """Test get_behavior helper."""
        behavior = GarakTaxonomy.get_behavior("dan")
        assert behavior == "Robustness"

    def test_get_default_detector(self):
        """Test get_default_detector helper."""
        detector = GarakTaxonomy.get_default_detector("dan")
        assert detector == "garak.detectors.mitigation.MitigationBypass"

    def test_list_mapped_modules(self):
        """Test list_mapped_modules returns all mapped modules."""
        modules = GarakTaxonomy.list_mapped_modules()

        assert isinstance(modules, list)
        assert len(modules) > 0
        assert "dan" in modules
        assert "encoding" in modules
        assert "xss" in modules
        assert "continuation" in modules

    def test_get_all_mappings(self):
        """Test get_all_mappings returns all mappings."""
        mappings = GarakTaxonomy.get_all_mappings()

        assert isinstance(mappings, dict)
        assert len(mappings) > 0
        assert "dan" in mappings
        assert isinstance(mappings["dan"], GarakMapping)

    def test_get_all_mappings_returns_copy(self):
        """Test that get_all_mappings returns a copy."""
        mappings1 = GarakTaxonomy.get_all_mappings()
        mappings2 = GarakTaxonomy.get_all_mappings()

        assert mappings1 is not mappings2
        assert mappings1 == mappings2


@pytest.mark.unit
@pytest.mark.service
class TestGarakTaxonomyConsistency:
    """Tests for taxonomy consistency."""

    def test_all_mappings_have_full_paths(self):
        """Test that all detector paths are full garak paths."""
        mappings = GarakTaxonomy.get_all_mappings()

        for module_name, mapping in mappings.items():
            assert mapping.default_detector.startswith("garak.detectors."), (
                f"Detector for {module_name} should start with 'garak.detectors.'"
            )

    def test_all_mappings_have_valid_categories(self):
        """Test that all mappings have valid category values."""
        mappings = GarakTaxonomy.get_all_mappings()

        for module_name, mapping in mappings.items():
            assert mapping.category, f"Module {module_name} has empty category"

    def test_all_mappings_have_descriptions(self):
        """Test that all mappings have descriptions."""
        mappings = GarakTaxonomy.get_all_mappings()

        for module_name, mapping in mappings.items():
            assert mapping.description, f"Module {module_name} has empty description"

    def test_known_probe_modules_count(self):
        """Test that we have mappings for expected number of modules."""
        mappings = GarakTaxonomy.get_all_mappings()

        # Should have at least 15 known modules mapped
        assert len(mappings) >= 15
