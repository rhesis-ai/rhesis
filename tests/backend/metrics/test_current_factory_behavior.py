"""
Test current MetricFactory behavior (baseline regression tests).

These tests validate the factory pattern used in the backend metrics infrastructure
and will serve as regression guards during the migration to SDK metrics.
"""

import pytest
from rhesis.backend.metrics import (
    MetricFactory,
    RhesisMetricFactory,
    RagasMetricFactory,
    RhesisPromptMetric,
    RagasAnswerRelevancy,
)
from rhesis.backend.metrics.constants import ThresholdOperator
from rhesis.backend.metrics.constants import ScoreType


class TestCurrentFactoryBehavior:
    """Test current MetricFactory behavior (baseline)."""
    
    def test_metric_factory_get_factory_rhesis(self):
        """Test getting rhesis factory."""
        factory = MetricFactory()
        rhesis_factory = factory.get_factory("rhesis")
        
        assert rhesis_factory is not None
        assert isinstance(rhesis_factory, RhesisMetricFactory)
    
    def test_metric_factory_get_factory_ragas(self):
        """Test getting ragas factory."""
        factory = MetricFactory()
        ragas_factory = factory.get_factory("ragas")
        
        assert ragas_factory is not None
        assert isinstance(ragas_factory, RagasMetricFactory)
    
    def test_metric_factory_create_rhesis_prompt_metric(self):
        """Test factory.create() with rhesis backend."""
        factory = MetricFactory()
        rhesis_factory = factory.get_factory("rhesis")
        
        metric = rhesis_factory.create(
            "RhesisPromptMetric",
            name="test",
            evaluation_prompt="Test",
            evaluation_steps="Steps",
            reasoning="Reason",
            score_type="numeric",
            min_score=0,
            max_score=10
        )
        
        assert metric is not None
        assert metric.name == "test"
        assert isinstance(metric, RhesisPromptMetric)
        assert metric.score_type == ScoreType.NUMERIC
    
    def test_metric_factory_static_create_method(self):
        """Test MetricFactory.create() static method."""
        metric = MetricFactory.create(
            framework="rhesis",
            class_name="RhesisPromptMetric",
            name="test",
            evaluation_prompt="Test",
            evaluation_steps="Steps",
            reasoning="Reason",
            score_type="numeric",
            min_score=0,
            max_score=10
        )
        
        assert metric is not None
        assert metric.name == "test"
        assert isinstance(metric, RhesisPromptMetric)
    
    def test_list_supported_frameworks(self):
        """Test listing supported frameworks."""
        frameworks = MetricFactory.list_supported_frameworks()
        
        assert isinstance(frameworks, list)
        assert "rhesis" in frameworks
        assert "ragas" in frameworks
    
    def test_factory_handles_missing_params(self):
        """Test factory error handling for missing required params."""
        factory = MetricFactory()
        rhesis_factory = factory.get_factory("rhesis")
        
        with pytest.raises((ValueError, TypeError)):
            # Missing required parameters should raise error
            rhesis_factory.create("RhesisPromptMetric", name="test")
    
    def test_factory_handles_unknown_class(self):
        """Test factory error handling for unknown class name."""
        factory = MetricFactory()
        rhesis_factory = factory.get_factory("rhesis")
        
        with pytest.raises(ValueError):
            # Unknown class name should raise ValueError
            rhesis_factory.create("NonExistentMetric", name="test")
    
    def test_factory_handles_unknown_framework(self):
        """Test factory error handling for unknown framework."""
        factory = MetricFactory()
        
        with pytest.raises(ValueError):
            # Unknown framework should raise ValueError
            factory.get_factory("unknown_framework")
    
    def test_rhesis_factory_create_categorical_metric(self):
        """Test creating categorical metric through factory."""
        factory = RhesisMetricFactory()
        metric = factory.create(
            "RhesisPromptMetric",
            name="sentiment",
            evaluation_prompt="Classify sentiment",
            evaluation_steps="Steps",
            reasoning="Reason",
            score_type="categorical",
            reference_score="positive"
        )
        
        assert metric is not None
        assert metric.score_type == ScoreType.CATEGORICAL
        assert metric.reference_score == "positive"
    
    def test_ragas_factory_create_answer_relevancy(self):
        """Test creating Ragas metric through factory."""
        factory = RagasMetricFactory()
        metric = factory.create("RagasAnswerRelevancy", threshold=0.7)
        
        assert metric is not None
        assert isinstance(metric, RagasAnswerRelevancy)
        assert metric.threshold == 0.7
    
    def test_factory_create_with_all_optional_parameters(self):
        """Test factory.create() with all optional parameters."""
        metric = MetricFactory.create(
            framework="rhesis",
            class_name="RhesisPromptMetric",
            name="comprehensive",
            evaluation_prompt="Evaluate",
            evaluation_steps="Steps",
            reasoning="Reason",
            score_type="numeric",
            min_score=0,
            max_score=100,
            threshold=70,
            threshold_operator=">=",
            ground_truth_required=True,
            context_required=True,
            evaluation_examples="Examples",
            explanation="Explanation"
        )
        
        assert metric is not None
        # Threshold is normalized: (70-0)/(100-0) = 0.7
        assert metric.threshold == 0.7
        assert metric.raw_threshold == 70
        # RhesisPromptMetric has requires_ground_truth property
        assert metric.requires_ground_truth is True
    
    def test_factory_preserves_metric_configuration(self):
        """Test that factory preserves all metric configuration."""
        config = {
            "name": "test_metric",
            "evaluation_prompt": "Test prompt",
            "evaluation_steps": "Step 1\nStep 2",
            "reasoning": "Test reasoning",
            "score_type": "numeric",
            "min_score": 1,
            "max_score": 5,
            "threshold": 3,
            "threshold_operator": ">",
        }
        
        metric = MetricFactory.create(
            framework="rhesis",
            class_name="RhesisPromptMetric",
            **config
        )
        
        assert metric.name == config["name"]
        assert metric.evaluation_prompt == config["evaluation_prompt"]
        assert metric.evaluation_steps == config["evaluation_steps"]
        assert metric.reasoning == config["reasoning"]
        assert metric.min_score == config["min_score"]
        assert metric.max_score == config["max_score"]
        # Threshold is normalized: (3-1)/(5-1) = 0.5
        assert metric.threshold == 0.5
        assert metric.raw_threshold == 3
        assert metric.threshold_operator == ThresholdOperator.GREATER_THAN

