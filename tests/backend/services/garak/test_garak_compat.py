"""
Tests for the garak compatibility layer (compat.py).

These tests serve two purposes:
1. Verify compat.py works correctly with the installed garak version.
2. Act as early-warning guardrails for future garak upgrades.

When upgrading garak, run these tests first. Any failure here tells you exactly
which compatibility helper needs updating before touching the rest of the codebase.
"""

import inspect

import pytest

# ---------------------------------------------------------------------------
# Version sanity
# ---------------------------------------------------------------------------


class TestGarakVersion:
    def test_garak_is_importable(self):
        """garak must be importable — basic install sanity check."""
        import garak  # noqa: F401

    def test_garak_version_is_at_least_0_13(self):
        """Ensure we're running garak >= 0.13.0 as required by this integration."""
        import garak

        version_str = garak.__version__
        parts = version_str.split(".")
        major, minor = int(parts[0]), int(parts[1])
        assert (major, minor) >= (0, 13), (
            f"garak {version_str} is older than the required 0.13.0. "
            f"Update garak or lower the version bound in pyproject.toml."
        )

    def test_garak_version_string_is_available(self):
        """garak.__version__ must be a non-empty string."""
        import garak

        assert isinstance(garak.__version__, str)
        assert len(garak.__version__) > 0


# ---------------------------------------------------------------------------
# API attribute stability — these are the attributes compat.py depends on
# ---------------------------------------------------------------------------


class TestGarakProbeBaseClass:
    """Verify the probe base class is importable and has the expected interface."""

    def test_probe_base_class_importable(self):
        from rhesis.backend.app.services.garak.compat import get_probe_base_class

        Probe = get_probe_base_class()
        assert Probe is not None

    def test_probe_base_class_is_a_class(self):
        from rhesis.backend.app.services.garak.compat import get_probe_base_class

        Probe = get_probe_base_class()
        assert inspect.isclass(Probe)

    def test_probe_base_class_has_expected_attributes(self):
        """If garak renames or restructures Probe, this test fails early."""
        from rhesis.backend.app.services.garak.compat import get_probe_base_class

        Probe = get_probe_base_class()
        # primary_detector and tags are stable public class attributes since v0.13.x
        assert hasattr(Probe, "primary_detector") or hasattr(Probe, "tags"), (
            "garak.probes.base.Probe no longer has 'primary_detector' or 'tags' — "
            "the base class API has changed. Check compat.py."
        )


class TestGetProbeDetector:
    """Verify get_probe_detector handles both old and new API gracefully."""

    def test_returns_primary_detector_when_present(self):
        from rhesis.backend.app.services.garak.compat import get_probe_detector

        class FakeProbe:
            primary_detector = "garak.detectors.some.Detector"
            recommended_detector = ["garak.detectors.old.Detector"]

        result = get_probe_detector(FakeProbe)
        assert result == "garak.detectors.some.Detector"

    def test_falls_back_to_recommended_detector_list(self):
        from rhesis.backend.app.services.garak.compat import get_probe_detector

        class FakeProbe:
            primary_detector = None
            recommended_detector = ["garak.detectors.old.Detector"]

        result = get_probe_detector(FakeProbe)
        assert result == "garak.detectors.old.Detector"

    def test_falls_back_to_recommended_detector_string(self):
        from rhesis.backend.app.services.garak.compat import get_probe_detector

        class FakeProbe:
            primary_detector = None
            recommended_detector = "garak.detectors.old.Detector"

        result = get_probe_detector(FakeProbe)
        assert result == "garak.detectors.old.Detector"

    def test_returns_none_when_always_fail(self):
        from rhesis.backend.app.services.garak.compat import get_probe_detector

        class FakeProbe:
            primary_detector = None
            recommended_detector = "always.Fail"

        result = get_probe_detector(FakeProbe)
        assert result is None

    def test_returns_none_when_no_detector(self):
        from rhesis.backend.app.services.garak.compat import get_probe_detector

        class FakeProbe:
            pass

        result = get_probe_detector(FakeProbe)
        assert result is None

    def test_real_probe_class_returns_a_detector(self):
        """A real garak probe class should have a primary_detector or recommended_detector."""
        from rhesis.backend.app.services.garak.compat import get_probe_detector

        try:
            from garak.probes.dan import Dan_11_0 as RealProbe
        except ImportError:
            pytest.skip("garak.probes.dan not available in this environment")

        result = get_probe_detector(RealProbe)
        assert result is not None, (
            "garak.probes.dan.Dan_11_0 returned no detector from get_probe_detector. "
            "Check if primary_detector or recommended_detector was removed or renamed."
        )
        # Primary detector may be a short form (e.g. "dan.DAN") or full path
        # ("garak.detectors.dan.DAN") depending on garak version — either is acceptable.
        assert isinstance(result, str) and len(result) > 0


