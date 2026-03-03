"""Tests for MetricRegistry."""

import pytest

from rhesis.sdk.connector.registry import MetricRegistry


@pytest.fixture
def registry():
    """Create a metric registry for testing."""
    return MetricRegistry()


@pytest.fixture
def sample_metric():
    """Sample metric function."""

    def my_metric(input: str, output: str) -> dict:
        return {"score": 0.9}

    return my_metric


def test_registry_initialization(registry):
    """Test registry initializes with empty storage."""
    assert registry.count() == 0
    assert registry.get_all_metadata() == []


def test_register_metric(registry, sample_metric):
    """Test registering a metric."""
    metadata = {
        "score_type": "numeric",
        "description": "test metric",
        "accepted_params": ["input", "output"],
    }

    registry.register("my_metric", sample_metric, metadata)

    assert registry.count() == 1
    assert registry.has("my_metric")
    assert registry.get("my_metric") == sample_metric


def test_register_multiple_metrics(registry, sample_metric):
    """Test registering multiple metrics."""

    def another_metric(input: str, output: str, context: list) -> dict:
        return {"score": 1.0}

    registry.register(
        "metric1",
        sample_metric,
        {"accepted_params": ["input", "output"]},
    )
    registry.register(
        "metric2",
        another_metric,
        {"accepted_params": ["input", "output", "context"]},
    )

    assert registry.count() == 2
    assert registry.has("metric1")
    assert registry.has("metric2")


def test_get_nonexistent_metric(registry):
    """Test getting a metric that doesn't exist."""
    assert registry.get("nonexistent") is None


def test_has_metric(registry, sample_metric):
    """Test checking if metric exists."""
    assert not registry.has("my_metric")

    registry.register(
        "my_metric",
        sample_metric,
        {"accepted_params": ["input", "output"]},
    )

    assert registry.has("my_metric")


def test_get_metadata(registry, sample_metric):
    """Test getting metadata for a specific metric."""
    metadata = {
        "score_type": "numeric",
        "description": "test",
        "accepted_params": ["input", "output"],
    }

    registry.register("my_metric", sample_metric, metadata)

    result = registry.get_metadata("my_metric")
    assert result is not None
    assert result["score_type"] == "numeric"
    assert result["accepted_params"] == ["input", "output"]


def test_get_metadata_nonexistent(registry):
    """Test getting metadata for nonexistent metric."""
    assert registry.get_metadata("nonexistent") is None


def test_get_all_metadata(registry, sample_metric):
    """Test getting all metric metadata as MetricMetadata list."""

    def context_metric(input: str, output: str, context: list) -> dict:
        return {"score": 1.0}

    registry.register(
        "metric1",
        sample_metric,
        {"accepted_params": ["input", "output"], "score_type": "numeric"},
    )
    registry.register(
        "metric2",
        context_metric,
        {
            "accepted_params": ["input", "output", "context"],
            "score_type": "binary",
        },
    )

    metadata_list = registry.get_all_metadata()

    assert len(metadata_list) == 2
    names = {m.name for m in metadata_list}
    assert names == {"metric1", "metric2"}

    for m in metadata_list:
        assert m.return_type == "MetricResult"
        assert hasattr(m, "parameters")
        assert hasattr(m, "metadata")


def test_get_all_metadata_parameters(registry, sample_metric):
    """Test that MetricMetadata.parameters matches accepted_params."""
    registry.register(
        "my_metric",
        sample_metric,
        {"accepted_params": ["input", "output"]},
    )

    metadata_list = registry.get_all_metadata()
    assert len(metadata_list) == 1
    assert metadata_list[0].parameters == ["input", "output"]


def test_get_all_metadata_excludes_accepted_params_from_metadata_dict(registry, sample_metric):
    """Test that accepted_params is not leaked into the metadata dict."""
    registry.register(
        "my_metric",
        sample_metric,
        {
            "accepted_params": ["input", "output"],
            "score_type": "numeric",
        },
    )

    metadata_list = registry.get_all_metadata()
    assert "accepted_params" not in metadata_list[0].metadata
    assert metadata_list[0].metadata["score_type"] == "numeric"


def test_register_overwrites_existing(registry, sample_metric):
    """Test that registering with same name overwrites."""

    def new_metric(input: str, output: str) -> dict:
        return {"score": 0.5}

    registry.register(
        "metric",
        sample_metric,
        {"accepted_params": ["input", "output"], "version": "1"},
    )
    registry.register(
        "metric",
        new_metric,
        {"accepted_params": ["input", "output"], "version": "2"},
    )

    assert registry.count() == 1
    assert registry.get("metric") == new_metric
    assert registry.get_metadata("metric")["version"] == "2"


def test_default_parameters_when_missing(registry, sample_metric):
    """Test that defaults are used when accepted_params is missing."""
    registry.register("my_metric", sample_metric, {})

    metadata_list = registry.get_all_metadata()
    assert set(metadata_list[0].parameters) == {"input", "output"}
