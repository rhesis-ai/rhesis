"""
🔗 API Endpoints Configuration

Centralized configuration for all API endpoints used in route testing.
This eliminates hardcoded endpoint strings and provides a single source of truth
for endpoint management across all test files.

Usage:
    from tests.backend.routes.endpoints import APIEndpoints

    # Use the endpoints
    response = client.post(APIEndpoints.REQUIREMENTS.create, json=data)
    response = client.get(APIEndpoints.TOPICS.list)
"""

from dataclasses import dataclass
from typing import Any, Dict


class EndpointBase:
    """Base class for endpoint configurations"""

    @classmethod
    def format_path(cls, path: str, **kwargs) -> str:
        """Format path with parameters"""
        return path.format(**kwargs)


@dataclass
class BaseEntityEndpoints(EndpointBase):
    """Base class for all entity endpoints with common patterns"""

    _base_entity: str = ""
    _id_param: str = ""

    def __post_init__(self):
        """Initialize endpoints using base entity name"""
        if not self._base_entity or not self._id_param:
            raise ValueError("_base_entity and _id_param must be set")

        # Base endpoints
        self.create = f"/{self._base_entity}/"
        self.list = f"/{self._base_entity}/"

        # Parameterized endpoints
        self.get_by_id = f"/{self._base_entity}/{{{self._id_param}}}"
        self.update = f"/{self._base_entity}/{{{self._id_param}}}"
        self.delete = f"/{self._base_entity}/{{{self._id_param}}}"

    def get(self, entity_id: str) -> str:
        """Get entity by ID endpoint"""
        return self.format_path(self.get_by_id, **{self._id_param: entity_id})

    def put(self, entity_id: str) -> str:
        """Update entity endpoint"""
        return self.format_path(self.update, **{self._id_param: entity_id})

    def remove(self, entity_id: str) -> str:
        """Delete entity endpoint"""
        return self.format_path(self.delete, **{self._id_param: entity_id})


@dataclass
class RequirementEndpoints(BaseEntityEndpoints):
    """Requirement API endpoints"""

    # Base entity configuration
    _base_entity: str = "requirements"
    _id_param: str = "requirement_id"

    def __post_init__(self):
        """Initialize requirement-specific endpoints"""
        # Initialize base endpoints
        super().__post_init__()

        # Requirement-specific relationship endpoints
        self.get_metrics = f"/{self._base_entity}/{{{self._id_param}}}/metrics/"
        self.add_metric = f"/{self._base_entity}/{{{self._id_param}}}/metrics/{{metric_id}}"
        self.remove_metric = f"/{self._base_entity}/{{{self._id_param}}}/metrics/{{metric_id}}"

    def metrics(self, entity_id: str) -> str:
        """Get entity metrics endpoint"""
        return self.format_path(self.get_metrics, **{self._id_param: entity_id})

    def add_metric_to_requirement(self, entity_id: str, metric_id: str) -> str:
        """Add metric to entity endpoint"""
        return self.format_path(self.add_metric, **{self._id_param: entity_id}, metric_id=metric_id)

    def remove_metric_from_requirement(self, entity_id: str, metric_id: str) -> str:
        """Remove metric from entity endpoint"""
        return self.format_path(
            self.remove_metric, **{self._id_param: entity_id}, metric_id=metric_id
        )


@dataclass
class TopicEndpoints(BaseEntityEndpoints):
    """Topic API endpoints"""

    # Base entity configuration
    _base_entity: str = "topics"
    _id_param: str = "topic_id"


@dataclass
class MetricEndpoints(BaseEntityEndpoints):
    """Metric API endpoints"""

    # Base entity configuration
    _base_entity: str = "metrics"
    _id_param: str = "metric_id"

    def __post_init__(self):
        """Initialize metric-specific endpoints"""
        # Initialize base endpoints
        super().__post_init__()

        # Generate endpoint
        self.generate = f"/{self._base_entity}/generate"

        # Improve endpoint
        self.improve_path = f"/{self._base_entity}/{{{self._id_param}}}/improve"

        # Metric-specific relationship endpoints
        self.get_requirements = f"/{self._base_entity}/{{{self._id_param}}}/requirements/"
        self.add_requirement = f"/{self._base_entity}/{{{self._id_param}}}/requirements/{{requirement_id}}"
        self.remove_requirement = (
            f"/{self._base_entity}/{{{self._id_param}}}/requirements/{{requirement_id}}"
        )

    def improve(self, entity_id: str) -> str:
        """Improve metric endpoint"""
        return self.format_path(self.improve_path, **{self._id_param: entity_id})

    def requirements(self, entity_id: str) -> str:
        """Get metric requirements endpoint"""
        return self.format_path(self.get_requirements, **{self._id_param: entity_id})

    def add_requirement_to_metric(self, entity_id: str, requirement_id: str) -> str:
        """Add requirement to metric endpoint"""
        return self.format_path(
            self.add_requirement, **{self._id_param: entity_id}, requirement_id=requirement_id
        )

    def remove_requirement_from_metric(self, entity_id: str, requirement_id: str) -> str:
        """Remove requirement from metric endpoint"""
        return self.format_path(
            self.remove_requirement, **{self._id_param: entity_id}, requirement_id=requirement_id
        )


