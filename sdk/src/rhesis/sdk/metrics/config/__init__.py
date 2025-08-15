import os
from pathlib import Path
from typing import Any, Dict, List

import yaml


def get_metrics_config_path() -> Path:
    """Get the path to the metrics configuration directory."""
    return Path(__file__).parent


def load_backends_config() -> Dict[str, Any]:
    """Load the backend configuration from backends.yml."""
    config_path = get_metrics_config_path() / "backends.yml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config


def load_default_metrics() -> List[Dict[str, Any]]:
    """Load the default metrics configuration from defaults.yml."""
    config_path = get_metrics_config_path() / "defaults.yml"
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config.get("default_metrics", [])
    except FileNotFoundError:
        # Fall back to hard-coded defaults if file not found
        return [
            {
                "name": "Answer Relevancy",
                "class_name": "DeepEvalAnswerRelevancy",
                "backend": "deepeval",
                "threshold": 0.7,
                "description": "Measures how relevant the answer is to the question",
            }
        ]
