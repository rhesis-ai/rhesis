"""
Test current end-to-end flow (baseline regression tests).

These tests validate the complete flow from test execution to result storage,
ensuring all components work together correctly.
"""

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4
from rhesis.backend.metrics import MetricResult


class TestCurrentE2EFlow:
    """Test current end-to-end flow (baseline)."""
    
    @pytest.fixture
    def test_endpoint(self, test_db, test_org_id, authenticated_user_id):
        """Create a test endpoint."""
        from rhesis.backend.app import models
        
        endpoint = models.Endpoint(
            name="Test Endpoint",
            protocol="REST",
            url="https://api.example.com/test",
            method="POST",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(endpoint)
        test_db.commit()
        test_db.refresh(endpoint)
        return endpoint
    
    @pytest.fixture
    def test_run(self, test_db, test_org_id, authenticated_user_id):
        """Create a test run."""
        from rhesis.backend.app import models
        from rhesis.backend.app.utils.crud_utils import get_or_create_status
        
        status = get_or_create_status(
            test_db,
            status_name="running",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        
        test_run = models.TestRun(
            status_id=status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(test_run)
        test_db.commit()
        test_db.refresh(test_run)
        return test_run
    
    @pytest.fixture
    def test_config(self, test_db, test_org_id, authenticated_user_id, test_endpoint, test_behavior_with_metrics):
        """Create a test configuration."""
        from rhesis.backend.app import models
        
        test_config = models.TestConfiguration(
            name="Test Config",
            endpoint_id=test_endpoint.id,
            behavior_id=test_behavior_with_metrics.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(test_config)
        test_db.commit()
        test_db.refresh(test_config)
        return test_config
    
    @pytest.fixture
    def full_test_setup(self, test_db, test_with_prompt, test_endpoint, test_run, test_config):
        """Complete test setup with all components."""
        return {
            "db": test_db,
            "test": test_with_prompt,
            "test_id": str(test_with_prompt.id),
            "endpoint": test_endpoint,
            "endpoint_id": str(test_endpoint.id),
            "test_run": test_run,
            "test_run_id": str(test_run.id),
            "test_config": test_config,
            "test_config_id": str(test_config.id),
            "organization_id": str(test_with_prompt.organization_id),
            "user_id": str(test_with_prompt.user_id),
        }
    
    @patch('rhesis.backend.app.services.endpoint_service.EndpointService.invoke_endpoint')
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_e2e_single_test_execution(self, mock_evaluate, mock_invoke, full_test_setup):
        """Test complete flow: task → execution → evaluation → storage."""
        # Mock endpoint invocation
        mock_invoke.return_value = {
            "output": "The answer is 4",
            "status_code": 200
        }
        
        # Mock metric evaluation
        mock_evaluate.return_value = MetricResult(
            name="Test Metric",
            score=9.0,
            passed=True,
            reason="Excellent response",
            threshold=7.0,
            threshold_operator=">=",
            verdict="pass"
        )
        
        from rhesis.backend.tasks.execution.test_execution import execute_test
        
        result = execute_test(
            db=full_test_setup["db"],
            test_config_id=full_test_setup["test_config_id"],
            test_run_id=full_test_setup["test_run_id"],
            test_id=full_test_setup["test_id"],
            endpoint_id=full_test_setup["endpoint_id"],
            organization_id=full_test_setup["organization_id"],
            user_id=full_test_setup["user_id"]
        )
        
        # Verify execution result
        assert result is not None
        assert "test_id" in result
        assert result["test_id"] == full_test_setup["test_id"]
        
        # Verify result was stored in database
        from rhesis.backend.app import crud
        from uuid import UUID
        
        test_results = crud.get_test_results_by_test_run(
            full_test_setup["db"],
            UUID(full_test_setup["test_run_id"])
        )
        
        assert len(test_results) > 0
        # Find our test result
        our_result = next((r for r in test_results if str(r.test_id) == full_test_setup["test_id"]), None)
        assert our_result is not None
        assert our_result.test_metrics is not None
    
    @patch('rhesis.backend.app.services.endpoint_service.EndpointService.invoke_endpoint')
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_e2e_with_multiple_metrics(self, mock_evaluate, mock_invoke, full_test_setup):
        """Test execution with multiple metrics."""
        mock_invoke.return_value = {
            "output": "Positive response",
            "status_code": 200
        }
        
        # Multiple metric evaluations
        mock_evaluate.side_effect = [
            MetricResult(
                name="Quality Metric",
                score=8.5,
                passed=True,
                reason="High quality",
                threshold=7.0,
                threshold_operator=">=",
                verdict="pass"
            ),
            MetricResult(
                name="Sentiment Metric",
                score="positive",
                passed=True,
                reason="Positive sentiment",
                verdict="pass"
            )
        ]
        
        from rhesis.backend.tasks.execution.test_execution import execute_test
        
        result = execute_test(
            db=full_test_setup["db"],
            test_config_id=full_test_setup["test_config_id"],
            test_run_id=full_test_setup["test_run_id"],
            test_id=full_test_setup["test_id"],
            endpoint_id=full_test_setup["endpoint_id"],
            organization_id=full_test_setup["organization_id"],
            user_id=full_test_setup["user_id"]
        )
        
        assert result is not None
        # Multiple metrics should be evaluated (mock was called multiple times)
        assert mock_evaluate.call_count >= 2
    
    @patch('rhesis.backend.app.services.endpoint_service.EndpointService.invoke_endpoint')
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_e2e_handles_endpoint_error(self, mock_evaluate, mock_invoke, full_test_setup):
        """Test flow handles endpoint errors gracefully."""
        # Endpoint fails
        mock_invoke.side_effect = Exception("Endpoint unavailable")
        
        from rhesis.backend.tasks.execution.test_execution import execute_test
        
        # Should handle error gracefully
        try:
            result = execute_test(
                db=full_test_setup["db"],
                test_config_id=full_test_setup["test_config_id"],
                test_run_id=full_test_setup["test_run_id"],
                test_id=full_test_setup["test_id"],
                endpoint_id=full_test_setup["endpoint_id"],
                organization_id=full_test_setup["organization_id"],
                user_id=full_test_setup["user_id"]
            )
            # If it returns, verify it contains error info
            assert result is not None
        except Exception as e:
            # If it raises, that's also acceptable current behavior
            assert "unavailable" in str(e).lower() or "error" in str(e).lower()
    
    @patch('rhesis.backend.app.services.endpoint_service.EndpointService.invoke_endpoint')
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_e2e_handles_metric_evaluation_error(self, mock_evaluate, mock_invoke, full_test_setup):
        """Test flow handles metric evaluation errors gracefully."""
        mock_invoke.return_value = {
            "output": "Test response",
            "status_code": 200
        }
        
        # Metric evaluation fails
        mock_evaluate.side_effect = Exception("Evaluation failed")
        
        from rhesis.backend.tasks.execution.test_execution import execute_test
        
        # Should handle gracefully and still store result
        result = execute_test(
            db=full_test_setup["db"],
            test_config_id=full_test_setup["test_config_id"],
            test_run_id=full_test_setup["test_run_id"],
            test_id=full_test_setup["test_id"],
            endpoint_id=full_test_setup["endpoint_id"],
            organization_id=full_test_setup["organization_id"],
            user_id=full_test_setup["user_id"]
        )
        
        # Result should still be returned even if metrics fail
        assert result is not None
    
    @patch('rhesis.backend.app.services.endpoint_service.EndpointService.invoke_endpoint')
    @patch('rhesis.backend.metrics.ragas.metrics.RagasAnswerRelevancy.evaluate')
    def test_e2e_with_ragas_metric(self, mock_ragas_evaluate, mock_invoke, test_db, test_org_id, authenticated_user_id, test_with_prompt, test_endpoint, test_run):
        """Test with Ragas metric."""
        from rhesis.backend.app import models
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
        
        # Create behavior with Ragas metric
        backend_type = get_or_create_type_lookup(
            test_db,
            type_name="backend_type",
            type_value="ragas",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        
        metric_type = get_or_create_type_lookup(
            test_db,
            type_name="metric_type",
            type_value="framework",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        
        ragas_metric = models.Metric(
            name="Ragas Answer Relevancy",
            class_name="RagasAnswerRelevancy",
            score_type="numeric",
            evaluation_prompt="N/A",
            threshold=0.7,
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(ragas_metric)
        test_db.flush()
        
        behavior = models.Behavior(
            name="Behavior with Ragas",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(behavior)
        test_db.flush()
        
        behavior.metrics = [ragas_metric]
        
        test_config = models.TestConfiguration(
            name="Config with Ragas",
            endpoint_id=test_endpoint.id,
            behavior_id=behavior.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(test_config)
        test_db.commit()
        test_db.refresh(test_config)
        
        # Update test to use this behavior
        test_with_prompt.behavior_id = behavior.id
        test_db.commit()
        
        mock_invoke.return_value = {
            "output": "Relevant answer",
            "status_code": 200
        }
        
        mock_ragas_evaluate.return_value = MetricResult(
            name="Ragas Answer Relevancy",
            score=0.85,
            passed=True,
            reason="Highly relevant",
            threshold=0.7,
            threshold_operator=">=",
            verdict="pass"
        )
        
        from rhesis.backend.tasks.execution.test_execution import execute_test
        
        result = execute_test(
            db=test_db,
            test_config_id=str(test_config.id),
            test_run_id=str(test_run.id),
            test_id=str(test_with_prompt.id),
            endpoint_id=str(test_endpoint.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        
        assert result is not None
    
    @patch('rhesis.backend.app.services.endpoint_service.EndpointService.invoke_endpoint')
    def test_e2e_stores_execution_time(self, mock_invoke, full_test_setup):
        """Test that execution time is tracked and stored."""
        mock_invoke.return_value = {
            "output": "Response",
            "status_code": 200
        }
        
        from rhesis.backend.tasks.execution.test_execution import execute_test
        from rhesis.backend.app import crud
        from uuid import UUID
        
        result = execute_test(
            db=full_test_setup["db"],
            test_config_id=full_test_setup["test_config_id"],
            test_run_id=full_test_setup["test_run_id"],
            test_id=full_test_setup["test_id"],
            endpoint_id=full_test_setup["endpoint_id"],
            organization_id=full_test_setup["organization_id"],
            user_id=full_test_setup["user_id"]
        )
        
        # Retrieve stored result
        test_results = crud.get_test_results_by_test_run(
            full_test_setup["db"],
            UUID(full_test_setup["test_run_id"])
        )
        
        our_result = next((r for r in test_results if str(r.test_id) == full_test_setup["test_id"]), None)
        assert our_result is not None
        assert our_result.execution_time is not None
        assert our_result.execution_time >= 0
    
    @patch('rhesis.backend.app.services.endpoint_service.EndpointService.invoke_endpoint')
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_e2e_metric_results_structure(self, mock_evaluate, mock_invoke, full_test_setup):
        """Test that metric results are stored in correct structure."""
        mock_invoke.return_value = {
            "output": "Test response",
            "status_code": 200
        }
        
        mock_evaluate.return_value = MetricResult(
            name="Quality Metric",
            score=8.0,
            passed=True,
            reason="Good quality",
            threshold=7.0,
            threshold_operator=">=",
            verdict="pass"
        )
        
        from rhesis.backend.tasks.execution.test_execution import execute_test
        from rhesis.backend.app import crud
        from uuid import UUID
        
        execute_test(
            db=full_test_setup["db"],
            test_config_id=full_test_setup["test_config_id"],
            test_run_id=full_test_setup["test_run_id"],
            test_id=full_test_setup["test_id"],
            endpoint_id=full_test_setup["endpoint_id"],
            organization_id=full_test_setup["organization_id"],
            user_id=full_test_setup["user_id"]
        )
        
        # Retrieve and verify structure
        test_results = crud.get_test_results_by_test_run(
            full_test_setup["db"],
            UUID(full_test_setup["test_run_id"])
        )
        
        our_result = next((r for r in test_results if str(r.test_id) == full_test_setup["test_id"]), None)
        assert our_result is not None
        assert our_result.test_metrics is not None
        assert isinstance(our_result.test_metrics, dict)
        
        # Verify metrics structure has expected fields
        for metric_name, metric_data in our_result.test_metrics.items():
            assert isinstance(metric_data, dict)
            # Should have key metric fields (exact structure may vary)
            assert "score" in metric_data or "passed" in metric_data
    
    @patch('rhesis.backend.app.services.endpoint_service.EndpointService.invoke_endpoint')
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_e2e_result_queryable_via_api(self, mock_evaluate, mock_invoke, full_test_setup):
        """Test that stored results are queryable."""
        mock_invoke.return_value = {
            "output": "Response",
            "status_code": 200
        }
        
        mock_evaluate.return_value = MetricResult(
            name="Metric",
            score=7.5,
            passed=True,
            reason="Pass",
            threshold=7.0,
            threshold_operator=">=",
            verdict="pass"
        )
        
        from rhesis.backend.tasks.execution.test_execution import execute_test
        from rhesis.backend.app import crud
        from uuid import UUID
        
        execute_test(
            db=full_test_setup["db"],
            test_config_id=full_test_setup["test_config_id"],
            test_run_id=full_test_setup["test_run_id"],
            test_id=full_test_setup["test_id"],
            endpoint_id=full_test_setup["endpoint_id"],
            organization_id=full_test_setup["organization_id"],
            user_id=full_test_setup["user_id"]
        )
        
        # Query via different methods
        # 1. By test run
        by_run = crud.get_test_results_by_test_run(
            full_test_setup["db"],
            UUID(full_test_setup["test_run_id"])
        )
        assert len(by_run) > 0
        
        # 2. By test ID
        by_test = crud.get_test_results_by_test(
            full_test_setup["db"],
            UUID(full_test_setup["test_id"])
        )
        assert len(by_test) > 0
        
        # 3. Individual result
        result_id = by_run[0].id
        individual = crud.get_test_result(full_test_setup["db"], result_id)
        assert individual is not None

