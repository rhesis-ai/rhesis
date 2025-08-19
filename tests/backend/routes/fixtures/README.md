# 🧪 Fixture System Documentation

Welcome to the enhanced Rhesis test fixture system! This documentation provides a comprehensive guide to using our factory-based fixtures for clean, maintainable, and efficient testing.

## 📋 Table of Contents

- [🎯 Quick Start](#-quick-start)
- [🏗️ Architecture Overview](#%EF%B8%8F-architecture-overview)
- [🧩 Fixture Categories](#-fixture-categories)
- [📊 Data Factories](#-data-factories)
- [🏭 Entity Factories](#-entity-factories)
- [👤 User Fixtures](#-user-fixtures)
- [🔗 Composite Fixtures](#-composite-fixtures)
- [⚡ Performance Fixtures](#-performance-fixtures)
- [🎯 Best Practices](#-best-practices)


## 🎯 Quick Start

### For Unit Tests (Fast, No Database)
```python
def test_business_logic(mock_user_data):
    # Use mock data for fast unit tests
    result = process_user_data(mock_user_data)
    assert result.success
```

### For Integration Tests (Real Database)
```python
def test_api_endpoint(behavior_factory):
    # Create entity with automatic cleanup
    behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
    
    response = behavior_factory.client.get(f"/behaviors/{behavior['id']}")
    assert response.status_code == 200
    # Automatic cleanup after test
```

### For Relationship Testing
```python
def test_complex_relationships(behavior_with_metrics):
    # Pre-created relationships with automatic cleanup
    behavior = behavior_with_metrics["behavior"]
    metrics = behavior_with_metrics["metrics"]
    
    assert len(metrics) == 2
    # All entities cleaned up automatically
```

## 🏗️ Architecture Overview

```
tests/backend/routes/fixtures/
├── 📊 data_factories.py      # Data generation (BehaviorDataFactory, etc.)
├── 🏭 factories.py           # Entity creation & cleanup (EntityFactory, etc.)
├── 🧩 factory_fixtures.py    # Pytest fixture integration
├── entities/
│   ├── users_v2.py           # Simplified user fixtures
│   └── ...                   # Other entity fixtures
└── README.md                 # This documentation
```

### Key Principles

1. **🧹 Automatic Cleanup**: All factory fixtures clean up after themselves
2. **🎯 Clear Purpose**: Fixture names indicate their intended use
3. **⚡ Performance**: Proper scoping for optimal test speed
4. **🔄 Consistency**: Unified patterns across all entities

## 🧩 Fixture Categories

### 🎭 Mock Fixtures (Unit Tests)
**Purpose**: Fast tests without database interaction
**Naming**: `mock_*`

```python
def test_unit_logic(mock_user_data):
    # Fast, no database needed
    result = validate_user_data(mock_user_data)
    assert result.is_valid
```

### 🗄️ Database Fixtures (Integration Tests)
**Purpose**: Real database entities for integration testing
**Naming**: `db_*`

```python
def test_database_integration(db_user):
    # Real user in test database
    assert db_user.id is not None
    assert db_user.is_active is True
```

### 🏭 Factory Fixtures (Entity Management)
**Purpose**: Create and clean up test entities
**Naming**: `*_factory`

```python
def test_entity_creation(behavior_factory):
    # Automatic cleanup
    behavior = behavior_factory.create({"name": "Test"})
    assert behavior["id"] is not None
```

### 📊 Data Fixtures (Test Data)
**Purpose**: Consistent test data generation
**Naming**: `*_data`

```python
def test_with_consistent_data(behavior_data):
    # Pre-generated test data
    assert "name" in behavior_data
    assert behavior_data["name"] is not None
```

## 📊 Data Factories

Data factories provide consistent, realistic test data generation.

### Available Factories

| Factory | Purpose | Key Methods |
|---------|---------|-------------|
| `BehaviorDataFactory` | Behavior test data | `sample_data()`, `minimal_data()`, `edge_case_data()` |
| `TopicDataFactory` | Topic test data | `sample_data()`, `hierarchy_data()` |
| `CategoryDataFactory` | Category test data | `sample_data()`, `minimal_data()` |
| `MetricDataFactory` | Metric test data | `sample_data()`, `update_data()` |
| `DimensionDataFactory` | Dimension test data | `sample_data()`, `minimal_data()` |

### Usage Examples

```python
# Standard data
data = BehaviorDataFactory.sample_data()

# Minimal data (only required fields)
data = BehaviorDataFactory.minimal_data()

# Edge cases
data = BehaviorDataFactory.edge_case_data("long_name")
data = BehaviorDataFactory.edge_case_data("special_chars")
data = BehaviorDataFactory.edge_case_data("unicode")

# Batch data
batch = BehaviorDataFactory.batch_data(count=10, variation=True)

# Custom variations
data = BehaviorDataFactory.sample_data(
    name_length=50, 
    include_description=False
)
```

### Edge Case Types

| Type | Description | Use Case |
|------|-------------|----------|
| `long_name` | Very long names (1000+ chars) | Boundary testing |
| `special_chars` | Special characters & emojis | Input validation |
| `unicode` | International characters | Encoding/decoding |
| `sql_injection` | SQL injection attempts | Security testing |
| `empty_strings` | Empty string values | Validation testing |
| `only_spaces` | Whitespace-only values | Sanitization testing |

## 🏭 Entity Factories

Entity factories create and manage test entities with automatic cleanup.

### Core Factory: `EntityFactory`

```python
class EntityFactory:
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]
    def create_batch(self, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]
    def cleanup(self) -> None
    def get_created_ids(self) -> List[str]
```

### Specialized Factories

#### `BehaviorFactory`
```python
def test_behavior_with_metrics(behavior_factory, metric_factory):
    # Create metrics first
    metrics = metric_factory.create_batch([
        MetricDataFactory.sample_data(),
        MetricDataFactory.sample_data()
    ])
    
    # Create behavior with metrics
    behavior = behavior_factory.create_with_metrics(
        BehaviorDataFactory.sample_data(),
        [m["id"] for m in metrics]
    )
```

#### `TopicFactory`
```python
def test_topic_hierarchy(topic_factory):
    hierarchy = topic_factory.create_hierarchy(
        parent_data=TopicDataFactory.sample_data(),
        children_data=[TopicDataFactory.sample_data() for _ in range(3)]
    )
    
    assert hierarchy["parent"]["id"] is not None
    assert len(hierarchy["children"]) == 3
```

### Factory Fixtures

All factory fixtures provide automatic cleanup:

```python
@pytest.fixture
def behavior_factory(authenticated_client: TestClient):
    factory = BehaviorFactory(authenticated_client)
    yield factory
    factory.cleanup()  # Automatic cleanup
```

Available factory fixtures:
- `behavior_factory`
- `topic_factory` 
- `category_factory`
- `metric_factory`
- `dimension_factory`
- `demographic_factory`
- `endpoint_factory`

## 👤 User Fixtures

Simplified user fixtures with clear naming and purpose.

### Mock User Fixtures (Unit Tests)

| Fixture | Purpose | Returns |
|---------|---------|---------|
| `mock_user_data` | Standard user data | `Dict[str, Any]` |
| `mock_admin_data` | Admin user data | `Dict[str, Any]` |
| `mock_inactive_user_data` | Inactive user data | `Dict[str, Any]` |
| `mock_user_object` | Mock User model | `Mock` object |

### Database User Fixtures (Integration Tests)

| Fixture | Purpose | Returns |
|---------|---------|---------|
| `db_user` | Regular user in DB | `User` model |
| `db_admin` | Admin user in DB | `User` model |
| `db_inactive_user` | Inactive user in DB | `User` model |
| `db_owner_user` | User for owner relationships | `User` model |
| `db_assignee_user` | User for assignee relationships | `User` model |

### Authenticated User Fixtures

| Fixture | Purpose | Returns |
|---------|---------|---------|
| `authenticated_user` | The real authenticated user | `User` model |
| `authenticated_user_data` | Auth user as dict | `Dict[str, Any]` |
| `test_organization` | Test organization | `Organization` model |

### Convenience User Fixtures

```python
def test_user_relationships(user_trio):
    # Get three different users
    regular_user = user_trio["user"]
    owner_user = user_trio["owner"] 
    assignee_user = user_trio["assignee"]

def test_permissions(admin_and_user):
    admin = admin_and_user["admin"]
    user = admin_and_user["user"]
    # Test admin vs user permissions
```

## 🔗 Composite Fixtures

Composite fixtures create complex entity relationships with automatic cleanup.

### `behavior_with_metrics`
```python
def test_behavior_metrics(behavior_with_metrics):
    behavior = behavior_with_metrics["behavior"]
    metrics = behavior_with_metrics["metrics"]
    
    assert behavior["id"] is not None
    assert len(metrics) == 2
    # Relationship already established
```

### `topic_hierarchy`
```python
def test_topic_relationships(topic_hierarchy):
    parent = topic_hierarchy["parent"]
    children = topic_hierarchy["children"]
    
    assert parent["id"] is not None
    assert len(children) == 3
    # Parent-child relationships already set up
```

### `entity_relationships`
```python
def test_complex_relationships(entity_relationships):
    behaviors = entity_relationships["behaviors"]
    metrics = entity_relationships["metrics"]
    topics = entity_relationships["topics"]
    relationships = entity_relationships["relationships"]
    
    # Complex multi-entity relationships pre-configured
```

## ⚡ Performance Fixtures

For testing with large datasets and performance scenarios.

### `large_entity_batch`
```python
@pytest.mark.slow
def test_bulk_operations(large_entity_batch):
    # 20 pre-created entities for performance testing
    assert len(large_entity_batch) == 20
```

### `performance_test_data`
```python
@pytest.mark.slow
def test_performance_scenarios(performance_test_data):
    small_batch = performance_test_data["small_batch"]    # 10 items
    medium_batch = performance_test_data["medium_batch"]  # 50 items
    large_batch = performance_test_data["large_batch"]    # 100 items
    edge_cases = performance_test_data["edge_cases"]      # Various edge cases
```

## 🎯 Best Practices

### 1. Choose the Right Fixture Type

```python
# ✅ Unit tests: Use mock fixtures
def test_validation_logic(mock_user_data):
    result = validate_user(mock_user_data)
    assert result.is_valid

# ✅ Integration tests: Use factory fixtures  
def test_api_endpoint(behavior_factory):
    behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
    # Test with real database entity

# ✅ Relationship tests: Use composite fixtures
def test_complex_workflow(behavior_with_metrics):
    # Pre-configured relationships
```

### 2. Use Appropriate Data Types

```python
# ✅ Standard testing
data = BehaviorDataFactory.sample_data()

# ✅ Minimal testing (performance)
data = BehaviorDataFactory.minimal_data()

# ✅ Edge case testing
data = BehaviorDataFactory.edge_case_data("long_name")

# ✅ Batch testing
batch = BehaviorDataFactory.batch_data(count=10)
```

### 3. Leverage Automatic Cleanup

```python
def test_entity_operations(behavior_factory, topic_factory):
    # Create multiple entities
    behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
    topic = topic_factory.create(TopicDataFactory.sample_data())
    
    # Test operations
    # ...
    
    # NO manual cleanup needed - automatic via fixtures!
```

### 4. Use Parameterized Fixtures for Coverage

```python
def test_entity_creation(varied_behavior_data):
    # This test runs with multiple data variations automatically
    assert "name" in varied_behavior_data
    
def test_edge_cases(edge_case_behavior_data):
    # This test runs with multiple edge cases automatically
    # Handles long_name, special_chars, unicode, etc.
```

### 5. Combine Fixtures Effectively

```python
def test_user_entity_relationships(db_owner_user, behavior_factory):
    # Create behavior owned by specific user
    behavior_data = BehaviorDataFactory.sample_data()
    behavior_data["owner_id"] = str(db_owner_user.id)
    
    behavior = behavior_factory.create(behavior_data)
    assert behavior["owner_id"] == str(db_owner_user.id)
```

## 🚨 Common Pitfalls

### ❌ Don't Mix Fixture Types
```python
# BAD: Mixing mock and real data
def test_something(mock_user_data, db_user):
    # Confusing - which user should I use?
```

### ❌ Don't Forget Cleanup in Custom Fixtures
```python
# BAD: Custom fixture without cleanup
@pytest.fixture
def my_custom_entities(authenticated_client):
    entities = []
    for i in range(5):
        response = authenticated_client.post("/entities/", json={"name": f"Entity {i}"})
        entities.append(response.json())
    return entities
    # NO CLEANUP - entities remain in database!
```

### ❌ Don't Use Factory Fixtures for Unit Tests
```python
# BAD: Using database fixtures for unit tests
def test_validation_logic(behavior_factory):  # Too heavy for unit test
    # This creates real database entities for a simple validation test
```

### ✅ Do Use Appropriate Fixtures
```python
# GOOD: Use mock data for unit tests
def test_validation_logic(mock_behavior_data):
    result = validate_behavior(mock_behavior_data)
    assert result.is_valid

# GOOD: Use factory for integration tests
def test_api_behavior(behavior_factory):
    behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
    # Test with real entity
```

## 📚 Reference

### Quick Fixture Reference

| Need | Fixture | Example |
|------|---------|---------|
| Mock user data | `mock_user_data` | Unit tests |
| Real user in DB | `db_user` | Integration tests |
| Auth user | `authenticated_user` | Auth-specific tests |
| Create behaviors | `behavior_factory` | Entity testing |
| Behavior data | `behavior_data` | Data validation |
| Edge case data | `edge_case_behavior_data` | Boundary testing |
| Multiple entities | `large_entity_batch` | Performance tests |
| Relationships | `behavior_with_metrics` | Relationship tests |

### Import Cheat Sheet

```python
# Data factories
from .fixtures.data_factories import (
    BehaviorDataFactory,
    TopicDataFactory,
    CategoryDataFactory,
    MetricDataFactory
)

# Entity factories
from .fixtures.factories import EntityFactory, BehaviorFactory

# All fixtures are automatically available via conftest.py
# Just use them as parameters in your test functions!
```



## 🎉 Benefits Summary

1. **🧹 Automatic Cleanup**: No more test pollution
2. **⚡ Better Performance**: Optimized fixture scoping
3. **📝 Clear Intent**: Purpose-driven fixture names
4. **🔄 Consistency**: Unified data generation patterns
5. **🛠️ Maintainability**: Easy to add new entities
6. **🎭 Flexibility**: Mock vs real data as needed
7. **🏗️ DRY Compliance**: Maintains your excellent base class system

The new fixture system enhances your already excellent DRY testing framework with powerful data management and cleanup capabilities!
