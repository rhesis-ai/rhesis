"""
🧪 Metric Test Fixtures

Pytest fixtures for metrics testing. These provide consistent test data
for baseline regression tests.
"""

from typing import Any, Dict, List

import pytest

from .metric_factories import (
    MetricConfigFactory,
    RagasMetricConfigFactory,
)


@pytest.fixture
def numeric_metric_config() -> Dict[str, Any]:
    """Fixture for numeric metric configuration."""
    return MetricConfigFactory.numeric_config()


@pytest.fixture
def categorical_metric_config() -> Dict[str, Any]:
    """Fixture for categorical metric configuration."""
    return MetricConfigFactory.categorical_config()


@pytest.fixture
def binary_metric_config() -> Dict[str, Any]:
    """
    DEPRECATED: Fixture for binary metric configuration.
    Binary metrics have been migrated to categorical.
    This now returns a categorical metric configuration.
    """
    return MetricConfigFactory.binary_config()


@pytest.fixture
def rhesis_metric_with_model(test_model) -> Dict[str, Any]:
    """Fixture for metric configuration with custom model."""
    return MetricConfigFactory.with_model(model_id=str(test_model.id))


@pytest.fixture
def ragas_metric_config() -> Dict[str, Any]:
    """Fixture for Ragas metric configuration."""
    return RagasMetricConfigFactory.answer_relevancy()


@pytest.fixture
def metric_configs_batch() -> List[Dict[str, Any]]:
    """Fixture for batch of metric configurations."""
    return MetricConfigFactory.batch_configs(count=5, variation=True)


@pytest.fixture
def mock_llm_response() -> Dict[str, Any]:
    """Mock LLM response for testing metric evaluation."""
    return {
        "score": 8,
        "reason": "Response demonstrates good quality with clear explanation",
        "verdict": "pass"
    }


@pytest.fixture
def mock_llm_categorical_response() -> Dict[str, Any]:
    """Mock LLM response for categorical metric."""
    return {
        "score": "positive",
        "reason": "Response has a positive sentiment",
        "verdict": "pass"
    }


@pytest.fixture
def mock_llm_binary_response() -> Dict[str, Any]:
    """
    DEPRECATED: Mock LLM response for binary metric.
    Binary metrics have been migrated to categorical.
    This now returns a categorical response.
    """
    return {
        "score": "Pass",
        "reason": "Response meets the criteria",
        "verdict": "pass"
    }


@pytest.fixture
def test_model(test_db, test_org_id, authenticated_user_id):
    """Create a test Model for metrics testing."""
    from rhesis.backend.app import models
    
    model = models.Model(
        name="Test Model for Metrics",
        model_name="gpt-4",
        endpoint="https://api.openai.com/v1/chat/completions",
        key="test-key-123",
        organization_id=test_org_id,
        user_id=authenticated_user_id
    )
    test_db.add(model)
    test_db.commit()
    test_db.refresh(model)
    return model


@pytest.fixture
def test_metric_numeric(test_db, test_org_id, authenticated_user_id):
    """Create a numeric Metric DB model for testing."""
    from rhesis.backend.app import models
    from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
    
    # Get or create backend type
    backend_type = get_or_create_type_lookup(
        test_db,
        type_name="backend_type",
        type_value="rhesis",
        organization_id=test_org_id,
        user_id=authenticated_user_id
    )
    
    # Get or create metric type
    metric_type = get_or_create_type_lookup(
        test_db,
        type_name="metric_type",
        type_value="custom-prompt",
        organization_id=test_org_id,
        user_id=authenticated_user_id
    )
    
    metric = models.Metric(
        name="Test Numeric Metric",
        description="Test metric for baseline tests",
        class_name="RhesisPromptMetric",
        score_type="numeric",
        evaluation_prompt="Rate the quality from 0 to 10",
        evaluation_steps="1. Check accuracy\n2. Rate quality",
        reasoning="Quality assessment",
        min_score=0,
        max_score=10,
        threshold=7,
        threshold_operator=">=",
        backend_type_id=backend_type.id,
        metric_type_id=metric_type.id,
        organization_id=test_org_id,
        user_id=authenticated_user_id
    )
    test_db.add(metric)
    test_db.commit()
    test_db.refresh(metric)
    return metric


@pytest.fixture
def test_metric_categorical(test_db, test_org_id, authenticated_user_id):
    """Create a categorical Metric DB model for testing."""
    from rhesis.backend.app import models
    from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
    
    # Get or create backend type
    backend_type = get_or_create_type_lookup(
        test_db,
        type_name="backend_type",
        type_value="rhesis",
        organization_id=test_org_id,
        user_id=authenticated_user_id
    )
    
    # Get or create metric type
    metric_type = get_or_create_type_lookup(
        test_db,
        type_name="metric_type",
        type_value="custom-prompt",
        organization_id=test_org_id,
        user_id=authenticated_user_id
    )
    
    metric = models.Metric(
        name="Test Categorical Metric",
        description="Test categorical metric",
        class_name="RhesisPromptMetric",
        score_type="categorical",
        evaluation_prompt="Classify the sentiment",
        evaluation_steps="1. Read response\n2. Classify",
        reasoning="Sentiment classification",
        reference_score="positive",
        backend_type_id=backend_type.id,
        metric_type_id=metric_type.id,
        organization_id=test_org_id,
        user_id=authenticated_user_id
    )
    test_db.add(metric)
    test_db.commit()
    test_db.refresh(metric)
    return metric


@pytest.fixture
def test_behavior_with_metrics(test_db, test_org_id, authenticated_user_id, test_metric_numeric, test_metric_categorical):
    """Create a behavior with associated metrics for testing."""
    from rhesis.backend.app import models
    
    behavior = models.Behavior(
        name="Test Behavior with Metrics",
        description="Behavior for baseline metrics tests",
        organization_id=test_org_id,
        user_id=authenticated_user_id
    )
    test_db.add(behavior)
    test_db.flush()
    
    # Associate metrics with behavior
    behavior.metrics = [test_metric_numeric, test_metric_categorical]
    
    test_db.commit()
    test_db.refresh(behavior)
    return behavior

