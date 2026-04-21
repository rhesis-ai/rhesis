"""Tests for GarakMetricFactory."""

import pytest

from rhesis.sdk.metrics.providers.garak import GarakDetectorMetric, GarakMetricFactory
from rhesis.sdk.metrics.providers.garak.registry import (
    DETECTOR_PATHS,
    DETECTORS,
    LEGACY_ALIASES,
    SUPPORTED_NAMES,
)


@pytest.fixture
def factory():
    """Create a factory instance."""
    return GarakMetricFactory()


class TestFactoryListMetrics:
    """Tests for listing available metrics."""

    def test_list_supported_metrics(self, factory):
        """Test that factory lists all supported metrics."""
        metrics = factory.list_supported_metrics()

        assert isinstance(metrics, list)
        assert len(metrics) == len(SUPPORTED_NAMES)
        for name in SUPPORTED_NAMES:
            assert name in metrics, f"{name} missing from supported metrics"

    def test_list_supported_metrics_returns_copy(self, factory):
        """Test that list_supported_metrics returns a copy."""
        metrics1 = factory.list_supported_metrics()
        metrics2 = factory.list_supported_metrics()

        assert metrics1 == metrics2
        assert metrics1 is not metrics2

        metrics1.append("FakeMetric")
        assert "FakeMetric" not in metrics2


class TestFactoryCreateWithShortName:
    """Tests for creating metrics using short detector names."""

    @pytest.mark.parametrize(
        "name",
        SUPPORTED_NAMES,
        ids=SUPPORTED_NAMES,
    )
    def test_create_by_canonical_name(self, factory, name):
        """Each canonical detector name creates a valid metric."""
        metric = factory.create(name)

        assert isinstance(metric, GarakDetectorMetric)
        expected_path = DETECTOR_PATHS[name]
        assert metric.detector_class_path == expected_path
        assert metric.name == name

    @pytest.mark.parametrize(
        "alias,expected_path",
        sorted(LEGACY_ALIASES.items()),
        ids=sorted(LEGACY_ALIASES.keys()),
    )
    def test_create_by_legacy_alias(self, factory, alias, expected_path):
        """Legacy short names still resolve to the correct v0.14 path."""
        metric = factory.create(alias)

        assert isinstance(metric, GarakDetectorMetric)
        assert metric.detector_class_path == expected_path

    def test_create_with_threshold_only(self, factory):
        """Test creating short name detector with just threshold."""
        metric = factory.create("MitigationBypass", threshold=0.7)

        assert isinstance(metric, GarakDetectorMetric)
        assert metric.threshold == 0.7
        assert metric.name == "MitigationBypass"

    def test_create_with_description_only(self, factory):
        """Test creating short name detector with just description."""
        metric = factory.create("MitigationBypass", description="Custom description")

        assert isinstance(metric, GarakDetectorMetric)
        assert metric.description == "Custom description"


class TestFactoryCreateWithGarakDetectorMetric:
    """Tests for creating metrics using the GarakDetectorMetric class name."""

    def test_create_with_detector_class_kwarg(self, factory):
        """Test creating GarakDetectorMetric with detector_class kwarg."""
        metric = factory.create(
            "GarakDetectorMetric",
            detector_class="garak.detectors.custom.CustomDetector",
        )

        assert isinstance(metric, GarakDetectorMetric)
        assert metric.detector_class_path == "garak.detectors.custom.CustomDetector"

    def test_create_with_evaluation_prompt_as_detector_class(self, factory):
        """Test creating GarakDetectorMetric with evaluation_prompt storing detector class."""
        metric = factory.create(
            "GarakDetectorMetric",
            evaluation_prompt="garak.detectors.perspective.Toxicity",
        )

        assert isinstance(metric, GarakDetectorMetric)
        assert metric.detector_class_path == "garak.detectors.perspective.Toxicity"

    def test_create_garak_detector_metric_missing_detector_class(self, factory):
        """Test that creating GarakDetectorMetric without detector_class raises error."""
        with pytest.raises(ValueError, match="detector_class is required"):
            factory.create("GarakDetectorMetric")

    def test_create_with_custom_name(self, factory):
        """Test creating with custom name."""
        metric = factory.create(
            "GarakDetectorMetric",
            detector_class="garak.detectors.mitigation.MitigationBypass",
            name="My Custom Metric",
        )

        assert metric.name == "My Custom Metric"

    def test_create_with_custom_description(self, factory):
        """Test creating with custom description."""
        metric = factory.create(
            "GarakDetectorMetric",
            detector_class="garak.detectors.mitigation.MitigationBypass",
            description="Custom description",
        )

        assert metric.description == "Custom description"

    def test_create_with_custom_threshold(self, factory):
        """Test creating with custom threshold."""
        metric = factory.create(
            "GarakDetectorMetric",
            detector_class="garak.detectors.mitigation.MitigationBypass",
            threshold=0.8,
        )

        assert metric.threshold == 0.8


