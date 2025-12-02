"""
Test current database operations for metrics (baseline regression tests).

These tests validate database integration for metrics, including CRUD operations
and the storage of evaluation results in TestResult.test_metrics.
"""

from rhesis.backend.app import crud, models, schemas


class TestDatabaseIntegration:
    """Test current database operations (baseline)."""

    def test_create_metric_in_database(self, test_db, test_org_id, authenticated_user_id):
        """Test creating metric record."""
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

        # Get or create required types
        backend_type = get_or_create_type_lookup(
            test_db,
            type_name="backend_type",
            type_value="rhesis",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        metric_type = get_or_create_type_lookup(
            test_db,
            type_name="metric_type",
            type_value="custom-prompt",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        metric_data = schemas.MetricCreate(
            name="Test Metric",
            description="Test metric for baseline",
            class_name="RhesisPromptMetric",
            score_type="numeric",
            evaluation_prompt="Test prompt",
            evaluation_steps="Steps",
            reasoning="Reason",
            min_score=0,
            max_score=10,
            threshold=7,
            threshold_operator=">=",
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
        )

        metric = crud.create_metric(
            test_db, metric_data, organization_id=test_org_id, user_id=authenticated_user_id
        )

        assert metric.id is not None
        assert metric.name == "Test Metric"
        assert metric.class_name == "RhesisPromptMetric"
        assert metric.score_type == "numeric"
        assert metric.threshold == 7

    def test_get_metric_by_id(self, test_db, test_org_id, test_metric_numeric):
        """Test retrieving metric by ID."""
        metric = crud.get_metric(test_db, test_metric_numeric.id, test_org_id)

        assert metric is not None
        assert metric.id == test_metric_numeric.id
        assert metric.name == test_metric_numeric.name
        assert metric.class_name == test_metric_numeric.class_name

    def test_get_metrics_list(
        self, test_db, test_org_id, test_metric_numeric, test_metric_categorical
    ):
        """Test retrieving list of metrics."""
        metrics = crud.get_metrics(test_db, organization_id=test_org_id)

        assert isinstance(metrics, list)
        assert len(metrics) >= 2  # At least our two test metrics

        # Verify our metrics are in the list
        metric_ids = [m.id for m in metrics]
        assert test_metric_numeric.id in metric_ids
        assert test_metric_categorical.id in metric_ids

    def test_update_metric(self, test_db, test_org_id, test_metric_numeric):
        """Test updating metric."""
        update_data = schemas.MetricUpdate(name="Updated Metric Name", threshold=8)

        updated_metric = crud.update_metric(
            test_db, test_metric_numeric.id, update_data, test_org_id
        )

        assert updated_metric.name == "Updated Metric Name"
        assert updated_metric.threshold == 8
        # Other fields should remain unchanged
        assert updated_metric.class_name == test_metric_numeric.class_name

    def test_delete_metric(self, test_db, test_org_id, authenticated_user_id):
        """Test deleting metric."""
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

        # Create a metric to delete
        backend_type = get_or_create_type_lookup(
            test_db,
            type_name="backend_type",
            type_value="rhesis",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        metric_type = get_or_create_type_lookup(
            test_db,
            type_name="metric_type",
            type_value="custom-prompt",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        metric = models.Metric(
            name="Metric to Delete",
            class_name="RhesisPromptMetric",
            score_type="numeric",
            evaluation_prompt="Test",
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(metric)
        test_db.commit()
        test_db.refresh(metric)

        metric_id = metric.id

        # Delete the metric
        crud.delete_metric(test_db, metric_id, test_org_id, authenticated_user_id)

        # Verify it's deleted (soft delete)
        deleted_metric = crud.get_metric(test_db, metric_id, test_org_id)
        assert deleted_metric is None

    def test_metric_with_model_relationship(
        self, test_db, test_model, test_org_id, authenticated_user_id
    ):
        """Test metric with associated model."""
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

        backend_type = get_or_create_type_lookup(
            test_db,
            type_name="backend_type",
            type_value="rhesis",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        metric_type = get_or_create_type_lookup(
            test_db,
            type_name="metric_type",
            type_value="custom-prompt",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        metric = models.Metric(
            name="Metric with Model",
            class_name="RhesisPromptMetric",
            score_type="numeric",
            evaluation_prompt="Test",
            model_id=test_model.id,
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(metric)
        test_db.commit()
        test_db.refresh(metric)

        # Verify relationship
        assert metric.model_id == test_model.id
        assert metric.model is not None
        assert metric.model.id == test_model.id

    def test_metric_with_behavior_relationship(
        self, test_db, test_behavior_with_metrics, test_metric_numeric
    ):
        """Test metric associated with behavior."""
        behavior = test_behavior_with_metrics

        # Verify behavior has metrics
        assert len(behavior.metrics) > 0

        # Verify our metric is in the behavior's metrics
        metric_ids = [m.id for m in behavior.metrics]
        assert test_metric_numeric.id in metric_ids

        # Verify reverse relationship (if implemented)
        # Some ORMs support querying behaviors that use a metric
        assert test_metric_numeric.id is not None

    def test_test_result_test_metrics_storage(
        self, test_db, test_org_id, authenticated_user_id, db_test_with_prompt
    ):
        """Test storing evaluation results in TestResult.test_metrics."""

        from rhesis.backend.app.utils.crud_utils import get_or_create_status

        # Get or create status
        status = get_or_create_status(
            test_db,
            name="completed",
            entity_type="TestResult",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        # Create test result with metrics
        metrics_results = {
            "Test Metric 1": {
                "name": "Test Metric 1",
                "score": 8.0,
                "passed": True,
                "reason": "Good quality",
                "threshold": 7.0,
                "verdict": "pass",
            },
            "Test Metric 2": {
                "name": "Test Metric 2",
                "score": "positive",
                "passed": True,
                "reason": "Positive sentiment",
                "verdict": "pass",
            },
        }

        test_result = models.TestResult(
            test_id=db_test_with_prompt.id,
            test_run_id=None,
            test_configuration_id=None,
            test_output={"result": "Test response", "execution_time": 0.5},
            test_metrics=metrics_results,  # This is the critical field
            status_id=status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_result)
        test_db.commit()
        test_db.refresh(test_result)

        # Verify storage
        assert test_result.id is not None
        assert test_result.test_metrics is not None
        assert isinstance(test_result.test_metrics, dict)
        assert len(test_result.test_metrics) == 2
        assert "Test Metric 1" in test_result.test_metrics
        assert test_result.test_metrics["Test Metric 1"]["score"] == 8.0
        assert test_result.test_metrics["Test Metric 2"]["score"] == "positive"

    def test_test_result_test_metrics_retrieval(
        self, test_db, test_org_id, authenticated_user_id, db_test_with_prompt
    ):
        """Test retrieving test_metrics from TestResult."""

        from rhesis.backend.app.utils.crud_utils import get_or_create_status

        status = get_or_create_status(
            test_db,
            name="completed",
            entity_type="TestResult",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        # Create test result
        metrics_results = {
            "Metric A": {"score": 9.0, "passed": True},
            "Metric B": {"score": "excellent", "passed": True},
        }

        test_result = models.TestResult(
            test_id=db_test_with_prompt.id,
            test_run_id=None,
            test_configuration_id=None,
            test_output={"result": "Response", "execution_time": 0.3},
            test_metrics=metrics_results,
            status_id=status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_result)
        test_db.commit()
        test_db.refresh(test_result)

        # Retrieve via CRUD
        retrieved_result = crud.get_test_result(test_db, test_result.id, test_org_id)

        assert retrieved_result is not None
        assert retrieved_result.test_metrics is not None
        assert len(retrieved_result.test_metrics) == 2
        assert retrieved_result.test_metrics["Metric A"]["score"] == 9.0
        assert retrieved_result.test_metrics["Metric B"]["score"] == "excellent"

    def test_test_result_empty_test_metrics(
        self, test_db, test_org_id, authenticated_user_id, db_test_with_prompt
    ):
        """Test TestResult with empty test_metrics."""

        from rhesis.backend.app.utils.crud_utils import get_or_create_status

        status = get_or_create_status(
            test_db,
            name="completed",
            entity_type="TestResult",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        test_result = models.TestResult(
            test_id=db_test_with_prompt.id,
            test_run_id=None,
            test_configuration_id=None,
            test_output={"result": "Response", "execution_time": 0.2},
            test_metrics={},  # Empty metrics
            status_id=status.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_result)
        test_db.commit()
        test_db.refresh(test_result)

        assert test_result.test_metrics is not None
        assert isinstance(test_result.test_metrics, dict)
        assert len(test_result.test_metrics) == 0

    def test_query_metrics_by_organization(
        self, test_db, test_org_id, test_metric_numeric, secondary_org_id
    ):
        """Test querying metrics filtered by organization."""
        # Metrics should be isolated by organization
        metrics_org1 = crud.get_metrics(test_db, organization_id=test_org_id)
        metrics_org2 = crud.get_metrics(test_db, organization_id=secondary_org_id)

        org1_ids = [m.id for m in metrics_org1]
        org2_ids = [m.id for m in metrics_org2]

        # Test metric should be in org1 but not org2
        assert test_metric_numeric.id in org1_ids
        assert test_metric_numeric.id not in org2_ids
