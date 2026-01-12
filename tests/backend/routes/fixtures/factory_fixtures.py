"""
Factory Fixture Integration

This module provides pytest fixtures that integrate the factory system
with the test framework, providing automatic cleanup and easy access.

Usage:
    def test_behavior_creation(behavior_factory):
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
        # Automatic cleanup after test

    def test_multiple_behaviors(behavior_factory):
        behaviors = behavior_factory.create_batch([
            BehaviorDataFactory.sample_data(),
            BehaviorDataFactory.minimal_data()
        ])
        # All cleaned up automatically
"""

from typing import Generator

import pytest
from fastapi.testclient import TestClient

from ..endpoints import APIEndpoints
from .data_factories import (
    BehaviorDataFactory,
    CategoryDataFactory,
    DimensionDataFactory,
    MetricDataFactory,
    ModelDataFactory,
    ProjectDataFactory,
    PromptDataFactory,
    TopicDataFactory,
)
from .factories import (
    BehaviorFactory,
    EntityFactory,
    TopicFactory,
    create_behavior_factory,
    create_generic_factory,
    create_topic_factory,
)

# === ENTITY FACTORY FIXTURES ===


@pytest.fixture
def behavior_factory(authenticated_client: TestClient) -> Generator[BehaviorFactory, None, None]:
    """Behavior factory with automatic cleanup

    Provides a factory for creating behavior entities with automatic cleanup
    after the test completes.

    Usage:
        def test_behavior_creation(behavior_factory):
            behavior = behavior_factory.create(BehaviorDataFactory.sample_data())
            assert behavior["name"] == "Expected Name"
    """
    factory = create_behavior_factory(authenticated_client)
    yield factory
    factory.cleanup()


@pytest.fixture
def topic_factory(authenticated_client: TestClient) -> Generator[TopicFactory, None, None]:
    """Topic factory with automatic cleanup

    Provides a factory for creating topic entities with automatic cleanup.
    Supports hierarchical topic creation.

    Usage:
        def test_topic_hierarchy(topic_factory):
            result = topic_factory.create_hierarchy(
                parent_data=TopicDataFactory.sample_data(),
                children_data=[TopicDataFactory.sample_data() for _ in range(3)]
            )
    """
    factory = create_topic_factory(authenticated_client)
    yield factory
    factory.cleanup()


@pytest.fixture
def category_factory(authenticated_client: TestClient) -> Generator[EntityFactory, None, None]:
    """Category factory with automatic cleanup"""
    factory = create_generic_factory(authenticated_client, APIEndpoints.CATEGORIES)
    yield factory
    factory.cleanup()


@pytest.fixture
def comment_factory(authenticated_client: TestClient) -> Generator[EntityFactory, None, None]:
    """Comment factory with automatic cleanup"""
    factory = create_generic_factory(authenticated_client, APIEndpoints.COMMENTS)
    yield factory
    factory.cleanup()


@pytest.fixture
def metric_factory(authenticated_client: TestClient) -> Generator[EntityFactory, None, None]:
    """Metric factory with automatic cleanup"""
    factory = create_generic_factory(authenticated_client, APIEndpoints.METRICS)
    yield factory
    factory.cleanup()


@pytest.fixture
def dimension_factory(authenticated_client: TestClient) -> Generator[EntityFactory, None, None]:
    """Dimension factory with automatic cleanup"""
    factory = create_generic_factory(authenticated_client, APIEndpoints.DIMENSIONS)
    yield factory
    factory.cleanup()


@pytest.fixture
def demographic_factory(authenticated_client: TestClient) -> Generator[EntityFactory, None, None]:
    """👥 Demographic factory with automatic cleanup"""
    factory = create_generic_factory(authenticated_client, APIEndpoints.DEMOGRAPHICS)
    yield factory
    factory.cleanup()


@pytest.fixture
def endpoint_factory(authenticated_client: TestClient) -> Generator[EntityFactory, None, None]:
    """Endpoint factory with automatic cleanup"""
    factory = create_generic_factory(authenticated_client, APIEndpoints.ENDPOINTS)
    yield factory
    factory.cleanup()


