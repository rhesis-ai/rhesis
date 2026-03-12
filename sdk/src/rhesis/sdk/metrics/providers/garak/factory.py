"""
Garak metric factory.

Factory for creating Garak detector metrics.
"""

import logging
from typing import List

from rhesis.sdk.metrics.base import BaseMetric, BaseMetricFactory

from .detector_metric import GarakDetectorMetric
from .registry import DETECTOR_PATHS, SUPPORTED_NAMES

logger = logging.getLogger(__name__)


class GarakMetricFactory(BaseMetricFactory):
    """Factory for creating Garak detector metrics."""

    SUPPORTED_DETECTORS = SUPPORTED_NAMES

    DETECTOR_PATHS = DETECTOR_PATHS

    ACCEPTED_PARAMS = {"name", "description", "model", "threshold"}

    def _filter_kwargs(self, kwargs: dict) -> dict:
        """Extract only params that GarakDetectorMetric accepts."""
        return {k: v for k, v in kwargs.items() if k in self.ACCEPTED_PARAMS}

    def create(self, class_name: str, **kwargs) -> BaseMetric:
        """
        Create a Garak detector metric.

        Args:
            class_name: Either:
                - "GarakDetectorMetric" with detector_class kwarg
                - A short detector name like "MitigationBypass"
                - A full detector path like "garak.detectors.mitigation.MitigationBypass"
            **kwargs: Additional arguments including:
                - detector_class: Full path to detector (required for GarakDetectorMetric)
                - name: Optional metric name
                - description: Optional metric description

        Returns:
            GarakDetectorMetric instance
        """
        if class_name == "GarakDetectorMetric":
            detector_class = kwargs.pop("detector_class", None)
            if not detector_class:
                detector_class = kwargs.pop("evaluation_prompt", None)
            if not detector_class:
                raise ValueError("detector_class is required when creating GarakDetectorMetric")
            filtered_kwargs = self._filter_kwargs(kwargs)
            return GarakDetectorMetric(detector_class=detector_class, **filtered_kwargs)

        if class_name in self.DETECTOR_PATHS:
            detector_class = self.DETECTOR_PATHS[class_name]
            if detector_class is None:
                raise ValueError(f"Cannot create {class_name} without detector_class")
            filtered_kwargs = self._filter_kwargs(kwargs)
            return GarakDetectorMetric(
                detector_class=detector_class,
                name=filtered_kwargs.get("name", class_name),
                **filtered_kwargs,
            )

        if "." in class_name and class_name.startswith("garak."):
            filtered_kwargs = self._filter_kwargs(kwargs)
            return GarakDetectorMetric(
                detector_class=class_name,
                **filtered_kwargs,
            )

        raise ValueError(
            f"Unknown Garak detector: {class_name}. "
            f"Supported detectors: {self.list_supported_metrics()}"
        )

    def list_supported_metrics(self) -> List[str]:
        """List all supported Garak detector metrics."""
        return list(self.SUPPORTED_DETECTORS)
