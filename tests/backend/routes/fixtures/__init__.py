"""
🧪 Fixtures Package for Route Testing

This package provides organized, domain-specific fixtures for route testing.
Fixtures are organized into logical packages for better maintainability.

Structure:
- entities/: Individual business entity fixtures organized by domain
  - dimensions.py, categories.py, topics.py, behaviors.py, endpoints.py, metrics.py
- relationships/: Complex fixtures with entity relationships
  - demographics.py, hierarchies.py, associations.py
- utilities/: Common test utilities and helpers
  - identifiers.py, generators.py, helpers.py
- mocks/: Service and external dependency mocks
  - services.py, external_apis.py, infrastructure.py

Usage:
    All fixtures are automatically imported via conftest.py
    and are available to all tests in the routes package.
"""

# Import all fixture packages to make them discoverable
from .entities import *
from .relationships import *
from .utilities import *
from .mocks import *

__all__ = [
    # Entity fixtures
    "sample_dimension", "sample_dimensions",
    "sample_category", "parent_category", 
    "sample_topic", "parent_topic",
    "sample_behavior",
    "sample_metric",
    "sample_endpoint", "sample_endpoints", "working_endpoint", "endpoint_with_complex_config",
    "sample_user", "mock_user", "admin_user", "inactive_user",
    "test_organization", "db_authenticated_user", "db_user", "db_admin_user", "db_owner_user", "db_assignee_user",
    "api_user", "api_owner_user", "api_assignee_user",
    "test_type_lookup", "db_status", "db_inactive_status", "db_draft_status",
    "db_project", "db_inactive_project", "db_draft_project",
    
    # Relationship fixtures
    "dimension_with_demographics",
    "topic_with_children",
    "behavior_with_metrics",
    
    # Utility fixtures
    "invalid_uuid", "malformed_uuid",
    
    # Mock fixtures
    "mock_endpoint_service"
]
