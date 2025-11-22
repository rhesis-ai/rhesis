"""
Tests for in-place test execution service.

These tests verify the in-place test execution functionality that runs tests
synchronously without worker infrastructure or database persistence.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services import test_execution
from rhesis.backend.tasks.enums import ResultStatus
from tests.backend.routes.fixtures.data_factories import (
    BehaviorDataFactory,
    CategoryDataFactory,
    PromptDataFactory,
    TopicDataFactory,
)

# Import fixtures

fake = Faker()


# ============================================================================
# Data Factories
# ============================================================================


def create_single_turn_request_data(**overrides):
    """Create single-turn test execution request data."""
    data = {
        "prompt": {
            "content": fake.paragraph(nb_sentences=3),
            "expected_response": fake.paragraph(nb_sentences=2),
        },
        "behavior": BehaviorDataFactory.minimal_data()["name"],
        "topic": TopicDataFactory.minimal_data()["name"],
        "category": CategoryDataFactory.minimal_data()["name"],
        "test_type": "Single-Turn",
    }
    data.update(overrides)
    return data


def create_multi_turn_request_data(**overrides):
    """Create multi-turn test execution request data."""
    data = {
        "test_configuration": {
            "goal": fake.sentence(nb_words=8),
            "max_turns": 3,
            "success_criteria": fake.sentence(nb_words=10),
        },
        "behavior": BehaviorDataFactory.minimal_data()["name"],
        "topic": TopicDataFactory.minimal_data()["name"],
        "category": CategoryDataFactory.minimal_data()["name"],
        "test_type": "Multi-Turn",
    }
    data.update(overrides)
    return data


def create_test_with_id_request_data(test_id: str, **overrides):
    """Create test execution request data using existing test ID."""
    data = {"test_id": test_id}
    data.update(overrides)
    return data


# ============================================================================
# Test Classes
# ============================================================================


@pytest.mark.unit
@pytest.mark.service
class TestExecuteTestInPlace:
    """Test execute_test_in_place function with various scenarios."""

    def test_execute_existing_single_turn_test(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test execution of an existing single-turn test by test_id."""
        # Create behavior, topic, category
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.flush()

        topic = models.Topic(
            name=TopicDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(topic)
        test_db.flush()

        category = models.Category(
            name=CategoryDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(category)
        test_db.flush()

        # Create prompt
        prompt_data = PromptDataFactory.sample_data()
        prompt = models.Prompt(
            content=prompt_data["content"],
            expected_response=prompt_data["expected_response"],
            language_code=prompt_data["language_code"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(prompt)
        test_db.flush()

        # Create test
        test = models.Test(
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            prompt_id=prompt.id,
            behavior_id=behavior.id,
            topic_id=topic.id,
            category_id=category.id,
            status_id=db_status.id,
            test_type_id=test_type_lookup.id,
        )
        test_db.add(test)
        test_db.commit()

        request_data = create_test_with_id_request_data(str(test.id))

        # Mock the evaluation model and runner
        with (
            patch(
                "rhesis.backend.app.services.test_execution.get_evaluation_model"
            ) as mock_get_model,
            patch(
                "rhesis.backend.app.services.test_execution.SingleTurnRunner"
            ) as mock_runner_class,
        ):
            mock_get_model.return_value = "gpt-4"

            # Mock the runner instance
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.run.return_value = (
                1.23,  # execution_time
                {"response": "Test response"},  # processed_result
                {"accuracy": {"score": 0.95, "is_successful": True}},  # metrics_results
            )

            # Execute the test
            result = test_execution.execute_test_in_place(
                db=test_db,
                request_data=request_data,
                endpoint_id=str(db_endpoint.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                evaluate_metrics=True,
            )

        # Verify result structure
        assert result is not None
        assert "test_id" in result
        assert result["test_id"] == str(test.id)
        assert "prompt_id" in result
        assert result["prompt_id"] == str(prompt.id)
        assert "execution_time" in result
        assert result["execution_time"] == 1.23
        assert "test_output" in result
        assert result["test_output"] == {"response": "Test response"}
        assert "test_metrics" in result
        assert result["test_metrics"]["metrics"]["accuracy"]["is_successful"] is True
        assert "status" in result
        assert result["status"] == ResultStatus.PASS.value

    def test_execute_inline_single_turn_test(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test execution of an inline single-turn test without test_id."""
        # Create behavior for metrics
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.commit()

        request_data = create_single_turn_request_data(behavior=behavior.name)

        # Mock the evaluation model and runner
        with (
            patch(
                "rhesis.backend.app.services.test_execution.get_evaluation_model"
            ) as mock_get_model,
            patch(
                "rhesis.backend.app.services.test_execution.SingleTurnRunner"
            ) as mock_runner_class,
        ):
            mock_get_model.return_value = "gpt-4"

            # Mock the runner instance
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.run.return_value = (
                0.87,  # execution_time
                {"response": "Inline test response"},  # processed_result
                {"accuracy": {"score": 0.88, "is_successful": True}},  # metrics_results
            )

            # Execute the inline test
            result = test_execution.execute_test_in_place(
                db=test_db,
                request_data=request_data,
                endpoint_id=str(db_endpoint.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                evaluate_metrics=True,
            )

        # Verify result structure
        assert result is not None
        assert "test_id" in result
        assert result["test_id"] is not None  # Inline test gets a generated ID
        assert "execution_time" in result
        assert result["execution_time"] == 0.87
        assert "test_output" in result
        assert result["test_output"] == {"response": "Inline test response"}
        assert "test_metrics" in result
        assert result["test_metrics"]["metrics"]["accuracy"]["is_successful"] is True
        assert "status" in result
        assert result["status"] == ResultStatus.PASS.value

    def test_execute_inline_multi_turn_test(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test execution of an inline multi-turn test."""
        # Create behavior for metrics
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.commit()

        request_data = create_multi_turn_request_data(behavior=behavior.name)

        # Mock the evaluation model and runner
        with (
            patch(
                "rhesis.backend.app.services.test_execution.get_evaluation_model"
            ) as mock_get_model,
            patch(
                "rhesis.backend.app.services.test_execution.MultiTurnRunner"
            ) as mock_runner_class,
        ):
            mock_get_model.return_value = "gpt-4"

            # Mock the runner instance
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.run.return_value = (
                2.45,  # execution_time
                {"trace": "Multi-turn conversation trace"},  # penelope_trace
                {"goal_achievement": {"score": 0.92, "is_successful": True}},  # metrics_results
            )

            # Execute the multi-turn test
            result = test_execution.execute_test_in_place(
                db=test_db,
                request_data=request_data,
                endpoint_id=str(db_endpoint.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                evaluate_metrics=True,
            )

        # Verify result structure
        assert result is not None
        assert "test_id" in result
        assert result["test_id"] is not None
        assert "execution_time" in result
        assert result["execution_time"] == 2.45
        assert "test_output" in result
        assert result["test_output"] == {"trace": "Multi-turn conversation trace"}
        assert "test_metrics" in result
        assert result["test_metrics"]["metrics"]["goal_achievement"]["is_successful"] is True
        assert "status" in result
        assert result["status"] == ResultStatus.PASS.value
        assert "test_configuration" in result

    def test_execute_test_without_metrics(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test execution without metric evaluation."""
        # Create behavior
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.commit()

        request_data = create_single_turn_request_data(behavior=behavior.name)

        # Mock the evaluation model and runner
        with (
            patch(
                "rhesis.backend.app.services.test_execution.get_evaluation_model"
            ) as mock_get_model,
            patch(
                "rhesis.backend.app.services.test_execution.SingleTurnRunner"
            ) as mock_runner_class,
        ):
            mock_get_model.return_value = "gpt-4"

            # Mock the runner instance
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.run.return_value = (
                0.55,  # execution_time
                {"response": "Test response"},  # processed_result
                None,  # No metrics
            )

            # Execute without metrics
            result = test_execution.execute_test_in_place(
                db=test_db,
                request_data=request_data,
                endpoint_id=str(db_endpoint.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                evaluate_metrics=False,
            )

        # Verify result structure
        assert result is not None
        assert "test_id" in result
        assert "execution_time" in result
        assert result["execution_time"] == 0.55
        assert "test_output" in result
        assert "test_metrics" in result
        assert result["test_metrics"] is None
        assert "status" in result
        assert result["status"] == ResultStatus.ERROR.value  # Default when no metrics

    def test_execute_test_not_found(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test execution with non-existent test_id."""
        non_existent_id = str(uuid4())
        request_data = create_test_with_id_request_data(non_existent_id)

        # Mock the evaluation model
        with patch(
            "rhesis.backend.app.services.test_execution.get_evaluation_model"
        ) as mock_get_model:
            mock_get_model.return_value = "gpt-4"

            # Should raise ValueError for non-existent test
            with pytest.raises(ValueError, match="Test not found"):
                test_execution.execute_test_in_place(
                    db=test_db,
                    request_data=request_data,
                    endpoint_id=str(db_endpoint.id),
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                    evaluate_metrics=True,
                )

    def test_execute_test_behavior_not_found_inline(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test inline execution when behavior is not found (should proceed without metrics)."""
        request_data = create_single_turn_request_data(behavior="NonExistentBehavior")

        # Mock the evaluation model and runner
        with (
            patch(
                "rhesis.backend.app.services.test_execution.get_evaluation_model"
            ) as mock_get_model,
            patch(
                "rhesis.backend.app.services.test_execution.SingleTurnRunner"
            ) as mock_runner_class,
        ):
            mock_get_model.return_value = "gpt-4"

            # Mock the runner instance
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.run.return_value = (
                0.75,  # execution_time
                {"response": "Test response"},  # processed_result
                {},  # Empty metrics since behavior not found
            )

            # Execute - should not raise error, but log warning
            result = test_execution.execute_test_in_place(
                db=test_db,
                request_data=request_data,
                endpoint_id=str(db_endpoint.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                evaluate_metrics=True,
            )

        # Should complete but without meaningful metrics
        assert result is not None
        assert "test_id" in result
        assert "execution_time" in result

    def test_execute_test_failed_metrics(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test execution with failed metrics."""
        # Create behavior
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.commit()

        request_data = create_single_turn_request_data(behavior=behavior.name)

        # Mock the evaluation model and runner
        with (
            patch(
                "rhesis.backend.app.services.test_execution.get_evaluation_model"
            ) as mock_get_model,
            patch(
                "rhesis.backend.app.services.test_execution.SingleTurnRunner"
            ) as mock_runner_class,
        ):
            mock_get_model.return_value = "gpt-4"

            # Mock the runner instance
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.run.return_value = (
                1.0,  # execution_time
                {"response": "Test response"},  # processed_result
                {"accuracy": {"score": 0.3, "is_successful": False}},  # Failed metrics
            )

            # Execute the test
            result = test_execution.execute_test_in_place(
                db=test_db,
                request_data=request_data,
                endpoint_id=str(db_endpoint.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                evaluate_metrics=True,
            )

        # Verify failure status
        assert result is not None
        assert result["status"] == ResultStatus.FAIL.value
        assert result["test_metrics"]["metrics"]["accuracy"]["is_successful"] is False


@pytest.mark.unit
@pytest.mark.service
class TestCreateInplaceTest:
    """Test _create_inplace_test helper function."""

    def test_create_inline_test_with_behavior(
        self, test_db: Session, authenticated_user_id, test_org_id, test_organization, db_status
    ):
        """Test creating an inline test with behavior lookup."""
        # Create behavior
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.commit()

        request_data = create_single_turn_request_data(behavior=behavior.name)

        # Create inline test
        inline_test = test_execution._create_inplace_test(
            request_data=request_data,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            db=test_db,
        )

        # Verify inline test object
        assert inline_test is not None
        assert inline_test.id is not None
        assert inline_test.organization_id == test_org_id
        assert inline_test.user_id == authenticated_user_id
        assert inline_test.behavior is not None
        assert inline_test.behavior.id == behavior.id
        assert inline_test.prompt == request_data["prompt"]

    def test_create_inline_test_without_behavior(
        self, test_db: Session, authenticated_user_id, test_org_id, test_organization
    ):
        """Test creating an inline test without behavior."""
        request_data = create_single_turn_request_data()
        # Remove behavior to test warning path
        del request_data["behavior"]

        # Create inline test
        inline_test = test_execution._create_inplace_test(
            request_data=request_data,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            db=test_db,
        )

        # Verify inline test object
        assert inline_test is not None
        assert inline_test.id is not None
        assert inline_test.behavior is None
        assert inline_test.behavior_id is None

    def test_create_inline_multi_turn_test(
        self, test_db: Session, authenticated_user_id, test_org_id, test_organization, db_status
    ):
        """Test creating an inline multi-turn test."""
        # Create behavior
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.commit()

        request_data = create_multi_turn_request_data(behavior=behavior.name)

        # Create inline test
        inline_test = test_execution._create_inplace_test(
            request_data=request_data,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            db=test_db,
        )

        # Verify inline test object
        assert inline_test is not None
        assert inline_test.test_configuration is not None
        assert inline_test.test_configuration["goal"] == request_data["test_configuration"]["goal"]
        assert inline_test.behavior is not None

    def test_create_inline_test_auto_detect_type(
        self, test_db: Session, authenticated_user_id, test_org_id, test_organization, db_status
    ):
        """Test auto-detection of test type based on content."""
        # Create behavior
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.commit()

        # Test with goal in config - should detect Multi-Turn
        request_data_multi = {
            "behavior": behavior.name,
            "test_configuration": {"goal": "Test goal"},
        }
        inline_test_multi = test_execution._create_inplace_test(
            request_data=request_data_multi,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            db=test_db,
        )
        assert inline_test_multi.test_type is not None
        assert inline_test_multi.test_type.type_value == "Multi-Turn"

        # Test with prompt - should detect Single-Turn
        request_data_single = {
            "behavior": behavior.name,
            "prompt": {"content": "Test prompt"},
        }
        inline_test_single = test_execution._create_inplace_test(
            request_data=request_data_single,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            db=test_db,
        )
        assert inline_test_single.test_type is not None
        assert inline_test_single.test_type.type_value == "Single-Turn"


@pytest.mark.unit
@pytest.mark.service
class TestExecutionHelpers:
    """Test helper functions for single-turn and multi-turn execution."""

    def test_single_turn_execution_helper(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test _execute_single_turn_in_place helper function."""
        # Create a minimal test object
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.flush()

        prompt = models.Prompt(
            content="Test prompt",
            expected_response="Expected response",
            language_code="en",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(prompt)
        test_db.flush()

        test = models.Test(
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            prompt_id=prompt.id,
            behavior_id=behavior.id,
            status_id=db_status.id,
            test_type_id=test_type_lookup.id,
        )
        test_db.add(test)
        test_db.commit()

        # Mock the runner
        with patch(
            "rhesis.backend.app.services.test_execution.SingleTurnRunner"
        ) as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.run.return_value = (
                1.5,  # execution_time
                {"response": "Test response"},  # processed_result
                {"accuracy": {"score": 0.9, "is_successful": True}},  # metrics_results
            )

            # Execute single-turn
            result = test_execution._execute_single_turn_in_place(
                db=test_db,
                test=test,
                prompt_content="Test prompt",
                expected_response="Expected response",
                endpoint_id=str(db_endpoint.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                model="gpt-4",
                evaluate_metrics=True,
                start_time=datetime.utcnow(),
            )

        # Verify result
        assert result is not None
        assert result["test_id"] == str(test.id)
        assert result["execution_time"] == 1.5
        assert result["test_output"] == {"response": "Test response"}
        assert result["test_metrics"] is not None
        assert result["status"] == ResultStatus.PASS.value

    def test_multi_turn_execution_helper(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test _execute_multi_turn_in_place helper function."""
        # Create a minimal test object
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.flush()

        test = models.Test(
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            behavior_id=behavior.id,
            status_id=db_status.id,
            test_type_id=test_type_lookup.id,
            test_configuration={"goal": "Test goal", "max_turns": 3},
        )
        test_db.add(test)
        test_db.commit()

        # Mock the runner
        with patch(
            "rhesis.backend.app.services.test_execution.MultiTurnRunner"
        ) as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.run.return_value = (
                3.2,  # execution_time
                {"trace": "Multi-turn trace"},  # penelope_trace
                {"goal_achievement": {"score": 0.95, "is_successful": True}},  # metrics_results
            )

            # Execute multi-turn
            result = test_execution._execute_multi_turn_in_place(
                db=test_db,
                test=test,
                endpoint_id=str(db_endpoint.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                model="gpt-4",
                evaluate_metrics=True,
                start_time=datetime.utcnow(),
            )

        # Verify result
        assert result is not None
        assert result["test_id"] == str(test.id)
        assert result["execution_time"] == 3.2
        assert result["test_output"] == {"trace": "Multi-turn trace"}
        assert result["test_metrics"] is not None
        assert result["status"] == ResultStatus.PASS.value
        assert result["test_configuration"] == {"goal": "Test goal", "max_turns": 3}


@pytest.mark.unit
@pytest.mark.service
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_execute_with_special_characters_in_prompt(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test execution with special characters in prompt."""
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.commit()

        request_data = create_single_turn_request_data(
            behavior=behavior.name,
            prompt={
                "content": "Test with émoji 🧪 and spëcial chars! @#$%^&*()",
                "expected_response": "Response with 测试 тест テスト",
            },
        )

        # Mock the evaluation model and runner
        with (
            patch(
                "rhesis.backend.app.services.test_execution.get_evaluation_model"
            ) as mock_get_model,
            patch(
                "rhesis.backend.app.services.test_execution.SingleTurnRunner"
            ) as mock_runner_class,
        ):
            mock_get_model.return_value = "gpt-4"

            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.run.return_value = (
                0.9,
                {"response": "Special char response"},
                {"accuracy": {"score": 0.85, "is_successful": True}},
            )

            result = test_execution.execute_test_in_place(
                db=test_db,
                request_data=request_data,
                endpoint_id=str(db_endpoint.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                evaluate_metrics=True,
            )

        # Should handle special characters correctly
        assert result is not None
        assert result["status"] == ResultStatus.PASS.value

    def test_execute_with_empty_prompt(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test execution with empty prompt content."""
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.commit()

        request_data = create_single_turn_request_data(
            behavior=behavior.name, prompt={"content": "", "expected_response": ""}
        )

        # Mock the evaluation model and runner
        with (
            patch(
                "rhesis.backend.app.services.test_execution.get_evaluation_model"
            ) as mock_get_model,
            patch(
                "rhesis.backend.app.services.test_execution.SingleTurnRunner"
            ) as mock_runner_class,
        ):
            mock_get_model.return_value = "gpt-4"

            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.run.return_value = (0.5, {"response": "Empty prompt response"}, {})

            result = test_execution.execute_test_in_place(
                db=test_db,
                request_data=request_data,
                endpoint_id=str(db_endpoint.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                evaluate_metrics=False,
            )

        # Should handle empty prompt
        assert result is not None
        assert "test_id" in result

    def test_execute_with_complex_test_configuration(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
        db_endpoint,
    ):
        """Test execution with complex multi-turn configuration."""
        behavior = models.Behavior(
            name=BehaviorDataFactory.minimal_data()["name"],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=db_status.id,
        )
        test_db.add(behavior)
        test_db.commit()

        request_data = create_multi_turn_request_data(
            behavior=behavior.name,
            test_configuration={
                "goal": "Complex multi-turn goal with nested data",
                "max_turns": 5,
                "success_criteria": "Multiple criteria to meet",
                "context": {
                    "scenario": "Complex scenario",
                    "constraints": ["Constraint 1", "Constraint 2"],
                    "metadata": {"key1": "value1", "key2": "value2"},
                },
            },
        )

        # Mock the evaluation model and runner
        with (
            patch(
                "rhesis.backend.app.services.test_execution.get_evaluation_model"
            ) as mock_get_model,
            patch(
                "rhesis.backend.app.services.test_execution.MultiTurnRunner"
            ) as mock_runner_class,
        ):
            mock_get_model.return_value = "gpt-4"

            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.run.return_value = (
                5.5,
                {"trace": "Complex multi-turn trace"},
                {"goal_achievement": {"score": 0.88, "passed": True}},
            )

            result = test_execution.execute_test_in_place(
                db=test_db,
                request_data=request_data,
                endpoint_id=str(db_endpoint.id),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                evaluate_metrics=True,
            )

        # Should handle complex configuration
        assert result is not None
        assert result["test_configuration"] is not None
        assert "goal" in result["test_configuration"]
