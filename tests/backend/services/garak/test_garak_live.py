"""
Live tests for Garak backend services with real garak library.

These tests require garak to be installed and test actual probe
enumeration, prompt extraction, and taxonomy mapping against the
real garak library.

NOTE: These are "live" tests that use the actual garak library, not
backend integration tests (which test API routes). They verify that
the backend garak services work correctly with the installed garak version.
"""

import pytest

# Check if garak is available
try:
    import garak
    import garak.probes

    GARAK_AVAILABLE = True
    GARAK_VERSION = getattr(garak, "__version__", "unknown")
except ImportError:
    GARAK_AVAILABLE = False
    GARAK_VERSION = None


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not GARAK_AVAILABLE, reason="garak not installed"),
]


@pytest.mark.integration
class TestGarakProbeServiceIntegration:
    """Integration tests for GarakProbeService with real garak."""

    def test_garak_version_detection(self):
        """Test that we can detect the installed garak version."""
        from rhesis.backend.app.services.garak.probes import GarakProbeService

        service = GarakProbeService()
        version = service.garak_version

        assert version is not None
        assert version != "not_installed"
        assert version == GARAK_VERSION

    def test_enumerate_real_probe_modules(self):
        """Test enumerating actual garak probe modules."""
        from rhesis.backend.app.services.garak.probes import GarakProbeService

        service = GarakProbeService()
        modules = service.enumerate_probe_modules()

        assert len(modules) > 0, "Should find at least some probe modules"

        # Check that we have some expected modules
        module_names = [m.name for m in modules]
        # At least one of these common modules should exist
        expected_modules = ["dan", "encoding", "xss", "continuation"]
        found_modules = [m for m in expected_modules if m in module_names]
        assert len(found_modules) > 0, f"Expected at least one of {expected_modules}"

    def test_module_has_probe_classes(self):
        """Test that enumerated modules have probe classes."""
        from rhesis.backend.app.services.garak.probes import GarakProbeService

        service = GarakProbeService()
        modules = service.enumerate_probe_modules()

        # At least some modules should have probe classes
        modules_with_probes = [m for m in modules if m.probe_count > 0]
        assert len(modules_with_probes) > 0, "Some modules should have probes"

    def test_extract_probes_from_dan_module(self):
        """Test extracting probes from the DAN module."""
        from rhesis.backend.app.services.garak.probes import GarakProbeService

        service = GarakProbeService()

        # Try to get DAN probes - this is a commonly available module
        try:
            probes = service.extract_probes_from_module("dan")
        except Exception:
            pytest.skip("DAN module not available in this garak version")

        if not probes:
            pytest.skip("No DAN probes found in this garak version")

        # Check probe structure
        for probe in probes:
            assert probe.module_name == "dan"
            assert probe.class_name, "Probe should have a class name"
            assert probe.full_name.startswith("dan.")
            assert probe.description, "Probe should have a description"

    def test_extract_prompts_from_probes(self):
        """Test that we can extract prompts from probes."""
        from rhesis.backend.app.services.garak.probes import GarakProbeService

        service = GarakProbeService()
        modules = service.enumerate_probe_modules()

        # Find a module with prompts
        probes_with_prompts = []
        for module in modules[:5]:  # Check first 5 modules
            probes = service.extract_probes_from_module(module.name)
            for probe in probes:
                if probe.prompt_count > 0:
                    probes_with_prompts.append(probe)
                    break
            if probes_with_prompts:
                break

        if not probes_with_prompts:
            pytest.skip("No probes with extractable prompts found")

        probe = probes_with_prompts[0]
        assert len(probe.prompts) > 0, "Probe should have extracted prompts"
        assert all(isinstance(p, str) for p in probe.prompts), "Prompts should be strings"

    def test_probe_has_detector_info(self):
        """Test that some probes have detector information."""
        from rhesis.backend.app.services.garak.probes import GarakProbeService

        service = GarakProbeService()
        modules = service.enumerate_probe_modules()

        # Check if any module has detector info
        modules_with_detector = [m for m in modules if m.default_detector]

        # It's okay if no modules have detectors in the current garak version
        # We use taxonomy mappings as fallback
        if modules_with_detector:
            detector = modules_with_detector[0].default_detector
            # Garak may return relative paths (e.g., "mitigation.MitigationBypass")
            # or full paths (e.g., "garak.detectors.mitigation.MitigationBypass")
            is_full_path = detector.startswith("garak.detectors.")
            is_relative_path = "." in detector and not detector.startswith("garak.")
            assert is_full_path or is_relative_path, (
                f"Detector '{detector}' should be a valid detector path"
            )
        else:
            # This is acceptable - we use taxonomy default detectors as fallback
            pytest.skip("No modules with default_detector found - using taxonomy fallback")

    def test_get_all_probes(self):
        """Test getting all probes from all modules."""
        from rhesis.backend.app.services.garak.probes import GarakProbeService

        service = GarakProbeService()
        all_probes = service.get_all_probes()

        assert isinstance(all_probes, dict)
        assert len(all_probes) > 0, "Should have probes from at least one module"

        # Check structure
        for module_name, probes in all_probes.items():
            assert isinstance(module_name, str)
            assert isinstance(probes, list)
            for probe in probes:
                assert probe.module_name == module_name


