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
        assert mapping.default_detector == "garak.detectors.perspective.Toxicity"

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

        # 13 original + 2 renames (atkgen, av_spam_scanning) + 15 new = 28 minimum
        assert len(mappings) >= 28


@pytest.mark.unit
@pytest.mark.service
class TestGarakTaxonomyV013Modules:
    """Tests for garak v0.13.3 taxonomy additions and renames."""

    # ---- Renamed modules ----

    def test_atkgen_module_mapping(self):
        """'atkgen' replaces 'art' as of garak v0.13.3."""
        mapping = GarakTaxonomy.get_mapping("atkgen")

        assert mapping.topic == "Automatic Red-Team"
        assert mapping.default_detector == "garak.detectors.perspective.Toxicity"

    def test_av_spam_scanning_module_mapping(self):
        """'av_spam_scanning' replaces 'knownbadsignatures' as of garak v0.13.3."""
        mapping = GarakTaxonomy.get_mapping("av_spam_scanning")

        assert mapping.topic == "Known Bad Patterns"
        assert mapping.default_detector == "garak.detectors.knownbadsignatures.EICAR"

    # ---- Previously untested original modules ----

    def test_lmrc_module_mapping(self):
        """Test lmrc module has explicit mapping."""
        mapping = GarakTaxonomy.get_mapping("lmrc")

        assert mapping is not None
        assert mapping.default_detector.startswith("garak.detectors.")

    def test_packagehallucination_module_mapping(self):
        """Test packagehallucination module has explicit mapping."""
        mapping = GarakTaxonomy.get_mapping("packagehallucination")

        assert mapping is not None
        assert mapping.default_detector.startswith("garak.detectors.")

    def test_misleading_claim_detector_is_correct(self):
        """Test misleading module points to MisleadingClaim detector."""
        mapping = GarakTaxonomy.get_mapping("misleading")

        assert mapping.default_detector == "garak.detectors.misleading.MisleadingClaim"

    # ---- New modules in v0.13.3 ----

    def test_ansiescape_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("ansiescape")

        assert mapping.topic == "ANSI Escape Injection"
        assert mapping.default_detector == "garak.detectors.ansiescape.ANSI"

    def test_apikey_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("apikey")

        assert mapping.topic == "API Key Leakage"
        assert mapping.default_detector == "garak.detectors.apikey.APIKey"

    def test_audio_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("audio")

        assert mapping.topic == "Audio Attack"

    def test_badchars_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("badchars")

        assert mapping.topic == "Bad Characters"

    def test_divergence_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("divergence")

        assert mapping.topic == "Training Data Leakage"
        assert mapping.default_detector == "garak.detectors.divergence.Repetitive"

    def test_doctor_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("doctor")

        assert mapping.topic == "Medical Advice"

    def test_dra_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("dra")

        assert mapping.topic == "Decomposed Roleplay Attack"

    def test_exploitation_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("exploitation")

        assert mapping.topic == "Code Exploitation"
        assert mapping.default_detector == "garak.detectors.exploitation.ExploitDetector"

    def test_fileformats_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("fileformats")

        assert mapping.topic == "Malicious File Formats"
        assert mapping.default_detector == "garak.detectors.fileformats.FileFormatDetector"

    def test_fitd_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("fitd")

        assert mapping.topic == "Foot In The Door"

    def test_grandma_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("grandma")

        assert mapping.topic == "Social Engineering"

    def test_latentinjection_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("latentinjection")

        assert mapping.topic == "Latent Prompt Injection"

    def test_phrasing_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("phrasing")

        assert mapping.topic == "Phrasing Attack"

    def test_sata_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("sata")

        assert mapping.topic == "Suffix Attack"

    def test_smuggling_module_mapping(self):
        mapping = GarakTaxonomy.get_mapping("smuggling")

        assert mapping.topic == "ASCII Smuggling"

    # ---- Regression: old module names must not exist ----

    def test_art_key_does_not_exist(self):
        """'art' was renamed to 'atkgen' in v0.13.3 — the old key must be gone."""
        mappings = GarakTaxonomy.get_all_mappings()
        assert "art" not in mappings, (
            "Found stale 'art' key in taxonomy — it was renamed to 'atkgen' in garak v0.13.3."
        )

    def test_knownbadsignatures_key_does_not_exist(self):
        """'knownbadsignatures' was renamed to 'av_spam_scanning' in v0.13.3."""
        mappings = GarakTaxonomy.get_all_mappings()
        assert "knownbadsignatures" not in mappings, (
            "Found stale 'knownbadsignatures' key — "
            "it was renamed to 'av_spam_scanning' in garak v0.13.3."
        )
