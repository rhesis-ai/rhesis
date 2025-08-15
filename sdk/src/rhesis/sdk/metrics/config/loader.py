from pathlib import Path
from typing import Any, Dict, List

import yaml


class MetricConfigLoader:
    """Loads and manages backend configurations from YAML."""

    def __init__(self):
        self._config_path = Path(__file__).parent / "backends.yml"
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load the configuration from YAML file."""
        with open(self._config_path, "r") as f:
            return yaml.safe_load(f)

    @property
    def backends(self) -> Dict[str, Dict[str, str]]:
        """Get all backend configurations."""
        return self._config["backends"]

    def get_backend_config(self, backend_name: str) -> Dict[str, str]:
        """Get configuration for a specific backend."""
        if backend_name not in self.backends:
            raise ValueError(f"Unknown backend: {backend_name}")
        return self.backends[backend_name]

    def list_backends(self) -> List[str]:
        """Get a list of all available backends."""
        return list(self.backends.keys())