@dataclass
class ModelEndpoints(BaseEntityEndpoints):
    """Model API endpoints"""

    # Base entity configuration
    _base_entity: str = "models"
    _id_param: str = "model_id"

    def __post_init__(self):
        """Initialize model-specific endpoints"""
        # Initialize base endpoints
        super().__post_init__()

        # Model-specific operation endpoints
        self.test_connection = f"/{self._base_entity}/{{{self._id_param}}}/test"

    def test(self, entity_id: str) -> str:
        """Test model connection endpoint"""
        return self.format_path(self.test_connection, **{self._id_param: entity_id})


@dataclass
class OrganizationEndpoints(BaseEntityEndpoints):
    """Organization API endpoints"""

    # Base entity configuration
    _base_entity: str = "organizations"
    _id_param: str = "organization_id"

    def __post_init__(self):
        """Initialize organization-specific endpoints"""
        # Initialize base endpoints
        super().__post_init__()

        # Organization-specific operation endpoints
        self.load_initial_data = f"/{self._base_entity}/{{{self._id_param}}}/load-initial-data"
        self.rollback_initial_data = (
            f"/{self._base_entity}/{{{self._id_param}}}/rollback-initial-data"
        )

    def load_data(self, entity_id: str) -> str:
        """Load initial data endpoint"""
        return self.format_path(self.load_initial_data, **{self._id_param: entity_id})

    def rollback_data(self, entity_id: str) -> str:
        """Rollback initial data endpoint"""
        return self.format_path(self.rollback_initial_data, **{self._id_param: entity_id})


@dataclass
class CategoryEndpoints(BaseEntityEndpoints):
    """Category API endpoints"""

    # Base entity configuration
    _base_entity: str = "categories"
    _id_param: str = "category_id"


@dataclass
class CommentEndpoints(BaseEntityEndpoints):
    """Comment API endpoints"""

    # Base entity configuration
    _base_entity: str = "comments"
    _id_param: str = "comment_id"

    def __post_init__(self):
        """Initialize comment-specific endpoints"""
        # Initialize base endpoints
        super().__post_init__()

        # Comment-specific endpoints
        self.get_by_entity = f"/{self._base_entity}/entity/{{entity_type}}/{{entity_id}}"
        self.add_emoji = f"/{self._base_entity}/{{{self._id_param}}}/emoji/{{emoji}}"
        self.remove_emoji = f"/{self._base_entity}/{{{self._id_param}}}/emoji/{{emoji}}"

    def by_entity(self, entity_type: str, entity_id: str) -> str:
        """Get comments by entity endpoint"""
        return self.format_path(self.get_by_entity, entity_type=entity_type, entity_id=entity_id)

    def add_emoji_reaction(self, comment_id: str, emoji: str) -> str:
        """Add emoji reaction endpoint"""
        return self.format_path(self.add_emoji, **{self._id_param: comment_id}, emoji=emoji)

    def remove_emoji_reaction(self, comment_id: str, emoji: str) -> str:
        """Remove emoji reaction endpoint"""
        return self.format_path(self.remove_emoji, **{self._id_param: comment_id}, emoji=emoji)


@dataclass
class AuthEndpoints:
    """Authentication API endpoints"""

    callback: str = "/auth/callback"
    logout: str = "/auth/logout"
    verify: str = "/auth/verify"


@dataclass
class HomeEndpoints:
    """Home API endpoints"""

    # Base paths
    BASE: str = "/home"

    # Home endpoints
    HOME: str = "/home/"
    PROTECTED: str = "/home/protected"


@dataclass
class EndpointEndpoints(BaseEntityEndpoints):
    """Endpoint API endpoints"""

    # Base entity configuration
    _base_entity: str = "endpoints"
    _id_param: str = "endpoint_id"

    # Special endpoint-specific operations
    def invoke(self, endpoint_id: str) -> str:
        """Get endpoint invoke URL"""
        return f"/{self._base_entity}/{endpoint_id}/invoke"

    @property
    def schema(self) -> str:
        """Get endpoint schema URL"""
        return f"/{self._base_entity}/schema"


