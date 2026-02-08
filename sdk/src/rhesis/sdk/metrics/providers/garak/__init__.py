"""
Garak detector metric provider.

This module provides the GarakDetectorMetric class that wraps
Garak detectors as Rhesis metrics.
"""

from .detector_metric import GarakDetectorMetric
from .factory import GarakMetricFactory

__all__ = [
    "GarakDetectorMetric",
    "GarakMetricFactory",
]