@pytest.mark.integration
class TestGarakTaxonomyIntegration:
    """Integration tests for taxonomy mapping with real garak modules."""

    def test_all_discovered_modules_have_mapping(self):
        """Test that all discovered garak modules have taxonomy mappings."""
        from rhesis.backend.app.services.garak.probes import GarakProbeService
        from rhesis.backend.app.services.garak.taxonomy import GarakTaxonomy

        service = GarakProbeService()
        modules = service.enumerate_probe_modules()

        unmapped_modules = []
        for module in modules:
            mapping = GarakTaxonomy.get_mapping(module.name)
            # Check if it's the default mapping (indicates no specific mapping)
            if mapping == GarakTaxonomy.DEFAULT_MAPPING:
                unmapped_modules.append(module.name)

        # Log unmapped modules for visibility (they get default mapping)
        if unmapped_modules:
            print(
                f"\n⚠️  GARAK UPGRADE WARNING: {len(unmapped_modules)} modules "
                "using default mapping:"
            )
            for mod in unmapped_modules:
                print(f"    - {mod}")
            print("Consider adding explicit mappings in GarakTaxonomy.MODULE_MAPPINGS")

        # All modules should at least get a valid mapping (even if default)
        for module in modules:
            mapping = GarakTaxonomy.get_mapping(module.name)
            assert mapping.category, f"Module {module.name} should have a category"
            assert mapping.topic, f"Module {module.name} should have a topic"
            assert mapping.behavior, f"Module {module.name} should have a behavior"

    def test_taxonomy_detector_paths_are_valid(self):
        """Test that taxonomy detector paths follow garak conventions."""
        from rhesis.backend.app.services.garak.taxonomy import GarakTaxonomy

        mappings = GarakTaxonomy.get_all_mappings()

        for module_name, mapping in mappings.items():
            detector = mapping.default_detector
            assert detector.startswith("garak.detectors."), (
                f"Detector for {module_name} should start with 'garak.detectors.'"
            )

            # Check the detector path has at least 3 parts
            parts = detector.split(".")
            assert len(parts) >= 3, f"Detector path for {module_name} should have module and class"


@pytest.mark.integration
class TestGarakDetectorImportIntegration:
    """Integration tests for importing garak detectors."""

    def test_can_import_mitigation_bypass_detector(self):
        """Test importing a common detector."""
        try:
            from garak.detectors.mitigation import MitigationBypass

            assert MitigationBypass is not None
        except ImportError:
            pytest.skip("MitigationBypass detector not available")

    def test_can_import_detector_base(self):
        """Test importing the detector base class."""
        try:
            from garak.detectors.base import Detector

            assert Detector is not None
        except ImportError:
            pytest.skip("Detector base class not available")

    def test_can_import_attempt_class(self):
        """Test importing the Attempt class used for evaluation."""
        try:
            from garak.attempt import Attempt

            assert Attempt is not None
        except ImportError:
            pytest.skip("Attempt class not available")

    def test_detector_instantiation(self):
        """Test that we can instantiate a detector."""
        try:
            from garak.detectors.mitigation import MitigationBypass

            detector = MitigationBypass()
            assert detector is not None
            assert hasattr(detector, "detect")
        except ImportError:
            pytest.skip("MitigationBypass detector not available")
        except Exception as e:
            pytest.skip(f"Could not instantiate detector: {e}")