# Factory function for creating endpoints dynamically
def create_entity_endpoints(entity_name: str, entity_class=BaseEntityEndpoints):
    """
    Factory function to create endpoint classes for any entity

    Args:
        entity_name: Name of the entity (e.g., 'requirements', 'topics')
        entity_class: Base class to use (defaults to BaseEntityEndpoints)

    Returns:
        Configured endpoint instance
    """
    # Handle irregular plurals properly
    irregular_plurals = {
        "statuses": "status",
        "responses": "response",
        # Add more as needed
    }

    # Get singular form
    if entity_name in irregular_plurals:
        singular = irregular_plurals[entity_name]
    else:
        singular = entity_name.rstrip("s")

    @dataclass
    class DynamicEntityEndpoints(entity_class):
        _base_entity: str = entity_name
        _id_param: str = f"{singular}_id"

    return DynamicEntityEndpoints()


class APIEndpoints:
    """Centralized API endpoints registry"""

    REQUIREMENTS = RequirementEndpoints()
    TOPICS = TopicEndpoints()
    METRICS = MetricEndpoints()
    MODELS = ModelEndpoints()
    ORGANIZATIONS = OrganizationEndpoints()
    CATEGORIES = CategoryEndpoints()
    COMMENTS = CommentEndpoints()
    AUTH = AuthEndpoints()
    HOME = HomeEndpoints()
    ENDPOINTS = EndpointEndpoints()

    # Project and Prompt endpoints
    PROJECTS = create_entity_endpoints("projects")
    PROMPTS = create_entity_endpoints("prompts")

    # New entity endpoints
    PROMPT_TEMPLATES = create_entity_endpoints("prompt_templates")
    SOURCES = create_entity_endpoints("sources")
    STATUSES = create_entity_endpoints("statuses")
    TAGS = create_entity_endpoints("tags")
    TOKENS = create_entity_endpoints("tokens")
    TYPE_LOOKUPS = create_entity_endpoints("type_lookups")

    @classmethod
    def get_all_endpoints(cls) -> Dict[str, Any]:
        """Get all available endpoints"""
        return {
            "requirements": cls.REQUIREMENTS,
            "topics": cls.TOPICS,
            "metrics": cls.METRICS,
            "models": cls.MODELS,
            "organizations": cls.ORGANIZATIONS,
        }

    @classmethod
    def validate_endpoints(cls) -> bool:
        """Validate all endpoints are properly formatted"""
        try:
            # Test basic endpoint access
            assert cls.REQUIREMENTS.create.startswith("/")
            assert cls.TOPICS.create.startswith("/")
            assert cls.METRICS.create.startswith("/")
            assert cls.MODELS.create.startswith("/")
            assert cls.ORGANIZATIONS.create.startswith("/")

            # Test parameterized endpoints
            test_id = "test-id"
            assert cls.REQUIREMENTS.get(test_id).endswith(test_id)
            assert cls.TOPICS.get(test_id).endswith(test_id)
            assert cls.METRICS.get(test_id).endswith(test_id)
            assert cls.MODELS.get(test_id).endswith(test_id)
            assert cls.ORGANIZATIONS.get(test_id).endswith(test_id)

            return True
        except (AssertionError, AttributeError, KeyError):
            return False


# Constants for common query parameters
class QueryParams:
    """Common query parameter names"""

    LIMIT = "limit"
    SKIP = "skip"
    SORT_BY = "sort_by"
    SORT_ORDER = "sort_order"
    FILTER = "filter"


# HTTP Status codes commonly used in tests
class HTTPStatus:
    """HTTP status codes for consistent testing"""

    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    UNPROCESSABLE_ENTITY = 422
    INTERNAL_SERVER_ERROR = 500


# Pagination defaults
class PaginationDefaults:
    """Default pagination values"""

    DEFAULT_LIMIT = 10
    MAX_LIMIT = 100
    DEFAULT_SKIP = 0


# Export main interface
__all__ = [
    "APIEndpoints",
    "RequirementEndpoints",
    "TopicEndpoints",
    "MetricEndpoints",
    "ModelEndpoints",
    "OrganizationEndpoints",
    "CategoryEndpoints",
    "CommentEndpoints",
    "AuthEndpoints",
    "HomeEndpoints",
    "EndpointEndpoints",
    "QueryParams",
    "HTTPStatus",
    "PaginationDefaults",
]
