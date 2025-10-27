"""
Test current metrics_utils behavior (baseline regression tests).

These tests validate the utility functions that convert database Metric models
to metric configurations, which is a critical interface for the migration.
"""

import pytest
from rhesis.backend.tasks.execution.metrics_utils import create_metric_config_from_model


class TestCurrentMetricsUtils:
    """Test current metrics_utils behavior (baseline)."""
    
    def test_create_metric_config_from_numeric_model(self, test_metric_numeric):
        """Test creating config from DB model with numeric score_type."""
        config = create_metric_config_from_model(test_metric_numeric)
        
        assert config is not None
        assert config["name"] == test_metric_numeric.name
        assert config["class_name"] == "RhesisPromptMetric"
        assert config["backend"] == "rhesis"
        assert config["description"] == test_metric_numeric.description
        
        # threshold is at top level, not in parameters
        assert "threshold" in config
        assert config["threshold"] == 7
        assert "threshold_operator" in config
        
        # Verify parameters
        params = config.get("parameters", {})
        assert "evaluation_prompt" in params
        assert "evaluation_steps" in params
        assert "reasoning" in params
        assert "score_type" in params
        assert params["score_type"] == "numeric"
        assert "min_score" in params
        assert "max_score" in params
    
    def test_create_metric_config_from_categorical_model(self, test_metric_categorical):
        """Test creating config from categorical metric."""
        config = create_metric_config_from_model(test_metric_categorical)
        
        assert config is not None
        assert config["name"] == test_metric_categorical.name
        assert config["class_name"] == "RhesisPromptMetric"
        assert config["backend"] == "rhesis"
        
        # reference_score is at top level, not in parameters
        assert "reference_score" in config
        assert config["reference_score"] == "positive"
        # No threshold for categorical metrics
        assert "threshold" not in config
        
        # Verify parameters
        params = config.get("parameters", {})
        assert "score_type" in params
        assert params["score_type"] == "categorical"
    
    def test_create_metric_config_backend_mapping(self, test_db, test_org_id, authenticated_user_id):
        """Test backend type mapping (custom-code → custom, etc)."""
        from rhesis.backend.app import models
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
        
        # Create metric with custom backend type
        backend_type = get_or_create_type_lookup(
            test_db,
            type_name="backend_type",
            type_value="custom-code",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        
        metric_type = get_or_create_type_lookup(
            test_db,
            type_name="metric_type",
            type_value="custom-code",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        
        metric = models.Metric(
            name="Custom Metric",
            class_name="CustomMetric",
            score_type="numeric",
            evaluation_prompt="Test",
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(metric)
        test_db.commit()
        test_db.refresh(metric)
        
        config = create_metric_config_from_model(metric)
        
        assert config is not None
        # Backend should be mapped from custom-code to custom
        assert config["backend"] == "custom"
    
    def test_create_metric_config_detects_rhesis_class(self, test_db, test_org_id, authenticated_user_id):
        """Test class_name starting with 'Rhesis' uses rhesis backend."""
        from rhesis.backend.app import models
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
        
        # Create metric with Rhesis class name but different backend type
        backend_type = get_or_create_type_lookup(
            test_db,
            type_name="backend_type",
            type_value="custom",
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
        
        metric = models.Metric(
            name="Rhesis Custom Metric",
            class_name="RhesisPromptMetric",  # Starts with "Rhesis"
            score_type="numeric",
            evaluation_prompt="Test",
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(metric)
        test_db.commit()
        test_db.refresh(metric)
        
        config = create_metric_config_from_model(metric)
        
        assert config is not None
        # Should use "rhesis" backend because class_name starts with "Rhesis"
        assert config["backend"] == "rhesis"
    
    def test_create_metric_config_missing_class_name(self, test_db, test_org_id, authenticated_user_id):
        """Test returns None when class_name missing."""
        from rhesis.backend.app import models
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
        
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
        
        metric = models.Metric(
            name="Incomplete Metric",
            class_name=None,  # Missing class_name
            score_type="numeric",
            evaluation_prompt="Test",
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(metric)
        test_db.commit()
        test_db.refresh(metric)
        
        config = create_metric_config_from_model(metric)
        
        # Should return None for invalid metric
        assert config is None
    
    def test_create_metric_config_with_model(self, test_db, test_org_id, authenticated_user_id, test_model):
        """Test creating config from metric with associated model."""
        from rhesis.backend.app import models
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
        
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
        
        metric = models.Metric(
            name="Metric with Model",
            class_name="RhesisPromptMetric",
            score_type="numeric",
            evaluation_prompt="Test",
            model_id=test_model.id,
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(metric)
        test_db.commit()
        test_db.refresh(metric)
        
        config = create_metric_config_from_model(metric)
        
        assert config is not None
        assert config["model_id"] == str(test_model.id)
    
    def test_create_metric_config_preserves_all_fields(self, test_db, test_org_id, authenticated_user_id):
        """Test that all metric fields are preserved in config."""
        from rhesis.backend.app import models
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
        
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
        
        metric = models.Metric(
            name="Comprehensive Metric",
            description="Detailed description",
            class_name="RhesisPromptMetric",
            score_type="numeric",
            evaluation_prompt="Evaluate quality",
            evaluation_steps="Step 1\nStep 2\nStep 3",
            reasoning="Detailed reasoning",
            min_score=0,
            max_score=100,
            threshold=70,
            threshold_operator=">=",
            ground_truth_required=True,
            context_required=True,
            evaluation_examples="Example 1\nExample 2",
            explanation="Detailed explanation",
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(metric)
        test_db.commit()
        test_db.refresh(metric)
        
        config = create_metric_config_from_model(metric)
        
        assert config is not None
        assert config["name"] == "Comprehensive Metric"
        assert config["description"] == "Detailed description"
        
        # threshold and threshold_operator are at top level
        assert config["threshold"] == 70
        assert config["threshold_operator"] == ">="
        
        # Parameters dict contains evaluation fields, score ranges, etc
        params = config["parameters"]
        assert params["evaluation_prompt"] == "Evaluate quality"
        assert params["evaluation_steps"] == "Step 1\nStep 2\nStep 3"
        assert params["reasoning"] == "Detailed reasoning"
        assert params["min_score"] == 0
        assert params["max_score"] == 100
        assert params["score_type"] == "numeric"
        
        # Note: ground_truth_required, context_required, evaluation_examples, explanation
        # are NOT in the current backend implementation of create_metric_config_from_model
    
    def test_create_metric_config_ragas_metric(self, test_db, test_org_id, authenticated_user_id):
        """Test creating config for Ragas metric."""
        from rhesis.backend.app import models
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
        
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
        
        metric = models.Metric(
            name="Ragas Answer Relevancy",
            class_name="RagasAnswerRelevancy",
            score_type="numeric",
            evaluation_prompt="N/A for framework metrics",
            threshold=0.7,
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(metric)
        test_db.commit()
        test_db.refresh(metric)
        
        config = create_metric_config_from_model(metric)
        
        assert config is not None
        assert config["backend"] == "ragas"
        assert config["class_name"] == "RagasAnswerRelevancy"
    
    def test_create_metric_config_binary_score_type(self, test_db, test_org_id, authenticated_user_id):
        """Test creating config for binary score type metric."""
        from rhesis.backend.app import models
        from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
        
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
        
        metric = models.Metric(
            name="Binary Metric",
            class_name="RhesisPromptMetric",
            score_type="binary",
            evaluation_prompt="Pass or fail?",
            evaluation_steps="Check criteria",
            reasoning="Binary check",
            reference_score="True",
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(metric)
        test_db.commit()
        test_db.refresh(metric)
        
        config = create_metric_config_from_model(metric)
        
        assert config is not None
        # reference_score is at top level for binary/categorical metrics
        assert "reference_score" in config
        assert config["reference_score"] == "True"
        # No threshold for binary metrics
        assert "threshold" not in config
        
        # Parameters should contain score_type
        params = config["parameters"]
        assert params["score_type"] == "binary"

