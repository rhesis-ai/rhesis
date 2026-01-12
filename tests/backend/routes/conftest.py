"""
🧪 Enhanced Route Test Configuration

This conftest provides optimized fixture organization with factory-based
entity management, automatic cleanup, and performance optimizations.

Fixture Categories:
- 🏭 Factory Fixtures: Entity creation with automatic cleanup
- 📊 Data Fixtures: Consistent test data generation
- 👤 User Fixtures: Simplified user management
- 🔗 Composite Fixtures: Complex relationships
- ⚡ Performance Fixtures: Large datasets and optimization

Usage:
    All fixtures are automatically available to tests in the routes/ directory.
    Use factory fixtures for entity creation, data fixtures for test data.
"""


import pytest

# Import all fixtures from the enhanced fixtures package
try:
    from .fixtures import *
except AttributeError:
    # Fallback to direct imports if __all__ export fails
    pass

from .fixtures.data_factories import generate_test_data

# Explicit imports for all fixtures to ensure availability
# Import entity fixtures
from .fixtures.entities import *
from .fixtures.factory_fixtures import *

# === ENHANCED DATA FIXTURES ===


@pytest.fixture
def dynamic_test_data():
    """
    🎲 Dynamic test data generator

    Provides a function to generate test data for any entity type dynamically.

    Usage:
        def test_something(dynamic_test_data):
            behavior_data = dynamic_test_data("behavior", "sample")
            topic_data = dynamic_test_data("topic", "minimal")
    """

    def _generate(entity_type: str, data_type: str = "sample", **kwargs):
        return generate_test_data(entity_type, data_type, **kwargs)

    return _generate


@pytest.fixture
def batch_test_data():
    """
    📦 Batch test data generator

    Generates multiple test data records for bulk testing.

    Usage:
        def test_bulk_operations(batch_test_data):
            behaviors = batch_test_data("behavior", count=10)
    """

    def _generate_batch(entity_type: str, count: int = 5, **kwargs):
        from .fixtures.data_factories import get_factory

        factory = get_factory(entity_type)
        if hasattr(factory, "batch_data"):
            return factory.batch_data(count, **kwargs)
        else:
            # Fallback: generate individual records
            return [factory.sample_data() for _ in range(count)]

    return _generate_batch


# === AUTO-USE FIXTURES (Automatic Cleanup) ===


@pytest.fixture(autouse=True)
def test_isolation():
    """
    🏝️ Ensure test isolation and cleanup

    Automatically runs before and after each test to ensure proper isolation.
    """
    # Pre-test setup
    yield
    # Post-test cleanup handled by factory fixtures


@pytest.fixture(autouse=True)
def performance_monitoring():
    """
    📊 Monitor test performance

    Automatically tracks test execution time and warns about slow tests.
    """
    import time

    start_time = time.time()
    yield

    duration = time.time() - start_time
    if duration > 5.0:  # Warn about tests taking >5 seconds
        print(f"⚠️  Slow test detected: {duration:.2f}s (consider @pytest.mark.slow)")


# === PARAMETERIZED FIXTURES ===


@pytest.fixture(params=["behavior", "topic", "category", "metric", "dimension"])
def entity_type(request):
    """
    🎯 Parameterized entity type for testing multiple entities

    Runs tests against multiple entity types to ensure consistency.
    """
    return request.param


@pytest.fixture(params=["minimal", "sample", "with_optional"])
def data_variation(request):
    """
    📊 Parameterized data variation for comprehensive testing
    """
    return request.param


@pytest.fixture
def varied_entity_data(entity_type, data_variation, dynamic_test_data):
    """
    🎲 Combination fixture for parameterized entity and data testing

    This fixture combines entity_type and data_variation to create
    comprehensive test coverage across multiple entities and data types.
    """
    return dynamic_test_data(entity_type, data_variation)


# === DEBUGGING FIXTURES ===


@pytest.fixture
def test_debug_info(request):
    """
    🔍 Test debugging information

    Provides debugging context for test development and troubleshooting.
    """
    return {
        "test_name": request.node.name,
        "test_file": str(request.node.fspath),
        "markers": [m.name for m in request.node.iter_markers()],
        "fixtures_used": list(request.fixturenames),
    }


# === CONDITIONAL FIXTURES ===


@pytest.fixture
def skip_if_slow(request):
    """
    🐌 Skip slow tests unless explicitly requested

    Skips tests marked with @pytest.mark.slow unless --runslow is passed.
    """
    if hasattr(request.config, "getoption") and request.config.getoption(
        "--runslow", default=False
    ):
        return

    if request.node.get_closest_marker("slow"):
        pytest.skip("Slow test skipped (use --runslow to run)")


# This makes all fixtures automatically available to any test file
# in the routes/ directory without explicit imports