# ---------------------------------------------------------------------------
# Taxonomy completeness guardrail
# ---------------------------------------------------------------------------


class TestTaxonomyCompleteness:
    """
    Guardrail: every module in the installed garak's probe package should have
    a corresponding entry in Rhesis's taxonomy.

    When this test fails after a garak upgrade, it means new probe modules were
    added and taxonomy.py needs to be updated.
    """

    def _get_installed_garak_modules(self):
        """Return the set of top-level probe module names from installed garak."""
        import importlib
        import pkgutil

        import garak.probes

        modules = set()
        for info in pkgutil.iter_modules(garak.probes.__path__):
            if info.name.startswith("_"):
                continue
            try:
                mod = importlib.import_module(f"garak.probes.{info.name}")
                if hasattr(mod, "__all__") or any(not n.startswith("_") for n in dir(mod)):
                    modules.add(info.name)
            except Exception:
                # Some modules may fail to import (missing optional deps)
                modules.add(info.name)
        return modules

    def _get_taxonomy_modules(self):
        from rhesis.backend.app.services.garak.taxonomy import GarakTaxonomy

        return set(GarakTaxonomy.MODULE_MAPPINGS.keys())

    # Modules kept in taxonomy for backward compatibility with garak <0.14.0.
    # These were valid probe modules in older versions but were removed or renamed
    # in 0.14.0+. They are intentionally preserved so existing test-set records
    # referencing these module names remain resolvable via the default mapping fallback.
    KNOWN_LEGACY_MODULES = {
        "gcg",  # Removed in garak 0.14.0
        "xss",  # Removed in garak 0.14.0
        "base64",  # Historical mapping for base64-encoded probes
    }

    def test_no_removed_modules_in_taxonomy(self):
        """
        Taxonomy should not reference probe modules that no longer exist in garak,
        except for known legacy modules kept for backward compatibility.
        """
        installed = self._get_installed_garak_modules()
        taxonomy_modules = self._get_taxonomy_modules()

        installed.discard("base")
        taxonomy_modules.discard("base")

        stale = (taxonomy_modules - installed) - self.KNOWN_LEGACY_MODULES
        assert not stale, (
            f"Taxonomy references garak probe modules that are no longer installed: "
            f"{sorted(stale)}. "
            f"Either add them to KNOWN_LEGACY_MODULES (if intentionally kept for "
            f"backward compat) or remove them from taxonomy.py."
        )

    def test_taxonomy_coverage_ratio_is_acceptable(self):
        """
        At least 60% of installed garak probe modules should be in the taxonomy.

        This is a soft guardrail — this test catches a wholesale taxonomy regression
        where many modules go missing at once after a garak upgrade.
        """
        installed = self._get_installed_garak_modules()
        taxonomy_modules = self._get_taxonomy_modules()
        installed.discard("base")
        installed.discard("test")

        covered = len(installed & taxonomy_modules)
        total = len(installed)
        ratio = covered / total if total > 0 else 1.0

        assert ratio >= 0.6, (
            f"Taxonomy covers only {covered}/{total} ({ratio:.0%}) of installed garak "
            f"probe modules. After a garak upgrade, update taxonomy.py to cover at least 60%."
        )

    def test_known_removed_modules_not_in_taxonomy(self):
        """
        Regression: modules renamed in v0.13.3 must not appear in taxonomy.
        'art' was renamed to 'atkgen'; 'knownbadsignatures' was renamed to 'av_spam_scanning'.
        """
        taxonomy_modules = self._get_taxonomy_modules()

        assert "art" not in taxonomy_modules, (
            "'art' is a stale key — it was renamed to 'atkgen' in garak v0.13.3."
        )
        assert "knownbadsignatures" not in taxonomy_modules, (
            "'knownbadsignatures' is a stale key — "
            "it was renamed to 'av_spam_scanning' in garak v0.13.3."
        )
