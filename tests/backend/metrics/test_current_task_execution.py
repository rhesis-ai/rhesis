"""
Test current task execution flow (baseline regression tests).

These tests validate the test execution orchestration that uses metrics,
focusing on the interfaces between components.
"""

import pytest
from unittest.mock import patch, MagicMock
from rhesis.backend.tasks.execution.test_execution import (
    get_test_and_prompt,
    get_test_metrics,
)
from rhesis.backend.tasks.execution.evaluation import evaluate_prompt_response
from rhesis.backend.metrics import Evaluator, MetricResult


class TestCurrentTaskExecution:
    """Test current task execution flow (baseline)."""
    
    @pytest.fixture
    def test_prompt(self, test_db, test_org_id, authenticated_user_id):
        """Create a test prompt."""
        from rhesis.backend.app import models
        
        prompt = models.Prompt(
            content="What is 2+2?",
            expected_response="4",
            language_code="en",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(prompt)
        test_db.commit()
        test_db.refresh(prompt)
        return prompt
    
    @pytest.fixture
    def test_with_prompt(self, test_db, test_org_id, authenticated_user_id, test_prompt, test_behavior_with_metrics):
        """Create a test with prompt and behavior."""
        from rhesis.backend.app import models
        
        test = models.Test(
            prompt_id=test_prompt.id,
            behavior_id=test_behavior_with_metrics.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(test)
        test_db.commit()
        test_db.refresh(test)
        return test
    
    def test_get_test_and_prompt(self, test_db, test_with_prompt, test_org_id):
        """Test retrieving test and prompt."""
        test, prompt_content, expected_response = get_test_and_prompt(
            db=test_db,
            test_id=str(test_with_prompt.id),
            organization_id=test_org_id
        )
        
        assert test is not None
        assert test.id == test_with_prompt.id
        assert prompt_content is not None
        assert prompt_content == "What is 2+2?"
        assert expected_response is not None
        assert expected_response == "4"
    
    def test_get_test_and_prompt_missing_test(self, test_db, test_org_id):
        """Test get_test_and_prompt with non-existent test."""
        from uuid import uuid4
        
        with pytest.raises(ValueError, match="not found"):
            get_test_and_prompt(
                db=test_db,
                test_id=str(uuid4()),
                organization_id=test_org_id
            )
    
    def test_get_test_and_prompt_no_prompt(self, test_db, test_org_id, authenticated_user_id, test_behavior_with_metrics):
        """Test get_test_and_prompt when test has no prompt."""
        from rhesis.backend.app import models
        
        # Create test without prompt
        test = models.Test(
            prompt_id=None,
            behavior_id=test_behavior_with_metrics.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(test)
        test_db.commit()
        test_db.refresh(test)
        
        with pytest.raises(ValueError, match="no associated prompt"):
            get_test_and_prompt(
                db=test_db,
                test_id=str(test.id),
                organization_id=test_org_id
            )
    
    def test_get_test_metrics(self, test_with_prompt):
        """Test retrieving metrics from test's behavior."""
        metrics = get_test_metrics(test_with_prompt)
        
        assert isinstance(metrics, list)
        assert len(metrics) > 0
        # Should have at least the metrics from the behavior
        assert len(metrics) >= 2  # numeric and categorical from fixture
    
    def test_get_test_metrics_no_behavior(self, test_db, test_org_id, authenticated_user_id, test_prompt):
        """Test get_test_metrics when test has no behavior."""
        from rhesis.backend.app import models
        
        # Create test without behavior
        test = models.Test(
            prompt_id=test_prompt.id,
            behavior_id=None,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(test)
        test_db.commit()
        test_db.refresh(test)
        
        metrics = get_test_metrics(test)
        
        # Should return empty list when no behavior (no defaults in SDK)
        assert isinstance(metrics, list)
        assert len(metrics) == 0  # No default metrics anymore
    
    def test_get_test_metrics_behavior_without_metrics(self, test_db, test_org_id, authenticated_user_id, test_prompt):
        """Test get_test_metrics when behavior has no metrics."""
        from rhesis.backend.app import models
        
        # Create behavior without metrics
        behavior = models.Behavior(
            name="Behavior without metrics",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(behavior)
        test_db.flush()
        
        # Create test with this behavior
        test = models.Test(
            prompt_id=test_prompt.id,
            behavior_id=behavior.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(test)
        test_db.commit()
        test_db.refresh(test)
        
        metrics = get_test_metrics(test)
        
        # Should return empty list (no defaults in SDK)
        assert isinstance(metrics, list)
        assert len(metrics) == 0  # No default metrics anymore
    
    @patch('rhesis.backend.metrics.adapters.create_metric_from_config')
    def test_evaluate_prompt_response(self, mock_create_metric):
        """Test evaluate_prompt_response() orchestration."""
        mock_metric = MagicMock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.name = "Test Metric"
        mock_metric.evaluate.return_value = MetricResult(
            score=8.0,
            details={"reason": "Good quality"}
        )
        mock_create_metric.return_value = mock_metric
        
        evaluator = Evaluator()
        result = evaluate_prompt_response(
            metrics_evaluator=evaluator,
            prompt_content="Test prompt",
            expected_response="Expected",
            context=[],
            result={"output": "Test response"},
            metrics=[{
                "name": "Test Metric",
                "class_name": "RhesisPromptMetric",
                "backend": "rhesis",
                "threshold": 7,
                "parameters": {
                    "evaluation_prompt": "Test",
                    "evaluation_steps": "Step 1",
                    "reasoning": "Test reasoning",
                    "score_type": "numeric",
                    "min_score": 0,
                    "max_score": 10
                }
            }]
        )
        
        assert isinstance(result, dict)
        assert len(result) > 0
    
    @patch('rhesis.backend.metrics.adapters.create_metric_from_config')
    def test_evaluate_prompt_response_with_context(self, mock_create_metric):
        """Test evaluate_prompt_response with context."""
        mock_metric = MagicMock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.name = "Context Metric"
        mock_metric.evaluate.return_value = MetricResult(
            score=9.0,
            details={"reason": "High quality with context"}
        )
        mock_create_metric.return_value = mock_metric
        
        evaluator = Evaluator()
        context = ["Context item 1", "Context item 2"]
        
        result = evaluate_prompt_response(
            metrics_evaluator=evaluator,
            prompt_content="Test prompt",
            expected_response="Expected",
            context=context,
            result={"output": "Test response"},
            metrics=[{
                "name": "Test Metric",
                "class_name": "RhesisPromptMetric",
                "backend": "rhesis",
                "parameters": {
                    "evaluation_prompt": "Test",
                    "score_type": "numeric",
                    "threshold": 7
                }
            }]
        )
        
        assert isinstance(result, dict)
    
    @patch('rhesis.backend.metrics.adapters.create_metric_from_config')
    def test_evaluate_prompt_response_empty_metrics(self, mock_create_metric):
        """Test evaluate_prompt_response with empty metrics list."""
        evaluator = Evaluator()
        
        result = evaluate_prompt_response(
            metrics_evaluator=evaluator,
            prompt_content="Test prompt",
            expected_response="Expected",
            context=[],
            result={"output": "Test response"},
            metrics=[]
        )
        
        # Should return result even with no metrics
        assert isinstance(result, dict)
    
    @patch('rhesis.backend.metrics.adapters.create_metric_from_config')
    def test_evaluate_prompt_response_multiple_metrics(self, mock_create_metric):
        """Test evaluate_prompt_response with multiple metrics."""
        mock_metric1 = MagicMock()
        mock_metric1.requires_ground_truth = False
        mock_metric1.requires_context = False
        mock_metric1.name = "Metric 1"
        mock_metric1.evaluate.return_value = MetricResult(
            score=8.0,
            details={"reason": "Good"}
        )
        
        mock_metric2 = MagicMock()
        mock_metric2.requires_ground_truth = False
        mock_metric2.requires_context = False
        mock_metric2.name = "Metric 2"
        mock_metric2.evaluate.return_value = MetricResult(
            score="positive",
            details={"reason": "Positive sentiment"}
        )
        
        mock_create_metric.side_effect = [mock_metric1, mock_metric2]
        
        evaluator = Evaluator()
        metrics = [
            {
                "name": "Metric 1",
                "class_name": "RhesisPromptMetric",
                "backend": "rhesis",
                "threshold": 7,
                "parameters": {
                    "evaluation_prompt": "Test 1",
                    "evaluation_steps": "Step 1",
                    "reasoning": "Test reasoning",
                    "score_type": "numeric",
                    "min_score": 0,
                    "max_score": 10
                }
            },
            {
                "name": "Metric 2",
                "class_name": "RhesisPromptMetric",
                "backend": "rhesis",
                "reference_score": "positive",
                "parameters": {
                    "evaluation_prompt": "Test 2",
                    "evaluation_steps": "Step 1",
                    "reasoning": "Test reasoning",
                    "score_type": "categorical",
                    "reference_score": "positive"
                }
            }
        ]
        
        result = evaluate_prompt_response(
            metrics_evaluator=evaluator,
            prompt_content="Test prompt",
            expected_response="Expected",
            context=[],
            result={"output": "Test response"},
            metrics=metrics
        )
        
        assert isinstance(result, dict)
        assert len(result) >= 2
    
    def test_metrics_filtering_invalid(self, test_db, test_org_id, authenticated_user_id, test_prompt):
        """Test that invalid metrics are filtered out."""
        from rhesis.backend.app import models
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
        
        # Create behavior with some invalid metrics
        behavior = models.Behavior(
            name="Behavior with invalid metrics",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(behavior)
        test_db.flush()
        
        # Create valid metric
        backend_type = get_or_create_type_lookup(
            test_db,
            type_name="backend_type",
            type_value="rhesis",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        
        metric_type = get_or_create_type_lookup(
            test_db,
            type_name="metric_type",
            type_value="custom-prompt",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        
        valid_metric = models.Metric(
            name="Valid Metric",
            class_name="RhesisPromptMetric",
            score_type="numeric",
            evaluation_prompt="Test",
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(valid_metric)
        test_db.flush()
        
        # Create invalid metric (missing class_name)
        invalid_metric = models.Metric(
            name="Invalid Metric",
            class_name=None,
            score_type="numeric",
            evaluation_prompt="Test",
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(invalid_metric)
        test_db.flush()
        
        behavior.metrics = [valid_metric, invalid_metric]
        
        # Create test
        test = models.Test(
            prompt_id=test_prompt.id,
            behavior_id=behavior.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(test)
        test_db.commit()
        test_db.refresh(test)
        
        metrics = get_test_metrics(test)
        
        # Should filter out invalid metrics
        assert isinstance(metrics, list)
        assert len(metrics) >= 1  # At least the valid metric
        # All returned metrics should be valid (have class_name)
        for metric_config in metrics:
            assert metric_config is not None
            assert "class_name" in metric_config
    
    def test_evaluate_prompt_response_with_no_expected_response(self):
        """Test evaluation when no expected response is provided."""
        evaluator = Evaluator()
        
        result = evaluate_prompt_response(
            metrics_evaluator=evaluator,
            prompt_content="Test prompt",
            expected_response=None,  # No expected response
            context=[],
            result={"output": "Test response"},
            metrics=[]
        )
        
        # Should handle gracefully
        assert isinstance(result, dict)
    
    def test_evaluate_prompt_response_extracts_output(self):
        """Test that evaluate_prompt_response extracts output from result."""
        evaluator = Evaluator()
        
        # Test with nested output structure
        result_dict = {
            "output": "Actual response text",
            "metadata": {"tokens": 100}
        }
        
        result = evaluate_prompt_response(
            metrics_evaluator=evaluator,
            prompt_content="Test prompt",
            expected_response="Expected",
            context=[],
            result=result_dict,
            metrics=[]
        )
        
        assert isinstance(result, dict)

