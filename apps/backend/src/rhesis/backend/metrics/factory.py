from importlib import import_module
from typing import List

from .base import BaseMetric, BaseMetricFactory
from .config.loader import MetricConfigLoader
from .deepeval_metrics import DeepEvalMetricFactory


class MetricFactory:
    """Factory for creating metric instances from different backends."""

    def __init__(self):
        self.config = MetricConfigLoader()
        self._factories = {}

    def _load_factory(self, backend: str) -> BaseMetricFactory:
        """Dynamically load a factory class from configuration."""
        backend_config = self.config.get_backend_config(backend)
        module = import_module(backend_config["module"])
        factory_class = getattr(module, backend_config["factory"])
        return factory_class()

    def get_factory(self, backend: str) -> BaseMetricFactory:
        """Get the appropriate factory for the specified backend."""
        if backend not in self._factories:
            if backend not in self.config.backends:
                raise ValueError(f"Unknown backend: {backend}")
            self._factories[backend] = self._load_factory(backend)
        return self._factories[backend]

    def list_supported_metrics(self, backend: str = None) -> List[str]:
        """List supported metrics, optionally filtered by backend."""
        if backend:
            return list(self.config.get_metrics_for_backend(backend).keys())
        return list(self.config.metrics.keys())

    def list_supported_backends(self) -> List[str]:
        """List all supported backends."""
        return list(self.config.backends.keys())

    @staticmethod
    def create(framework: str, metric_name: str) -> BaseMetric:
        """Create a metric instance from the specified framework.

        Args:
            framework: The evaluation framework to use ('deepeval', 'ragas', etc.)
            metric_name: Name of metric to create ('answer_relevancy', etc.)

        Returns:
            BaseMetric: The corresponding metric implementation

        Raises:
            ValueError: If framework or metric_name is not supported
        """
        factories = {
            "deepeval": DeepEvalMetricFactory,
            # Add other frameworks as they're implemented
        }

        if framework not in factories:
            raise ValueError(
                f"Unsupported framework: {framework}. "
                f"Supported frameworks are: {list(factories.keys())}"
            )

        return factories[framework].create(metric_name)

    @staticmethod
    def list_supported_frameworks() -> List[str]:
        """List all supported evaluation frameworks."""
        return ["deepeval"]  # Add others as they're implemented

    @staticmethod
    def list_supported_metrics_for_framework(framework: str) -> List[str]:
        """List all supported metrics for a given framework.

        Args:
            framework: The evaluation framework

        Returns:
            List[str]: List of supported metric types
        """
        if framework == "deepeval":
            return ["answer_relevancy"]  # Add others as they're implemented
        raise ValueError(f"Unsupported framework: {framework}")
