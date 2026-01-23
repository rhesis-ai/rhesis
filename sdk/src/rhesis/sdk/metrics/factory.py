from importlib import import_module
from typing import List

from .base import BaseMetric, BaseMetricFactory
from .config.loader import MetricConfigLoader

# Use lazy loading to avoid circular imports
# from .deepeval.factory import DeepEvalMetricFactory
# from .ragas.factory import RagasMetricFactory
# from .rhesis.factory import RhesisMetricFactory


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

    def list_supported_backends(self) -> List[str]:
        """List all supported backends."""
        return self.config.list_backends()

    @staticmethod
    def create(framework: str, class_name: str, **kwargs) -> BaseMetric:
        """Create a metric instance from the specified framework using class name.

        Args:
            framework: The evaluation framework to use ('deepeval', 'ragas', 'rhesis', 'custom', 'garak')
            class_name: Class name of the metric to instantiate (e.g., 'DeepEvalContextualRecall')
            **kwargs: Additional parameters to pass to the metric constructor

        Returns:
            BaseMetric: The corresponding metric implementation

        Raises:
            ValueError: If framework is not supported
            AttributeError: If the class does not exist in the framework
        """

        # Lazy load factories to avoid circular imports
        def get_deepeval_factory():
            from rhesis.sdk.metrics.providers.deepeval import DeepEvalMetricFactory

            return DeepEvalMetricFactory()

        def get_ragas_factory():
            from rhesis.sdk.metrics.providers.ragas import RagasMetricFactory

            return RagasMetricFactory()

        def get_rhesis_factory():
            from rhesis.sdk.metrics.providers.native.factory import RhesisMetricFactory

            return RhesisMetricFactory()

        def get_garak_factory():
            from rhesis.sdk.metrics.providers.garak import GarakMetricFactory

            return GarakMetricFactory()

        factories = {
            "deepeval": get_deepeval_factory(),
            "ragas": get_ragas_factory(),
            "rhesis": get_rhesis_factory(),
            "custom": get_rhesis_factory(),
            "garak": get_garak_factory(),
        }

        if framework not in factories:
            raise ValueError(
                f"Unsupported framework: {framework}. "
                f"Supported frameworks are: {list(factories.keys())}"
            )

        return factories[framework].create(class_name, **kwargs)

    @staticmethod
    def list_supported_frameworks() -> List[str]:
        """List all supported evaluation frameworks."""
        return ["deepeval", "ragas", "rhesis", "custom", "garak"]

    @staticmethod
    def list_supported_metrics_for_framework(framework: str) -> List[str]:
        """List all supported metrics for a given framework.

        Args:
            framework: The evaluation framework

        Returns:
            List[str]: List of supported metric class names
        """
        if framework == "deepeval":
            from rhesis.sdk.metrics.providers.deepeval import DeepEvalMetricFactory

            return DeepEvalMetricFactory().list_supported_metrics()
        elif framework == "ragas":
            from rhesis.sdk.metrics.providers.ragas import RagasMetricFactory

            return RagasMetricFactory().list_supported_metrics()
        elif framework == "rhesis":
            from rhesis.sdk.metrics.providers.native.factory import RhesisMetricFactory

            return RhesisMetricFactory().list_supported_metrics()
        elif framework == "garak":
            from rhesis.sdk.metrics.providers.garak import GarakMetricFactory

            return GarakMetricFactory().list_supported_metrics()
        raise ValueError(f"Unsupported framework: {framework}")