class TestFactoryCreateWithFullPath:
    """Tests for creating metrics using full detector paths."""

    def test_create_with_full_garak_path(self, factory):
        """Test creating metric with full garak.detectors path."""
        metric = factory.create(
            "garak.detectors.perspective.Toxicity",
        )

        assert isinstance(metric, GarakDetectorMetric)
        assert metric.detector_class_path == "garak.detectors.perspective.Toxicity"

    def test_create_with_full_path_and_threshold(self, factory):
        """Test creating metric with full path and custom threshold."""
        metric = factory.create(
            "garak.detectors.perspective.Toxicity",
            threshold=0.9,
        )

        assert metric.threshold == 0.9


class TestFactoryParameterFiltering:
    """Tests for parameter filtering behavior."""

    def test_threshold_is_passed_through(self, factory):
        """Test that threshold parameter is passed to the metric."""
        metric = factory.create("MitigationBypass", threshold=0.7)

        assert metric.threshold == 0.7

    def test_description_is_passed_through(self, factory):
        """Test that description parameter is passed to the metric."""
        metric = factory.create("MitigationBypass", description="Test description")

        assert metric.description == "Test description"

    def test_unsupported_params_are_filtered(self, factory):
        """Test that unsupported parameters are filtered out."""
        metric = factory.create(
            "MitigationBypass",
            score_type="numeric",
            metric_type="custom-code",
            backend="garak",
            metric_scope=["Single-Turn"],
            requires_ground_truth=False,
            requires_context=False,
        )

        assert isinstance(metric, GarakDetectorMetric)

    def test_accepted_params_constant(self, factory):
        """Test that ACCEPTED_PARAMS contains expected values."""
        expected_params = {"name", "description", "model", "threshold", "probe_notes"}
        assert factory.ACCEPTED_PARAMS == expected_params


class TestFactoryErrorHandling:
    """Tests for factory error handling."""

    def test_create_unknown_detector(self, factory):
        """Test that creating unknown detector raises error."""
        with pytest.raises(ValueError, match="Unknown Garak detector"):
            factory.create("UnknownDetector")

    def test_error_message_includes_available_detectors(self, factory):
        """Test that error message lists available detectors."""
        try:
            factory.create("UnknownDetector")
        except ValueError as e:
            error_msg = str(e)
            assert "MitigationBypass" in error_msg or "Supported detectors" in error_msg

    def test_create_with_invalid_path_format(self, factory):
        """Test that non-garak paths without dots raise error."""
        with pytest.raises(ValueError, match="Unknown Garak detector"):
            factory.create("SingleWord")

    def test_create_with_non_garak_path(self, factory):
        """Test that non-garak prefixed paths raise error."""
        with pytest.raises(ValueError, match="Unknown Garak detector"):
            factory.create("other.detectors.Something")


class TestFactoryIntegration:
    """Integration tests for factory."""

    def test_create_all_supported_detectors(self, factory):
        """Test creating all supported detector types."""
        supported = factory.list_supported_metrics()

        for detector_name in supported:
            metric = factory.create(detector_name)
            assert isinstance(metric, GarakDetectorMetric)
            assert metric.name == detector_name

    def test_factory_instances_are_independent(self, factory):
        """Test that created instances are independent."""
        metric1 = factory.create("MitigationBypass", threshold=0.3)
        metric2 = factory.create("MitigationBypass", threshold=0.7)

        assert metric1.threshold != metric2.threshold
        assert metric1 is not metric2

    def test_create_same_detector_twice(self, factory):
        """Test creating same detector type twice."""
        metric1 = factory.create("Continuation")
        metric2 = factory.create("Continuation")

        assert metric1.detector_class_path == metric2.detector_class_path
        assert metric1 is not metric2


class TestFactoryDetectorPaths:
    """Tests for detector path mapping."""

    def test_detector_paths_mapping(self, factory):
        """Test that all supported detectors have valid path mappings."""
        for detector_name in factory.list_supported_metrics():
            path = factory.DETECTOR_PATHS.get(detector_name)
            assert path is not None, f"Missing path mapping for {detector_name}"
            assert path.startswith("garak.detectors."), f"Invalid path for {detector_name}"

    def test_garak_detector_metric_path_is_none(self, factory):
        """Test that GarakDetectorMetric has None path (uses detector_class kwarg)."""
        assert factory.DETECTOR_PATHS.get("GarakDetectorMetric") is None

    def test_all_paths_follow_naming_convention(self, factory):
        """Test that all paths follow the garak.detectors.<module>.<Class> convention."""
        for detector_name, path in factory.DETECTOR_PATHS.items():
            if path is not None:
                parts = path.split(".")
                assert len(parts) == 4, f"Path {path} doesn't have 4 parts"
                assert parts[0] == "garak"
                assert parts[1] == "detectors"

    def test_registry_detector_count(self):
        """Ensure the YAML registry has the expected number of detectors."""
        assert len(DETECTORS) == 20

    def test_all_registry_detectors_in_factory(self, factory):
        """Every detector in the YAML registry is reachable via the factory."""
        for d in DETECTORS:
            metric = factory.create(d.name)
            assert metric.detector_class_path == d.path