@pytest.fixture
def model_factory(authenticated_client: TestClient) -> Generator[EntityFactory, None, None]:
    """🤖 Model factory with automatic cleanup"""
    factory = create_generic_factory(authenticated_client, APIEndpoints.MODELS)
    yield factory
    factory.cleanup()


@pytest.fixture
def project_factory(authenticated_client: TestClient) -> Generator[EntityFactory, None, None]:
    """Project factory with automatic cleanup"""
    factory = create_generic_factory(authenticated_client, APIEndpoints.PROJECTS)
    yield factory
    factory.cleanup()


@pytest.fixture
def prompt_factory(authenticated_client: TestClient) -> Generator[EntityFactory, None, None]:
    """🤖 Prompt factory with automatic cleanup"""
    factory = create_generic_factory(authenticated_client, APIEndpoints.PROMPTS)
    yield factory
    factory.cleanup()


# === DATA FIXTURES (NO CLEANUP NEEDED) ===


@pytest.fixture
def behavior_data():
    """Standard behavior test data"""
    return BehaviorDataFactory.sample_data()


@pytest.fixture
def minimal_behavior_data():
    """Minimal behavior test data"""
    return BehaviorDataFactory.minimal_data()


@pytest.fixture
def behavior_update_data():
    """Behavior update test data"""
    return BehaviorDataFactory.update_data()


@pytest.fixture
def topic_data():
    """Standard topic test data"""
    return TopicDataFactory.sample_data()


@pytest.fixture
def minimal_topic_data():
    """Minimal topic test data"""
    return TopicDataFactory.minimal_data()


@pytest.fixture
def topic_update_data():
    """Topic update test data"""
    return TopicDataFactory.update_data()


@pytest.fixture
def category_data():
    """Standard category test data"""
    return CategoryDataFactory.sample_data()


@pytest.fixture
def metric_data():
    """Standard metric test data"""
    return MetricDataFactory.sample_data()


@pytest.fixture
def dimension_data():
    """Standard dimension test data"""
    return DimensionDataFactory.sample_data()


@pytest.fixture
def project_data():
    """Sample project data"""
    return ProjectDataFactory.sample_data()


@pytest.fixture
def minimal_project_data():
    """Minimal project data"""
    return ProjectDataFactory.minimal_data()


@pytest.fixture
def project_update_data():
    """Project update data"""
    return ProjectDataFactory.update_data()


@pytest.fixture
def prompt_data():
    """🤖 Sample prompt data"""
    return PromptDataFactory.sample_data()


@pytest.fixture
def minimal_prompt_data():
    """🤖 Minimal prompt data"""
    return PromptDataFactory.minimal_data()


@pytest.fixture
def prompt_update_data():
    """🤖 Prompt update data"""
    return PromptDataFactory.update_data()


@pytest.fixture
def model_data():
    """🤖 Standard model test data"""
    return ModelDataFactory.sample_data()


# === EDGE CASE DATA FIXTURES ===


@pytest.fixture
def long_name_behavior_data():
    """Behavior data with long name for edge testing"""
    return BehaviorDataFactory.edge_case_data("long_name")


@pytest.fixture
def special_chars_behavior_data():
    """Behavior data with special characters"""
    return BehaviorDataFactory.edge_case_data("special_chars")


@pytest.fixture
def unicode_behavior_data():
    """Behavior data with unicode characters"""
    return BehaviorDataFactory.edge_case_data("unicode")


@pytest.fixture
def sql_injection_behavior_data():
    """Behavior data with SQL injection attempt"""
    return BehaviorDataFactory.edge_case_data("sql_injection")


@pytest.fixture
def empty_behavior_data():
    """Invalid empty behavior data"""
    return BehaviorDataFactory.invalid_data()


# === BATCH DATA FIXTURES ===


