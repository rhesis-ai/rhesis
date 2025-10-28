"""
Test current task execution flow (baseline regression tests).

These tests validate the test execution orchestration that uses metrics,
focusing on the interfaces between components.
"""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.metrics import Evaluator, MetricResult
from rhesis.backend.tasks.execution.evaluation import evaluate_prompt_response
from rhesis.backend.tasks.execution.test_execution import (
    get_test_and_prompt,
    get_test_metrics,
    prepare_metric_configs,
)


class TestTaskExecution:
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
    
    def test_prepare_metric_configs_with_valid_dicts(self):
        """Test prepare_metric_configs validates and passes through valid metric dicts."""
        # This test covers the previously untested code path that caused the production bug
        metrics = [
            {
                "name": "Test Metric 1",
                "class_name": "RhesisPromptMetric",
                "backend": "rhesis",
                "parameters": {"score_type": "numeric"}
            },
            {
                "name": "Test Metric 2",
                "class_name": "DeepEvalAnswerRelevancy",
                "backend": "deepeval",
                "threshold": 0.7
            }
        ]
        
        result = prepare_metric_configs(metrics, "test-id-123")
        
        # Should return all valid metrics
        assert len(result) == 2
        assert isinstance(result[0], dict)
        assert isinstance(result[1], dict)
        assert result[0]["name"] == "Test Metric 1"
        assert result[1]["name"] == "Test Metric 2"
    
    def test_prepare_metric_configs_filters_invalid(self):
        """Test prepare_metric_configs filters out invalid metric dicts."""
        metrics = [
            {
                "name": "Valid Metric",
                "class_name": "RhesisPromptMetric",
                "backend": "rhesis"
            },
            {
                "name": "Invalid - No class_name",
                "backend": "rhesis"
                # Missing class_name!
            },
            "not a dict",  # Invalid type
        ]
        
        result = prepare_metric_configs(metrics, "test-id-123")
        
        # Should only return the valid metric
        assert len(result) == 1
        assert result[0]["name"] == "Valid Metric"
    
    def test_prepare_metric_configs_empty_list(self):
        """Test prepare_metric_configs handles empty metric list."""
        result = prepare_metric_configs([], "test-id-123")
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    @patch("rhesis.sdk.metrics.MetricFactory.create")
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
    
    @patch("rhesis.sdk.metrics.MetricFactory.create")
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
    
    @patch("rhesis.sdk.metrics.MetricFactory.create")
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
    
    @patch("rhesis.sdk.metrics.MetricFactory.create")
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
        # All returned metrics should be Metric models with class_name
        for metric in metrics:
            assert metric is not None
            assert hasattr(metric, "class_name")
            assert metric.class_name is not None
    
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
    
    def test_full_metric_flow_without_mocks(self):
        """
        Integration test: Full metric flow from dict → prepare_metric_configs → evaluator → adapter.
        
        This test exercises the ENTIRE flow without mocking the adapter, ensuring that:
        1. prepare_metric_configs correctly validates dicts
        2. Evaluator accepts the dicts
        3. Adapter properly converts dicts to SDK metrics
        4. The full chain works end-to-end
        
        This would have caught the MetricConfig.from_dict() bug!
        """
        # Create metric configs as dicts (simulating get_test_metrics output)
        raw_metrics = [
            {
                "name": "Test Numeric Metric",
                "class_name": "RhesisPromptMetric",
                "backend": "rhesis",
                "description": "Test metric",
                "threshold": 0.7,
                "parameters": {
                    "score_type": "numeric",
                    "evaluation_prompt": "Rate the quality",
                    "evaluation_steps": "1. Check accuracy\n2. Check relevance",
                    "reasoning": "Consider completeness"
                }
            }
        ]
        
        # Step 1: Validate with prepare_metric_configs (previously untested!)
        validated_metrics = prepare_metric_configs(raw_metrics, "test-id-456")
        
        assert len(validated_metrics) == 1
        assert isinstance(validated_metrics[0], dict)
        
        # Step 2: Pass to evaluator (should accept dicts)
        evaluator = Evaluator()
        
        # The KEY test: this flow should NOT crash with "MetricConfig.from_dict()" error
        # We expect it to fail with model configuration issues, but NOT dict conversion issues
        try:
            results = evaluator.evaluate(
                input_text="Test input",
                output_text="Test output",
                expected_output="Expected output",
                context=[],
                metrics=validated_metrics
            )
            
            # If we somehow got results, that's great! But we're really just testing
            # that the dict → adapter → SDK flow works without MetricConfig.from_dict() errors
            assert isinstance(results, dict)
            
        except (ValueError, AttributeError) as e:
            error_msg = str(e)
            
            # These errors are EXPECTED (model configuration issues):
            if any(expected in error_msg for expected in [
                "RHESIS_API_KEY",
                "Provider",
                "api_key",
                "not set"
            ]):
                # SUCCESS! We exercised the full chain:
                # dict → prepare_metric_configs → evaluator → adapter → SDK metric creation
                # The error is from model configuration, NOT from MetricConfig.from_dict()
                pass
            
            # This error means we hit the bug we're testing for:
            elif "from_dict" in error_msg:
                raise AssertionError(
                    f"Hit the MetricConfig.from_dict() bug! This test should prevent this: {error_msg}"
                )
            
            # Any other error is unexpected
            else:
                raise

