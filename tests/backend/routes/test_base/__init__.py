"""
🧪 Base Route Test Classes - Modular Architecture

This package provides a comprehensive, modular testing framework for backend route testing.
The framework includes automatic user field detection, comprehensive CRUD testing,
authentication validation, and performance testing.

## Architecture

The base test classes are organized into focused modules:

- **`core.py`** - Abstract base class and core functionality
- **`user_detection.py`** - Intelligent auto-detection of user relationship fields
- **`crud.py`** - Comprehensive CRUD operation tests
- **`user_relationships.py`** - User field testing (creation, updates, ownership transfer)
- **`list_operations.py`** - List operations, pagination, sorting, filtering
- **`authentication.py`** - Authentication requirement validation
- **`edge_cases.py`** - Edge cases, special characters, boundary conditions
- **`performance.py`** - Performance and bulk operation tests
- **`health.py`** - Basic health check tests

## Usage

```python
from tests.backend.routes.base import BaseEntityRouteTests

class TestMyEntity(BaseEntityRouteTests):
    entity_name = "my_entity"  # Auto-detection happens here!
    endpoints = APIEndpoints.MY_ENTITY

    def get_sample_data(self):
        return {"name": "Sample Entity"}

    def get_minimal_data(self):
        return {"name": "Minimal"}

    def get_update_data(self):
        return {"name": "Updated Entity"}
```

## Features

✨ **Automatic User Field Detection** - Zero configuration required
🧪 **Comprehensive Test Coverage** - CRUD, auth, edge cases, performance
🔧 **Modular Architecture** - Easy to extend and maintain
🚀 **Zero Setup** - Works out of the box for most entities
📊 **Intelligent Validation** - Graceful handling of data validation issues
"""

# Core base class and utilities
from .authentication import BaseAuthenticationTests
from .core import BaseEntityTests

# Individual test class modules
from .crud import BaseCRUDTests
from .edge_cases import BaseEdgeCaseTests
from .health import BaseHealthTests
from .list_operations import BaseListOperationTests
from .performance import BasePerformanceTests

# User field auto-detection
from .user_detection import UserFieldDetector
from .user_relationships import BaseUserRelationshipTests


# Composite test class that includes all standard tests
class BaseEntityRouteTests(
    BaseCRUDTests,
    BaseUserRelationshipTests,
    BaseListOperationTests,
    BaseAuthenticationTests,
    BaseEdgeCaseTests,
    BasePerformanceTests,
    BaseHealthTests,
):
    """
    Complete base test suite for any entity - includes all standard tests

    This class combines all the modular test classes into a comprehensive
    test suite that provides:

    - ✅ Full CRUD operation testing
    - 👤 Automatic user relationship field testing
    - 🔗 List operations and filtering
    - 🛡️ Authentication validation
    - 🏃‍♂️ Edge case handling
    - 🐌 Performance validation
    - ✅ Health checks

    Simply inherit from this class and define your entity-specific methods
    to get comprehensive test coverage with automatic user field detection.
    """

    pass


# Export everything for easy imports
__all__ = [
    # Main composite class
    "BaseEntityRouteTests",
    # Core classes
    "BaseEntityTests",
    # Individual test modules
    "BaseCRUDTests",
    "BaseUserRelationshipTests",
    "BaseListOperationTests",
    "BaseAuthenticationTests",
    "BaseEdgeCaseTests",
    "BasePerformanceTests",
    "BaseHealthTests",
    # Utilities
    "UserFieldDetector",
]
