from pathlib import Path
from typing import Any, Dict

import yaml


class MetricConfigLoader:
    """Loads and manages metric configurations from YAML."""

    def __init__(self):
        self._config_path = Path(__file__).parent / "metrics.yml"
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load the configuration from YAML file."""
        with open(self._config_path, "r") as f:
            return yaml.safe_load(f)

    @property
    def metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get all metric configurations."""
        return self._config["metrics"]

    @property
    def backends(self) -> Dict[str, Dict[str, str]]:
        """Get all backend configurations."""
        return self._config["backends"]

    def get_metric_config(self, metric_name: str) -> Dict[str, Any]:
        """Get configuration for a specific metric."""
        if metric_name not in self.metrics:
            raise ValueError(f"Unknown metric: {metric_name}")
        return self.metrics[metric_name]

    def get_backend_config(self, backend_name: str) -> Dict[str, str]:
        """Get configuration for a specific backend."""
        if backend_name not in self.backends:
            raise ValueError(f"Unknown backend: {backend_name}")
        return self.backends[backend_name]

    def get_metrics_for_backend(self, backend_name: str) -> Dict[str, Dict[str, Any]]:
        """Get all metrics that use a specific backend."""
        return {
            name: config
            for name, config in self.metrics.items()
            if config["backend"] == backend_name
        }
