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
- users.py: User-related fixtures
"""

# Import all entity fixtures
from .dimensions import *
from .categories import *
from .topics import *
from .behaviors import *
from .endpoints import *
from .metrics import *
from .users import *
from .statuses import *
from .projects import *

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
    "sample_endpoint", "sample_endpoints", "working_endpoint", "endpoint_with_complex_config",
    
    # User fixtures
    "sample_user", "mock_user", "admin_user", "inactive_user",
    "test_organization", "db_authenticated_user", "db_user", "db_admin_user", "db_owner_user", "db_assignee_user",
    "api_user", "api_owner_user", "api_assignee_user",
    
    # Status fixtures
    "test_type_lookup", "db_status", "db_inactive_status", "db_draft_status",
    
    # Project fixtures
    "db_project", "db_inactive_project", "db_draft_project"
]
