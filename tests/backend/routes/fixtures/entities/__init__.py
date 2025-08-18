"""
🏗️ Entity Fixtures Package

This package provides fixtures for individual business entities.
Each module contains fixtures for a specific business domain.

Modules:
- dimensions.py: Dimension-related fixtures
- categories.py: Category-related fixtures
- topics.py: Topic-related fixtures
- behaviors.py: Behavior-related fixtures
- endpoints.py: Endpoint-related fixtures
- metrics.py: Metric-related fixtures
"""

# Import all entity fixtures
from .dimensions import *
from .categories import *
from .topics import *
from .behaviors import *
from .endpoints import *
from .metrics import *

__all__ = [
    # Dimension fixtures
    "sample_dimension", "sample_dimensions",
    
    # Category fixtures
    "sample_category", "parent_category",
    
    # Topic fixtures
    "sample_topic", "parent_topic",
    
    # Behavior fixtures
    "sample_behavior",
    
    # Metric fixtures
    "sample_metric",
    
    # Endpoint fixtures
    "sample_endpoint", "sample_endpoints", "working_endpoint", "endpoint_with_complex_config"
]
