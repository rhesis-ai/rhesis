"""Unit tests for unsupported garak detectors.

The package-hallucination detectors (PythonPypi, RubyGems, …) report
"not implemented" instead of running. The short-circuit happens before any
garak import, so these tests run even when garak is not installed — which is
the environment where this safety behavior matters most. They are kept out of
the integration smoke-test module (which is skipped without garak) for exactly
that reason.
"""

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "path",
    [
        "garak.detectors.packagehallucination.PythonPypi",
        "garak.detectors.packagehallucination.RubyGems",
    ],
)
def test_packagehallucination_reports_not_implemented(path: str):
    from rhesis.sdk.metrics.providers.garak import GarakDetectorMetric

    metric = GarakDetectorMetric(detector_class=path)
    result = metric.evaluate(input="Is this safe?", output="import fakepkg123xyz")

    assert result.score is None
    assert result.details.get("not_implemented") is True
    assert result.details.get("inconclusive") is True


def test_supported_detector_is_not_short_circuited():
    """A normal detector is not flagged unsupported (guards the module match)."""
    from rhesis.sdk.metrics.providers.garak import GarakDetectorMetric

    metric = GarakDetectorMetric(detector_class="garak.detectors.mitigation.MitigationBypass")
    assert metric._is_unsupported() is False
