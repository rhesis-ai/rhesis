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
from .users import *  # Enhanced user fixtures
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
    
    # User fixtures (enhanced system with backward compatibility)
    # Mock fixtures (unit tests)
    "mock_user_data", "mock_admin_data", "mock_inactive_user_data", "mock_user_object",
    # Database fixtures (integration tests)  
    "db_user", "db_admin", "db_inactive_user", "db_owner_user", "db_assignee_user",
    # Authenticated fixtures
    "authenticated_user", "authenticated_user_data", "test_organization",
    # Convenience fixtures
    "user_trio", "admin_and_user",
    # Legacy aliases (backward compatibility)
    "sample_user", "mock_user", "admin_user", "inactive_user", "db_authenticated_user", "db_admin_user",
    
    # Status fixtures
    "test_type_lookup", "db_status", "db_inactive_status", "db_draft_status",
    
    # Project fixtures
    "db_project", "db_inactive_project", "db_draft_project"
]