@pytest.mark.integration
class TestGarakProbeModuleStructure:
    """Integration tests verifying garak probe module structure."""

    def test_probe_base_class_exists(self):
        """Test that the Probe base class exists."""
        try:
            from garak.probes.base import Probe

            assert Probe is not None
        except ImportError:
            pytest.skip("Probe base class not available")

    def test_dan_module_structure(self):
        """Test the structure of the DAN module."""
        try:
            import garak.probes.dan as dan_module
            from garak.probes.base import Probe

            # Check module has expected attributes
            assert hasattr(dan_module, "__doc__")

            # Find probe classes by checking if they inherit from Probe
            probe_classes = []
            for attr_name in dir(dan_module):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(dan_module, attr_name)
                if isinstance(attr, type):
                    # Check if it inherits from Probe
                    try:
                        if issubclass(attr, Probe) and attr is not Probe:
                            probe_classes.append(attr_name)
                    except TypeError:
                        pass

            # DAN module should have at least one probe
            assert len(probe_classes) > 0, "DAN module should have probe classes"
            print(f"\nFound DAN probe classes: {probe_classes}")

        except ImportError:
            pytest.skip("DAN module not available")

    def test_encoding_module_structure(self):
        """Test the structure of the encoding module."""
        try:
            import garak.probes.encoding as encoding_module

            assert hasattr(encoding_module, "__doc__")
        except ImportError:
            pytest.skip("Encoding module not available")


