"""Tests for GarakDetectorMetric."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.metrics.base import MetricScope, MetricType, ScoreType
from rhesis.sdk.metrics.providers.garak import GarakDetectorMetric


class TestGarakDetectorMetricInitialization:
    """Tests for GarakDetectorMetric initialization."""

    def test_initialization_with_full_detector_path(self):
        """Test initialization with a full Garak detector path."""
        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")

        assert metric.detector_class_path == "garak.detectors.mitigation.MitigationBypass"
        assert metric.threshold == GarakDetectorMetric.DEFAULT_THRESHOLD
        assert metric.name == "Garak: MitigationBypass"
        assert metric.score_type == ScoreType.NUMERIC
        assert metric.metric_type == MetricType.CUSTOM_CODE
        assert MetricScope.SINGLE_TURN in metric.metric_scope

    def test_initialization_with_relative_detector_path(self):
        """Test initialization with a relative detector path."""
        metric = GarakDetectorMetric(detector_class="mitigation.MitigationBypass")

        assert metric.detector_class_path == "mitigation.MitigationBypass"
        assert metric.name == "Garak: MitigationBypass"

    def test_initialization_with_custom_name(self):
        """Test initialization with a custom metric name."""
        metric = GarakDetectorMetric(
            detector_class="garak.detectors.toxicity.ToxicityDetector",
            name="Custom Toxicity Detector",
        )

        assert metric.name == "Custom Toxicity Detector"

    def test_initialization_with_custom_description(self):
        """Test initialization with a custom description."""
        metric = GarakDetectorMetric(
            detector_class="garak.detectors.xss.XSSDetector",
            description="Detect XSS vulnerabilities",
        )

        assert metric.description == "Detect XSS vulnerabilities"

    def test_initialization_with_custom_threshold(self):
        """Test initialization with a custom threshold."""
        metric = GarakDetectorMetric(
            detector_class="garak.detectors.mitigation.MitigationBypass",
            threshold=0.7,
        )

        assert metric.threshold == 0.7

    def test_default_threshold_value(self):
        """Test that default threshold is 0.5."""
        assert GarakDetectorMetric.DEFAULT_THRESHOLD == 0.5

        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")
        assert metric.threshold == 0.5

    def test_initialization_with_zero_threshold(self):
        """Test initialization with zero threshold."""
        metric = GarakDetectorMetric(
            detector_class="garak.detectors.mitigation.MitigationBypass",
            threshold=0.0,
        )

        # Zero threshold should be preserved, not replaced with default
        assert metric.threshold == 0.0

    def test_metric_config_properties(self):
        """Test that metric config properties are set correctly."""
        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")

        assert metric.requires_ground_truth is False
        assert metric.requires_context is False


class TestGarakDetectorMetricDetectorLoading:
    """Tests for lazy detector loading."""

    def test_detector_is_lazy_loaded(self):
        """Test that detector is not loaded until accessed."""
        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")

        # Detector should not be loaded yet
        assert metric._detector is None

    @patch("importlib.import_module")
    def test_detector_loading_normalizes_relative_path(self, mock_import):
        """Test that relative paths are normalized to full Garak paths."""
        mock_module = MagicMock()
        mock_detector_class = MagicMock()
        mock_module.MitigationBypass = mock_detector_class
        mock_import.return_value = mock_module

        metric = GarakDetectorMetric(detector_class="mitigation.MitigationBypass")

        # Access the detector to trigger loading
        _ = metric.detector

        # Should have normalized the path
        mock_import.assert_called_once_with("garak.detectors.mitigation")

    @patch("importlib.import_module")
    def test_detector_loading_preserves_full_path(self, mock_import):
        """Test that full paths are preserved during loading."""
        mock_module = MagicMock()
        mock_detector_class = MagicMock()
        mock_module.XSSDetector = mock_detector_class
        mock_import.return_value = mock_module

        metric = GarakDetectorMetric(detector_class="garak.detectors.xss.XSSDetector")

        _ = metric.detector

        mock_import.assert_called_once_with("garak.detectors.xss")

    @patch("importlib.import_module")
    def test_detector_loading_passes_kwargs(self, mock_import):
        """Test that additional kwargs are passed to detector constructor."""
        mock_module = MagicMock()
        mock_detector_class = MagicMock()
        mock_module.CustomDetector = mock_detector_class
        mock_import.return_value = mock_module

        metric = GarakDetectorMetric(
            detector_class="garak.detectors.custom.CustomDetector",
            custom_param="value",
            another_param=42,
        )

        _ = metric.detector

        mock_detector_class.assert_called_once_with(custom_param="value", another_param=42)

    def test_invalid_detector_path_raises_error(self):
        """Test that invalid detector path raises ImportError."""
        metric = GarakDetectorMetric(detector_class="InvalidPath")

        with pytest.raises(ImportError):
            _ = metric.detector

    @patch("importlib.import_module")
    def test_missing_detector_class_raises_import_error(self, mock_import):
        """Test that missing detector class raises ImportError."""
        mock_module = MagicMock()
        mock_module.NonExistent = MagicMock(side_effect=AttributeError)
        del mock_module.NonExistent  # Remove the attribute
        mock_import.return_value = mock_module

        metric = GarakDetectorMetric(detector_class="garak.detectors.fake.NonExistent")

        with pytest.raises(ImportError, match="not found in module"):
            _ = metric.detector


class TestGarakDetectorMetricEvaluate:
    """Tests for the evaluate method."""

    def test_evaluate_returns_metric_result(self):
        """Test that evaluate returns a MetricResult."""
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [0.2]

        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")

        # Directly set the detector to avoid lazy loading issues
        metric._detector = mock_detector

        # Mock the Attempt class import inside the evaluate method
        mock_attempt = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "garak": MagicMock(),
                "garak.attempt": MagicMock(Attempt=MagicMock(return_value=mock_attempt)),
            },
        ):
            result = metric.evaluate(input="Test prompt", output="Model response")

        assert result.score == 0.2
        assert "is_successful" in result.details
        assert result.details["is_successful"] is True  # 0.2 < 0.5 threshold
        assert result.details["threshold"] == 0.5
        assert "detector" in result.details

    def test_evaluate_with_attack_detected(self):
        """Test evaluate when attack is detected (score >= threshold)."""
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [0.8]

        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")
        metric._detector = mock_detector

        mock_attempt = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "garak": MagicMock(),
                "garak.attempt": MagicMock(Attempt=MagicMock(return_value=mock_attempt)),
            },
        ):
            result = metric.evaluate(input="Malicious prompt", output="Unsafe response")

        assert result.score == 0.8
        assert result.details["is_successful"] is False  # 0.8 >= 0.5 threshold
        assert "vulnerability" in result.details["reason"].lower()

    def test_evaluate_with_multiple_scores(self):
        """Test evaluate when detector returns multiple scores."""
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [0.1, 0.3, 0.7]  # Max is 0.7

        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")
        metric._detector = mock_detector

        mock_attempt = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "garak": MagicMock(),
                "garak.attempt": MagicMock(Attempt=MagicMock(return_value=mock_attempt)),
            },
        ):
            result = metric.evaluate(input="Test", output="Response")

        # Should use max score
        assert result.score == 0.7
        assert result.details["raw_scores"] == [0.1, 0.3, 0.7]
        assert result.details["is_successful"] is False  # 0.7 >= 0.5

    def test_evaluate_with_scalar_result(self):
        """Test evaluate when detector returns a scalar instead of list."""
        mock_detector = MagicMock()
        mock_detector.detect.return_value = 0.4  # Scalar result

        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")
        metric._detector = mock_detector

        mock_attempt = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "garak": MagicMock(),
                "garak.attempt": MagicMock(Attempt=MagicMock(return_value=mock_attempt)),
            },
        ):
            result = metric.evaluate(input="Test", output="Response")

        assert result.score == 0.4
        assert result.details["raw_scores"] == [0.4]

    def test_evaluate_with_custom_threshold(self):
        """Test evaluate respects custom threshold."""
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [0.6]

        metric = GarakDetectorMetric(
            detector_class="garak.detectors.mitigation.MitigationBypass",
            threshold=0.8,  # Higher threshold
        )
        metric._detector = mock_detector

        mock_attempt = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "garak": MagicMock(),
                "garak.attempt": MagicMock(Attempt=MagicMock(return_value=mock_attempt)),
            },
        ):
            result = metric.evaluate(input="Test", output="Response")

        # 0.6 < 0.8, so should be successful
        assert result.details["is_successful"] is True
        assert result.details["threshold"] == 0.8

    def test_evaluate_creates_attempt_correctly(self):
        """Test that Attempt object is created with correct data."""
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [0.0]

        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")
        metric._detector = mock_detector

        mock_attempt = MagicMock()
        mock_attempt_cls = MagicMock(return_value=mock_attempt)

        with patch.dict(
            "sys.modules",
            {
                "garak": MagicMock(),
                "garak.attempt": MagicMock(Attempt=mock_attempt_cls),
            },
        ):
            metric.evaluate(input="Test input prompt", output="Model output response")

        # Verify Attempt was configured correctly
        assert mock_attempt.prompt == "Test input prompt"
        assert mock_attempt.outputs == ["Model output response"]

    def test_evaluate_handles_import_error(self):
        """Test that ImportError is handled gracefully."""
        metric = GarakDetectorMetric(detector_class="garak.detectors.nonexistent.FakeDetector")

        result = metric.evaluate(input="Test", output="Response")

        # Should return error result
        assert result.score == 1.0  # Max score indicates failure
        assert result.details["is_successful"] is False
        assert "error" in result.details

    def test_evaluate_handles_detector_exception(self):
        """Test that detector exceptions are handled gracefully."""
        mock_detector = MagicMock()
        mock_detector.detect.side_effect = RuntimeError("Detector failed")

        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")
        metric._detector = mock_detector

        mock_attempt = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "garak": MagicMock(),
                "garak.attempt": MagicMock(Attempt=MagicMock(return_value=mock_attempt)),
            },
        ):
            result = metric.evaluate(input="Test", output="Response")

        assert result.score == 1.0
        assert result.details["is_successful"] is False
        assert "error" in result.details
        assert "Detector failed" in result.details["error"]


class TestGarakDetectorMetricRepr:
    """Tests for string representation."""

    def test_repr(self):
        """Test __repr__ returns expected format."""
        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")

        repr_str = repr(metric)

        assert "GarakDetectorMetric" in repr_str
        assert "garak.detectors.mitigation.MitigationBypass" in repr_str


class TestGarakDetectorMetricEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_evaluate_with_empty_output_list(self):
        """Test evaluate when detector returns empty list."""
        mock_detector = MagicMock()
        mock_detector.detect.return_value = []

        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")
        metric._detector = mock_detector

        mock_attempt = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "garak": MagicMock(),
                "garak.attempt": MagicMock(Attempt=MagicMock(return_value=mock_attempt)),
            },
        ):
            result = metric.evaluate(input="Test", output="Response")

        # Empty list should default to 0.0
        assert result.score == 0.0
        assert result.details["is_successful"] is True

    def test_evaluate_with_tuple_result(self):
        """Test evaluate when detector returns a tuple instead of list."""
        mock_detector = MagicMock()
        mock_detector.detect.return_value = (0.3, 0.5)  # Tuple result

        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")
        metric._detector = mock_detector

        mock_attempt = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "garak": MagicMock(),
                "garak.attempt": MagicMock(Attempt=MagicMock(return_value=mock_attempt)),
            },
        ):
            result = metric.evaluate(input="Test", output="Response")

        # Should handle tuple like list
        assert result.score == 0.5  # max of tuple
        assert result.details["raw_scores"] == [0.3, 0.5]

    def test_threshold_exactly_at_boundary(self):
        """Test behavior when score equals threshold exactly."""
        # Score >= threshold means attack detected (is_successful = False)
        # Score < threshold means safe (is_successful = True)
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [0.5]  # Exactly at threshold

        metric = GarakDetectorMetric(
            detector_class="garak.detectors.mitigation.MitigationBypass",
            threshold=0.5,
        )
        metric._detector = mock_detector

        mock_attempt = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "garak": MagicMock(),
                "garak.attempt": MagicMock(Attempt=MagicMock(return_value=mock_attempt)),
            },
        ):
            result = metric.evaluate(input="Test", output="Response")

        # 0.5 >= 0.5, so NOT successful (attack detected)
        assert result.details["is_successful"] is False

    def test_evaluate_with_empty_input(self):
        """Test evaluate with empty input string."""
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [0.0]

        metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")
        metric._detector = mock_detector

        mock_attempt = MagicMock()
        mock_attempt_cls = MagicMock(return_value=mock_attempt)

        with patch.dict(
            "sys.modules",
            {
                "garak": MagicMock(),
                "garak.attempt": MagicMock(Attempt=mock_attempt_cls),
            },
        ):
            # Should not raise error with empty input
            result = metric.evaluate(input="", output="Response")

        assert mock_attempt.prompt == ""
        assert result is not None
