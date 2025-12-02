"""
🧪 Metrics Test Fixtures

This module contains fixtures for testing the current backend metrics infrastructure.
These fixtures support baseline regression tests to lock in current behavior before migration.
"""

from .metric_factories import *
from .metric_fixtures import *

__all__ = [
    # Factories
    "MetricConfigFactory",
    "RhesisMetricConfigFactory",
    "RagasMetricConfigFactory",
    "DeepEvalMetricConfigFactory",
    # Fixtures - Config fixtures
    "numeric_metric_config",
    "categorical_metric_config",
    "binary_metric_config",
    "rhesis_metric_with_model",
    "ragas_metric_config",
    "metric_configs_batch",
    # Fixtures - Mock responses
    "mock_llm_response",
    "mock_llm_categorical_response",
    "mock_llm_binary_response",
    # Fixtures - Database entities
    "test_model",
    "test_metric_numeric",
    "test_metric_categorical",
    "test_behavior_with_metrics",
]