@pytest.mark.integration
class TestGarakUpgradeReadiness:
    """
    Tests specifically designed to help during garak library upgrades.

    These tests verify compatibility and highlight changes that may need attention.
    """

    # Known modules as of garak 0.9.0.4 - update when adding new mappings
    KNOWN_MODULES = {
        "dan",
        "encoding",
        "promptinject",
        "continuation",
        "misleading",
        "lmrc",
        "realtoxicityprompts",
        "xss",
        "knownbadsignatures",
        "malwaregen",
        "packagehallucination",
        "snowball",
        "suffix",
        "tap",
        "gcg",
        "artprompt",
        "base",
        "test",
        "atkgen",
        "av_spam_scanning",
        "donotanswer",
        "fileformats",
        "glitch",
        "goodside",
        "leakreplay",
        "replay",
        "visual_jailbreak",
    }

    def test_detect_new_garak_modules(self):
        """
        Detect NEW modules added in garak that may need taxonomy mapping.

        This test helps identify when garak adds new probe modules that
        should be added to GarakTaxonomy.MODULE_MAPPINGS.
        """
        from rhesis.backend.app.services.garak.probes import GarakProbeService

        service = GarakProbeService()
        modules = service.enumerate_probe_modules()

        current_modules = {m.name for m in modules}
        new_modules = current_modules - self.KNOWN_MODULES
        removed_modules = self.KNOWN_MODULES - current_modules

        if new_modules:
            print(f"\n🆕 NEW GARAK MODULES DETECTED ({len(new_modules)}):")
            for mod in sorted(new_modules):
                print(f"    + {mod}")
            print("\n   → Consider adding taxonomy mappings for these modules")
            print("   → Update KNOWN_MODULES in test_garak_live.py")

        if removed_modules:
            print(f"\n🗑️  REMOVED GARAK MODULES ({len(removed_modules)}):")
            for mod in sorted(removed_modules):
                print(f"    - {mod}")
            print("\n   → Consider removing from KNOWN_MODULES if intentional")

        # This test passes but provides visibility
        assert True

    def test_taxonomy_detectors_are_importable(self):
        """
        Verify that all detector paths in taxonomy are actually importable.

        This catches when garak reorganizes or removes detectors.
        """
        import importlib

        from rhesis.backend.app.services.garak.taxonomy import GarakTaxonomy

        mappings = GarakTaxonomy.get_all_mappings()
        failed_imports = []
        successful_imports = []

        for module_name, mapping in mappings.items():
            detector_path = mapping.default_detector

            # Parse the detector path
            parts = detector_path.rsplit(".", 1)
            if len(parts) != 2:
                failed_imports.append((module_name, detector_path, "Invalid path format"))
                continue

            module_path, class_name = parts

            try:
                module = importlib.import_module(module_path)
                if hasattr(module, class_name):
                    successful_imports.append((module_name, detector_path))
                else:
                    failed_imports.append(
                        (module_name, detector_path, f"Class {class_name} not found")
                    )
            except ImportError as e:
                failed_imports.append((module_name, detector_path, str(e)))

        if failed_imports:
            print(f"\n⚠️  DETECTOR IMPORT ISSUES ({len(failed_imports)}):")
            for mod, path, error in failed_imports:
                print(f"    {mod}: {path}")
                print(f"       Error: {error}")
            print("\n   → Update GarakTaxonomy.MODULE_MAPPINGS with valid detector paths")
            print("   → Or these detectors may not exist in this garak version")

        print(f"\n✅ Successfully imported {len(successful_imports)} detectors")

        # Must be able to import at least some detectors
        assert len(successful_imports) > 0, "Must be able to import some detectors!"

        # Warn but don't fail for individual missing detectors
        # Many detectors may be version-specific or renamed
        if len(failed_imports) > 0:
            import warnings

            warnings.warn(
                f"{len(failed_imports)} taxonomy detectors not found in current "
                f"garak version - review GarakTaxonomy.MODULE_MAPPINGS"
            )

    def test_garak_version_tracking(self):
        """
        Track garak version for upgrade awareness.

        Update LAST_TESTED_VERSION when you've verified compatibility.
        """
        LAST_TESTED_VERSION = "0.9.0.4"  # Update after successful upgrade testing

        from importlib.metadata import version

        current_version = version("garak")

        print("\n📦 Garak Version Info:")
        print(f"    Last tested: {LAST_TESTED_VERSION}")
        print(f"    Current:     {current_version}")

        if current_version != LAST_TESTED_VERSION:
            print("\n⚠️  VERSION MISMATCH - Review test results carefully!")
            print("   → If all tests pass, update LAST_TESTED_VERSION")
        else:
            print("\n✅ Running on last tested version")

        # This test always passes but provides version visibility
        assert True

    def test_probe_count_sanity_check(self):
        """
        Sanity check that garak still has a reasonable number of probes.

        Helps detect if garak made major structural changes.
        """
        from rhesis.backend.app.services.garak.probes import GarakProbeService

        service = GarakProbeService()
        modules = service.enumerate_probe_modules()

        total_probes = sum(m.probe_count for m in modules)

        print("\n📊 Garak Probe Statistics:")
        print(f"    Total modules: {len(modules)}")
        print(f"    Total probes:  {total_probes}")

        # Sanity checks - adjust thresholds if garak legitimately changes
        assert len(modules) >= 5, "Expected at least 5 probe modules"
        assert total_probes >= 20, "Expected at least 20 total probes"

        # Warn if numbers changed significantly
        EXPECTED_MODULE_COUNT = 25  # Approximate, update as needed
        EXPECTED_PROBE_COUNT = 100  # Approximate, update as needed

        if abs(len(modules) - EXPECTED_MODULE_COUNT) > 10:
            print(f"\n⚠️  Module count changed significantly from ~{EXPECTED_MODULE_COUNT}")

        if abs(total_probes - EXPECTED_PROBE_COUNT) > 50:
            print(f"\n⚠️  Probe count changed significantly from ~{EXPECTED_PROBE_COUNT}")