@pytest.fixture
def behavior_batch_data():
    """Batch of behavior test data"""
    return BehaviorDataFactory.batch_data(count=5, variation=True)


@pytest.fixture
def small_behavior_batch():
    """Small batch of behavior test data"""
    return BehaviorDataFactory.batch_data(count=2, variation=False)


# === COMPOSITE FIXTURES (MULTIPLE ENTITIES) ===


@pytest.fixture
def behavior_with_metrics(behavior_factory, metric_factory):
    """Behavior with associated metrics

    Creates a behavior and metrics for relationship testing.
    Note: This creates separate entities but doesn't establish backend associations
    since the association endpoints may not be implemented yet.

    Returns:
        Dict with 'behavior' and 'metrics' keys
    """
    # Create metrics first
    metrics = metric_factory.create_batch(
        [MetricDataFactory.sample_data(), MetricDataFactory.sample_data()]
    )

    # Create behavior separately (no association for now)
    behavior = behavior_factory.create(BehaviorDataFactory.sample_data())

    return {"behavior": behavior, "metrics": metrics}


@pytest.fixture
def topic_hierarchy(topic_factory):
    """Topic hierarchy for testing parent-child relationships

    Returns:
        Dict with 'parent' and 'children' keys
    """
    return topic_factory.create_hierarchy(
        parent_data=TopicDataFactory.sample_data(),
        children_data=[
            TopicDataFactory.sample_data(),
            TopicDataFactory.sample_data(),
            TopicDataFactory.sample_data(),
        ],
    )


# === PERFORMANCE FIXTURES ===


@pytest.fixture
def large_entity_batch(behavior_factory):
    """Large batch of entities for performance testing

    Creates 20 behaviors for testing bulk operations and performance.
    Use with @pytest.mark.slow marker.
    """
    batch_data = BehaviorDataFactory.batch_data(count=20, variation=True)
    return behavior_factory.create_batch(batch_data)


# === PARAMETERIZED FIXTURES ===


@pytest.fixture(params=["minimal", "sample", "with_description"])
def varied_behavior_data(request):
    """Parameterized behavior data for testing multiple scenarios

    This fixture will run tests with different data variations:
    - minimal: Only required fields
    - sample: Standard sample data
    - with_description: Explicitly includes description
    """
    if request.param == "minimal":
        return BehaviorDataFactory.minimal_data()
    elif request.param == "sample":
        return BehaviorDataFactory.sample_data()
    elif request.param == "with_description":
        return BehaviorDataFactory.sample_data(include_description=True)


@pytest.fixture(params=["long_name", "special_chars", "unicode"])
def edge_case_behavior_data(request):
    """Parameterized edge case behavior data"""
    return BehaviorDataFactory.edge_case_data(request.param)


# Export fixture names for documentation
__all__ = [
    # Factory fixtures
    "behavior_factory",
    "topic_factory",
    "category_factory",
    "comment_factory",
    "metric_factory",
    "model_factory",
    "dimension_factory",
    "demographic_factory",
    "endpoint_factory",
    "project_factory",
    "prompt_factory",
    # Data fixtures
    "behavior_data",
    "minimal_behavior_data",
    "behavior_update_data",
    "topic_data",
    "minimal_topic_data",
    "topic_update_data",
    "category_data",
    "metric_data",
    "model_data",
    "dimension_data",
    "project_data",
    "minimal_project_data",
    "project_update_data",
    "prompt_data",
    "minimal_prompt_data",
    "prompt_update_data",
    # Edge case fixtures
    "long_name_behavior_data",
    "special_chars_behavior_data",
    "unicode_behavior_data",
    "sql_injection_behavior_data",
    "empty_behavior_data",
    # Batch fixtures
    "behavior_batch_data",
    "small_behavior_batch",
    # Composite fixtures
    "behavior_with_metrics",
    "topic_hierarchy",
    # Performance fixtures
    "large_entity_batch",
    # Parameterized fixtures
    "varied_behavior_data",
    "edge_case_behavior_data",
]
