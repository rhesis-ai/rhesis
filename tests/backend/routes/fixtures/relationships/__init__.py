"""
Relationship Fixtures Package

This package provides fixtures for complex entity relationships and combinations.
Each module focuses on relationships between specific entity types.

Modules:
- demographics.py: Dimension-demographic relationships
- hierarchies.py: Parent-child hierarchical relationships
- associations.py: Many-to-many associations between entities
"""

from .demographics import *
from .hierarchies import *
from .associations import *

__all__ = [
    # Demographic relationships
    "dimension_with_demographics",

    # Hierarchical relationships
    "topic_with_children",

    # Associations
    "behavior_with_metrics"
]
