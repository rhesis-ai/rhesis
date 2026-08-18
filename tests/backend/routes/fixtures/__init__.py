"""
🧪 Fixtures Package for Route Testing

This package provides organized, domain-specific fixtures for route testing.
Fixtures are organized into logical packages for better maintainability.

Structure:
- entities/: Individual business entity fixtures organized by domain
  - categories.py, topics.py, requirements.py, endpoints.py, metrics.py
- relationships/: Complex fixtures with entity relationships
  - hierarchies.py, associations.py
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
from .factory_fixtures import *
from .mocks import *
from .relationships import *
from .utilities import *

__all__ = [
    # === FACTORY FIXTURES (Primary System) ===
    # Entity factory fixtures
    "requirement_factory",
    "topic_factory",
    "category_factory",
    "metric_factory",
    "model_factory",
    "endpoint_factory",
    "project_factory",
    "prompt_factory",
    # Data fixtures
    "requirement_data",
    "minimal_requirement_data",
    "requirement_update_data",
    "topic_data",
    "minimal_topic_data",
    "topic_update_data",
    "category_data",
    "metric_data",
    "model_data",
    "project_data",
    "minimal_project_data",
    "project_update_data",
    "prompt_data",
    "minimal_prompt_data",
    "prompt_update_data",
    # Edge case fixtures
    "long_name_requirement_data",
    "special_chars_requirement_data",
    "unicode_requirement_data",
    "sql_injection_requirement_data",
    "empty_requirement_data",
    # Batch fixtures
    "requirement_batch_data",
    "small_requirement_batch",
    # Composite fixtures (with automatic cleanup)
    "requirement_with_metrics",
    "topic_hierarchy",
    # Performance fixtures
    "large_entity_batch",
    # Parameterized fixtures
    "varied_requirement_data",
    "edge_case_requirement_data",
    # === USER FIXTURES (Enhanced System) ===
    # Mock user fixtures (unit tests)
    "mock_user_data",
    "mock_admin_data",
    "mock_inactive_user_data",
    "mock_user_object",
    # Database user fixtures (integration tests)
    "db_user",
    "db_admin",
    "db_inactive_user",
    "db_owner_user",
    "db_assignee_user",
    # Authenticated user fixtures
    "authenticated_user",
    "authenticated_user_data",
    "test_organization",
    # Convenience user fixtures
    "user_trio",
    "admin_and_user",
    # === LEGACY FIXTURES (Backward Compatibility) ===
    # Entity fixtures (deprecated - use factory fixtures instead)
    "sample_category",
    "parent_category",
    "sample_topic",
    "parent_topic",
    "sample_requirement",
    "sample_metric",
    "sample_endpoint",
    "sample_endpoints",
    "working_endpoint",
    "endpoint_with_complex_config",
    # Legacy user fixtures (deprecated - use enhanced user fixtures instead)
    "sample_user",
    "mock_user",
    "admin_user",
    "inactive_user",
    "db_authenticated_user",
    "db_admin_user",
    # Legacy relationship fixtures (deprecated - use composite fixtures instead)
    "topic_with_children",
    # Status and project fixtures
    "test_type_lookup",
    "project_entity_type",
    "db_status",
    "db_inactive_status",
    "db_draft_status",
    "db_project_status",
    "db_project",
    "db_inactive_project",
    "db_draft_project",
    # Utility fixtures
    "invalid_uuid",
    "malformed_uuid",
    # Mock fixtures
    "mock_endpoint_service",
]
