"""
Relationship Fixtures Package

This package provides fixtures for complex entity relationships and combinations.
Each module focuses on relationships between specific entity types.

Modules:
- hierarchies.py: Parent-child hierarchical relationships
- associations.py: Many-to-many associations between entities
"""

from .associations import *
from .hierarchies import *

__all__ = [
    # Hierarchical relationships
    "topic_with_children",
    # Associations
    "behavior_with_metrics",
]
