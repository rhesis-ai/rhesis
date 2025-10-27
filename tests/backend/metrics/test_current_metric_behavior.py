"""
Test current RhesisPromptMetric behavior (baseline regression tests).

These tests validate the existing behavior of the backend metrics infrastructure
and will serve as regression guards during the migration to SDK metrics.
"""

import pytest
from rhesis.backend.metrics import RhesisPromptMetric, RhesisMetricFactory
from rhesis.backend.metrics import RagasAnswerRelevancy, RagasContextualPrecision
from rhesis.backend.metrics.constants import ScoreType, ThresholdOperator


class TestCurrentMetricBehavior:
    """Test current RhesisPromptMetric behavior (baseline)."""
    
    def test_rhesis_prompt_metric_numeric(self):
        """Test creating RhesisPromptMetric with numeric score_type."""
        metric = RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Rate quality",
            evaluation_steps="Check accuracy",
            reasoning="Quality matters",
            score_type="numeric",
            min_score=0,
            max_score=10,
            threshold=7
        )
        
        assert metric.name == "test_metric"
        assert metric.score_type == ScoreType.NUMERIC
        assert metric.min_score == 0
        assert metric.max_score == 10
        # Threshold is normalized: (7-0)/(10-0) = 0.7
        assert metric.threshold == 0.7
        assert metric.raw_threshold == 7
        assert metric.evaluation_prompt == "Rate quality"
        assert metric.evaluation_steps == "Check accuracy"
        assert metric.reasoning == "Quality matters"
    
    def test_rhesis_prompt_metric_categorical(self):
        """Test creating RhesisPromptMetric with categorical score_type."""
        metric = RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Classify sentiment",
            evaluation_steps="Check tone",
            reasoning="Sentiment classification",
            score_type="categorical",
            reference_score="positive"
        )
        
        assert metric.name == "test_metric"
        assert metric.score_type == ScoreType.CATEGORICAL
        assert metric.reference_score == "positive"
        assert metric.evaluation_prompt == "Classify sentiment"
    
    def test_rhesis_prompt_metric_binary(self):
        """Test creating RhesisPromptMetric with binary score_type."""
        metric = RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Pass or fail",
            evaluation_steps="Check criteria",
            reasoning="Binary check",
            score_type="binary",
            reference_score="True"
        )
        
        assert metric.name == "test_metric"
        assert metric.score_type == ScoreType.BINARY
        assert metric.reference_score == "True"
    
    def test_rhesis_prompt_metric_with_model_string(self):
        """Test creating metric with custom model as string."""
        metric = RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Rate quality",
            evaluation_steps="Check accuracy",
            reasoning="Quality assessment",
            score_type="numeric",
            min_score=0,
            max_score=10,
            model="gemini"
        )
        
        assert metric.name == "test_metric"
        assert metric.provider == "gemini"
        assert metric.score_type == ScoreType.NUMERIC
    
    def test_rhesis_prompt_metric_default_threshold_operator(self):
        """Test default threshold_operator is None."""
        metric = RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Rate quality",
            evaluation_steps="Steps",
            reasoning="Reason",
            score_type="numeric",
            min_score=0,
            max_score=10,
            threshold=7
        )
        
        # Default threshold operator is None when not specified
        assert metric.threshold_operator is None
    
    def test_rhesis_prompt_metric_custom_threshold_operator(self):
        """Test custom threshold_operator."""
        metric = RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Rate quality",
            evaluation_steps="Steps",
            reasoning="Reason",
            score_type="numeric",
            min_score=0,
            max_score=10,
            threshold=7,
            threshold_operator=">"
        )
        
        # threshold_operator is stored as enum
        assert metric.threshold_operator == ThresholdOperator.GREATER_THAN
    
    def test_rhesis_prompt_metric_ground_truth_required(self):
        """Test ground_truth requirement via property."""
        metric = RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Compare with ground truth",
            evaluation_steps="Check similarity",
            reasoning="Accuracy check",
            score_type="numeric",
            min_score=0,
            max_score=10
        )
        
        # RhesisPromptMetric has a property requires_ground_truth
        assert metric.requires_ground_truth is True
    
    def test_rhesis_prompt_metric_stores_evaluation_params(self):
        """Test that evaluation parameters are stored."""
        metric = RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Evaluate with context",
            evaluation_steps="Check relevance",
            reasoning="Context relevance",
            score_type="numeric",
            min_score=0,
            max_score=10
        )
        
        # Verify evaluation parameters are stored
        assert metric.evaluation_prompt == "Evaluate with context"
        assert metric.evaluation_steps == "Check relevance"
        assert metric.reasoning == "Context relevance"
    
    def test_rhesis_metric_factory_create_numeric(self):
        """Test RhesisMetricFactory.create() for numeric metric."""
        factory = RhesisMetricFactory()
        metric = factory.create(
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
        assert metric.score_type == ScoreType.NUMERIC
        assert isinstance(metric, RhesisPromptMetric)
    
    def test_rhesis_metric_factory_create_categorical(self):
        """Test RhesisMetricFactory.create() for categorical metric."""
        factory = RhesisMetricFactory()
        metric = factory.create(
            "RhesisPromptMetric",
            name="test",
            evaluation_prompt="Test",
            evaluation_steps="Steps",
            reasoning="Reason",
            score_type="categorical",
            reference_score="positive"
        )
        
        assert metric is not None
        assert metric.name == "test"
        assert metric.score_type == ScoreType.CATEGORICAL
    
    def test_ragas_metric_creation(self):
        """Test creating Ragas metrics (current behavior)."""
        metric = RagasAnswerRelevancy(threshold=0.7)
        
        assert metric.threshold == 0.7
        # Ragas metrics use snake_case names
        assert metric.name == "answer_relevancy"
    
    def test_ragas_contextual_precision_creation(self):
        """Test creating RagasContextualPrecision metric."""
        metric = RagasContextualPrecision(threshold=0.8)
        
        assert metric.threshold == 0.8
        # Ragas metrics use snake_case names
        assert metric.name == "contextual_precision"
    
    def test_rhesis_prompt_metric_evaluation_examples(self):
        """Test metric with evaluation_examples parameter."""
        examples = "Example 1: High quality\nExample 2: Low quality"
        metric = RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Rate quality",
            evaluation_steps="Steps",
            reasoning="Reason",
            score_type="numeric",
            min_score=0,
            max_score=10,
            evaluation_examples=examples
        )
        
        assert metric.evaluation_examples == examples
    
    def test_rhesis_prompt_metric_additional_params(self):
        """Test metric stores additional parameters in kwargs."""
        metric = RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Rate quality",
            evaluation_steps="Steps",
            reasoning="Reason",
            score_type="numeric",
            min_score=0,
            max_score=10,
            custom_param="custom_value"
        )
        
        # Additional params are stored in additional_params dict
        assert "custom_param" in metric.additional_params
        assert metric.additional_params["custom_param"] == "custom_value"
    
    def test_rhesis_prompt_metric_all_parameters(self):
        """Test creating metric with all parameters specified."""
        metric = RhesisPromptMetric(
            name="comprehensive_metric",
            evaluation_prompt="Comprehensive evaluation",
            evaluation_steps="Step 1\nStep 2\nStep 3",
            reasoning="Detailed reasoning",
            score_type="numeric",
            min_score=0,
            max_score=100,
            threshold=70,
            threshold_operator=">=",
            evaluation_examples="Example responses"
        )
        
        assert metric.name == "comprehensive_metric"
        assert metric.score_type == ScoreType.NUMERIC
        assert metric.min_score == 0
        assert metric.max_score == 100
        # Threshold is normalized: (70-0)/(100-0) = 0.7
        assert metric.threshold == 0.7
        assert metric.raw_threshold == 70
        assert metric.threshold_operator == ThresholdOperator.GREATER_THAN_OR_EQUAL
        assert metric.requires_ground_truth is True  # Property
        assert metric.evaluation_examples == "Example responses"

