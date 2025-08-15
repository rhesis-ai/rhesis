"""
🔗 API Endpoints Configuration

Centralized configuration for all API endpoints used in route testing.
This eliminates hardcoded endpoint strings and provides a single source of truth
for endpoint management across all test files.

Usage:
    from tests.backend.routes.endpoints import APIEndpoints
    
    # Use the endpoints
    response = client.post(APIEndpoints.BEHAVIORS.create, json=data)
    response = client.get(APIEndpoints.TOPICS.list)
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any


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
class BehaviorEndpoints(BaseEntityEndpoints):
    """Behavior API endpoints"""
    
    # Base entity configuration
    _base_entity: str = "behaviors"
    _id_param: str = "behavior_id"
    
    def __post_init__(self):
        """Initialize behavior-specific endpoints"""
        # Initialize base endpoints
        super().__post_init__()
        
        # Behavior-specific relationship endpoints
        self.get_metrics = f"/{self._base_entity}/{{{self._id_param}}}/metrics/"
        self.add_metric = f"/{self._base_entity}/{{{self._id_param}}}/metrics/{{metric_id}}"
        self.remove_metric = f"/{self._base_entity}/{{{self._id_param}}}/metrics/{{metric_id}}"
    
    def metrics(self, entity_id: str) -> str:
        """Get entity metrics endpoint"""
        return self.format_path(self.get_metrics, **{self._id_param: entity_id})
    
    def add_metric_to_behavior(self, entity_id: str, metric_id: str) -> str:
        """Add metric to entity endpoint"""
        return self.format_path(self.add_metric, **{self._id_param: entity_id}, metric_id=metric_id)
    
    def remove_metric_from_behavior(self, entity_id: str, metric_id: str) -> str:
        """Remove metric from entity endpoint"""
        return self.format_path(self.remove_metric, **{self._id_param: entity_id}, metric_id=metric_id)


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


@dataclass
class CategoryEndpoints(BaseEntityEndpoints):
    """Category API endpoints"""

    # Base entity configuration
    _base_entity: str = "categories"
    _id_param: str = "category_id"


# Factory function for creating endpoints dynamically
def create_entity_endpoints(entity_name: str, entity_class=BaseEntityEndpoints):
    """
    Factory function to create endpoint classes for any entity
    
    Args:
        entity_name: Name of the entity (e.g., 'behaviors', 'topics')
        entity_class: Base class to use (defaults to BaseEntityEndpoints)
    
    Returns:
        Configured endpoint instance
    """
    @dataclass
    class DynamicEntityEndpoints(entity_class):
        _base_entity: str = entity_name
        _id_param: str = f"{entity_name.rstrip('s')}_id"
    
    return DynamicEntityEndpoints()


class APIEndpoints:
    """Centralized API endpoints registry"""

    BEHAVIORS = BehaviorEndpoints()
    TOPICS = TopicEndpoints()
    METRICS = MetricEndpoints()
    CATEGORIES = CategoryEndpoints()
    
    # Example of using the factory for future entities
    # PROMPTS = create_entity_endpoints("prompts")
    # MODELS = create_entity_endpoints("models")
    
    @classmethod
    def get_all_endpoints(cls) -> Dict[str, Any]:
        """Get all available endpoints"""
        return {
            "behaviors": cls.BEHAVIORS,
            "topics": cls.TOPICS,
            "metrics": cls.METRICS
        }
    
    @classmethod
    def validate_endpoints(cls) -> bool:
        """Validate all endpoints are properly formatted"""
        try:
            # Test basic endpoint access
            assert cls.BEHAVIORS.create.startswith("/")
            assert cls.TOPICS.create.startswith("/")
            assert cls.METRICS.create.startswith("/")
            
            # Test parameterized endpoints
            test_id = "test-id"
            assert cls.BEHAVIORS.get(test_id).endswith(test_id)
            assert cls.TOPICS.get(test_id).endswith(test_id)
            assert cls.METRICS.get(test_id).endswith(test_id)
            
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
    "BehaviorEndpoints", 
    "TopicEndpoints",
    "MetricEndpoints",
    "QueryParams",
    "HTTPStatus",
    "PaginationDefaults"
]
