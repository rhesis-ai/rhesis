"""
🧪 Metrics Test Configuration

This conftest.py makes all metrics fixtures available to test modules.
"""

# Import all fixtures from the local fixtures package (relative import)
from .fixtures import *

# Explicit imports to ensure availability
from .fixtures.metric_fixtures import (
    numeric_metric_config,
    categorical_metric_config,
    binary_metric_config,
    rhesis_metric_with_model,
    ragas_metric_config,
    metric_configs_batch,
    mock_llm_response,
    mock_llm_categorical_response,
    mock_llm_binary_response,
    test_model,
    test_metric_numeric,
    test_metric_categorical,
    test_behavior_with_metrics,
)

# This makes all fixtures automatically available to any test file
# in the metrics/ directory without explicit imports

