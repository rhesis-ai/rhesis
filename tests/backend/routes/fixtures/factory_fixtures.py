"""
Factory Fixture Integration

This module provides pytest fixtures that integrate the factory system
with the test framework, providing automatic cleanup and easy access.

Usage:
    def test_requirement_creation(requirement_factory):
        requirement = requirement_factory.create(RequirementDataFactory.sample_data())
        # Automatic cleanup after test

    def test_multiple_requirements(requirement_factory):
        requirements = requirement_factory.create_batch([
            RequirementDataFactory.sample_data(),
            RequirementDataFactory.minimal_data()
        ])
        # All cleaned up automatically
"""

from typing import Generator

import pytest
from fastapi.testclient import TestClient

from ..endpoints import APIEndpoints
from .data_factories import (
    RequirementDataFactory,
    CategoryDataFactory,
    MetricDataFactory,
    ModelDataFactory,
    ProjectDataFactory,
    PromptDataFactory,
    TopicDataFactory,
)
from .factories import (
    RequirementFactory,
    EntityFactory,
    TopicFactory,
    create_requirement_factory,
    create_generic_factory,
    create_topic_factory,
)

# === ENTITY FACTORY FIXTURES ===


@pytest.fixture
def requirement_factory(authenticated_client: TestClient) -> Generator[RequirementFactory, None, None]:
    """Requirement factory with automatic cleanup

    Provides a factory for creating requirement entities with automatic cleanup
    after the test completes.

    Usage:
        def test_requirement_creation(requirement_factory):
            requirement = requirement_factory.create(RequirementDataFactory.sample_data())
            assert requirement["name"] == "Expected Name"
    """
    factory = create_requirement_factory(authenticated_client)
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
def requirement_data():
    """Standard requirement test data"""
    return RequirementDataFactory.sample_data()


@pytest.fixture
def minimal_requirement_data():
    """Minimal requirement test data"""
    return RequirementDataFactory.minimal_data()


@pytest.fixture
def requirement_update_data():
    """Requirement update test data"""
    return RequirementDataFactory.update_data()


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
def long_name_requirement_data():
    """Requirement data with long name for edge testing"""
    return RequirementDataFactory.edge_case_data("long_name")


@pytest.fixture
def special_chars_requirement_data():
    """Requirement data with special characters"""
    return RequirementDataFactory.edge_case_data("special_chars")


@pytest.fixture
def unicode_requirement_data():
    """Requirement data with unicode characters"""
    return RequirementDataFactory.edge_case_data("unicode")


@pytest.fixture
def sql_injection_requirement_data():
    """Requirement data with SQL injection attempt"""
    return RequirementDataFactory.edge_case_data("sql_injection")


@pytest.fixture
def empty_requirement_data():
    """Invalid empty requirement data"""
    return RequirementDataFactory.invalid_data()


# === BATCH DATA FIXTURES ===


@pytest.fixture
def requirement_batch_data():
    """Batch of requirement test data"""
    return RequirementDataFactory.batch_data(count=5, variation=True)


@pytest.fixture
def small_requirement_batch():
    """Small batch of requirement test data"""
    return RequirementDataFactory.batch_data(count=2, variation=False)


# === COMPOSITE FIXTURES (MULTIPLE ENTITIES) ===


@pytest.fixture
def requirement_with_metrics(requirement_factory, metric_factory):
    """Requirement with associated metrics

    Creates a requirement and metrics for relationship testing.
    Note: This creates separate entities but doesn't establish backend associations
    since the association endpoints may not be implemented yet.

    Returns:
        Dict with 'requirement' and 'metrics' keys
    """
    # Create metrics first
    metrics = metric_factory.create_batch(
        [MetricDataFactory.sample_data(), MetricDataFactory.sample_data()]
    )

    # Create requirement separately (no association for now)
    requirement = requirement_factory.create(RequirementDataFactory.sample_data())

    return {"requirement": requirement, "metrics": metrics}


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
def large_entity_batch(requirement_factory):
    """Large batch of entities for performance testing

    Creates 20 requirements for testing bulk operations and performance.
    Use with @pytest.mark.slow marker.
    """
    batch_data = RequirementDataFactory.batch_data(count=20, variation=True)
    return requirement_factory.create_batch(batch_data)


# === PARAMETERIZED FIXTURES ===


@pytest.fixture(params=["minimal", "sample", "with_description"])
def varied_requirement_data(request):
    """Parameterized requirement data for testing multiple scenarios

    This fixture will run tests with different data variations:
    - minimal: Only required fields
    - sample: Standard sample data
    - with_description: Explicitly includes description
    """
    if request.param == "minimal":
        return RequirementDataFactory.minimal_data()
    elif request.param == "sample":
        return RequirementDataFactory.sample_data()
    elif request.param == "with_description":
        return RequirementDataFactory.sample_data(include_description=True)


@pytest.fixture(params=["long_name", "special_chars", "unicode"])
def edge_case_requirement_data(request):
    """Parameterized edge case requirement data"""
    return RequirementDataFactory.edge_case_data(request.param)


# Export fixture names for documentation
__all__ = [
    # Factory fixtures
    "requirement_factory",
    "topic_factory",
    "category_factory",
    "comment_factory",
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
    # Composite fixtures
    "requirement_with_metrics",
    "topic_hierarchy",
    # Performance fixtures
    "large_entity_batch",
    # Parameterized fixtures
    "varied_requirement_data",
    "edge_case_requirement_data",
]
