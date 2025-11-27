import logging
from typing import List, Optional, Union

from rhesis.backend.app import crud
from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL, TestType
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.schemas.services import GenerationConfig, SourceData
from rhesis.backend.app.services.generation import get_source_specifications
from rhesis.backend.app.services.test_set import bulk_create_test_set
from rhesis.backend.app.utils.llm_utils import get_user_generation_model
from rhesis.backend.notifications.email.template_service import EmailTemplate
from rhesis.backend.tasks.base import BaseTask, email_notification
from rhesis.backend.worker import app

# Import SDK components for test generation
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers import ConfigSynthesizer

# Set up logging
logger = logging.getLogger(__name__)


@app.task(
    base=BaseTask,
    name="rhesis.backend.tasks.count_test_sets",
    bind=True,
    display_name="Test Set Count",
)
# with_tenant_context decorator removed - tenant context now passed directly
def count_test_sets(self):
    """
    Task that counts the total number of test sets in the database.

    This task gets tenant context passed directly and uses get_db_with_tenant_variables
    for explicit tenant context.
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()

    self.log_with_context("info", "Starting count_test_sets task")

    try:
        # Update task state to show progress
        self.update_state(state="PROGRESS", meta={"status": "Counting test sets"})
        self.log_with_context("info", "Starting database queries")

        # Use tenant-aware database session with explicit organization_id and user_id
        with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
            # Get all test sets with the proper tenant context
            test_sets = crud.get_test_sets(db, organization_id=org_id, user_id=user_id)
            total_count = len(test_sets)
            self.log_with_context("info", "Total test sets counted", total_count=total_count)

            # Get counts by visibility
            public_count = db.query(TestSet).filter(TestSet.visibility == "public").count()
            private_count = db.query(TestSet).filter(TestSet.visibility == "private").count()
        self.log_with_context(
            "info",
            "Visibility counts retrieved",
            public_count=public_count,
            private_count=private_count,
        )

        # Get counts by published status
        published_count = db.query(TestSet).filter(TestSet.is_published).count()
        unpublished_count = db.query(TestSet).filter(~TestSet.is_published).count()
        self.log_with_context(
            "info",
            "Published status counts retrieved",
            published_count=published_count,
            unpublished_count=unpublished_count,
        )

        result = {
            "total_count": total_count,
            "by_visibility": {"public": public_count, "private": private_count},
            "by_status": {"published": published_count, "unpublished": unpublished_count},
            "organization_id": org_id,
            "user_id": user_id,
        }

        self.log_with_context(
            "info",
            "Task completed successfully",
            total_count=total_count,
            public_count=public_count,
            private_count=private_count,
        )
        return result

    except Exception as e:
        self.log_with_context("error", "Task failed", error=str(e))
        # The task will be automatically retried due to BaseTask settings
        raise


# Helper functions for test set generation and saving


def _save_test_set_to_database(
    self,
    test_set,
    org_id: str,
    user_id: str,
    custom_name: str = None,
):
    """Save the generated test set directly to the database.

    Args:
        test_set: The SDK TestSet with generated tests
        org_id: Organization ID
        user_id: User ID
        custom_name: Optional custom name to use instead of auto-generated name

    Note:
        Source IDs are automatically embedded in test metadata via SourceSpecification.
        The SDK propagates metadata from SourceSpecification to each generated test,
        so no manual mapping is needed.
    """
    if not test_set.tests:
        raise ValueError("No tests to save. Please add tests to the test set first.")

    # Convert SDK Test objects/dicts to TestData format
    from rhesis.backend.app.schemas.test_set import TestData, TestPrompt

    converted_tests = []
    for test in test_set.tests:
        # Handle both dict and Test object formats
        if isinstance(test, dict):
            test_dict = test
        else:
            # Convert Test object to dict
            if hasattr(test, "model_dump"):
                test_dict = test.model_dump()
            elif hasattr(test, "__dict__"):
                test_dict = test.__dict__.copy()
            else:
                # Fallback: try to access attributes directly
                test_dict = {
                    "prompt": getattr(test, "prompt", None),
                    "behavior": getattr(test, "behavior", None),
                    "category": getattr(test, "category", None),
                    "topic": getattr(test, "topic", None),
                    "test_type": getattr(test, "test_type", None),
                    "test_configuration": getattr(test, "test_configuration", None),
                    "metadata": getattr(test, "metadata", {}),
                    "assignee_id": getattr(test, "assignee_id", None),
                    "owner_id": getattr(test, "owner_id", None),
                    "status": getattr(test, "status", None),
                    "priority": getattr(test, "priority", None),
                }

        # Extract prompt data
        prompt_data = None
        if test_dict.get("prompt"):
            prompt = test_dict["prompt"]
            # Handle both dict and Prompt object formats
            if isinstance(prompt, dict):
                prompt_dict = prompt
            else:
                # Convert Prompt object to dict
                if hasattr(prompt, "model_dump"):
                    prompt_dict = prompt.model_dump()
                elif hasattr(prompt, "__dict__"):
                    prompt_dict = prompt.__dict__.copy()
                else:
                    # Fallback: access attributes directly
                    prompt_dict = {
                        "content": getattr(prompt, "content", ""),
                        "language_code": getattr(prompt, "language_code", "en"),
                        "expected_response": getattr(prompt, "expected_response", None),
                        "demographic": getattr(prompt, "demographic", None),
                        "dimension": getattr(prompt, "dimension", None),
                    }

            prompt_data = TestPrompt(
                content=prompt_dict.get("content", ""),
                language_code=prompt_dict.get("language_code", "en"),
                expected_response=prompt_dict.get("expected_response"),
                demographic=prompt_dict.get("demographic"),
                dimension=prompt_dict.get("dimension"),
            )

        # Convert test_type if it's an enum
        test_type_value = test_dict.get("test_type")
        if test_type_value is not None:
            # Handle TestType enum - convert to string value
            if hasattr(test_type_value, "value"):
                test_type_value = test_type_value.value
            elif not isinstance(test_type_value, str):
                test_type_value = str(test_type_value)

        # Convert test_configuration if it's an object
        test_configuration_value = test_dict.get("test_configuration")
        if test_configuration_value is not None and not isinstance(test_configuration_value, dict):
            # Convert TestConfiguration object to dict
            if hasattr(test_configuration_value, "model_dump"):
                test_configuration_value = test_configuration_value.model_dump()
            elif hasattr(test_configuration_value, "__dict__"):
                test_configuration_value = test_configuration_value.__dict__.copy()

        # Build TestData dict
        test_data_dict = {
            "prompt": prompt_data,
            "behavior": test_dict.get("behavior", ""),
            "category": test_dict.get("category", ""),
            "topic": test_dict.get("topic", ""),
            "test_type": test_type_value,
            "test_configuration": test_configuration_value,
            "metadata": test_dict.get("metadata", {}),
        }

        # Only include optional fields if they exist
        if test_dict.get("assignee_id"):
            test_data_dict["assignee_id"] = test_dict["assignee_id"]
        if test_dict.get("owner_id"):
            test_data_dict["owner_id"] = test_dict["owner_id"]
        if test_dict.get("status"):
            test_data_dict["status"] = test_dict["status"]
        if test_dict.get("priority") is not None:
            test_data_dict["priority"] = test_dict["priority"]

        converted_tests.append(TestData(**test_data_dict))

    test_set_data = {
        "name": custom_name if custom_name else test_set.name,
        "description": test_set.description,
        "short_description": test_set.short_description,
        "metadata": test_set.metadata,
        "tests": converted_tests,
    }

    with self.get_db_session() as db:
        db_test_set = bulk_create_test_set(
            db=db,
            test_set_data=test_set_data,
            organization_id=org_id,
            user_id=user_id,
            test_set_type=TestType.SINGLE_TURN,  # ConfigSynthesizer generates single-turn tests
        )

        # Note: We don't set the SDK test_set.id because:
        # 1. The database auto-generates the ID
        # 2. The SDK TestSet is just used for generation, not as a database entity
        # 3. We'll use the db_test_set.id for our return result instead

    self.log_with_context(
        "info",
        "Test set saved successfully to database",
        test_set_id=str(db_test_set.id),
        test_set_name=db_test_set.name,
    )

    return db_test_set


def _get_model_for_user(self, org_id: str, user_id: str) -> Union[str, BaseLLM]:
    """
    Fetch user's configured generation model from database.

    Args:
        org_id: Organization ID
        user_id: User ID

    Returns:
        Either the user's configured BaseLLM instance or DEFAULT_GENERATION_MODEL string
    """
    self.log_with_context("info", "Fetching user's configured generation model")
    with get_db_with_tenant_variables(org_id, user_id) as db:
        # Get the user from database (user_id from context is already a UUID string)
        user = crud.get_user(db, user_id=user_id)
        if user:
            model = get_user_generation_model(db, user)
            self.log_with_context(
                "info",
                "Using user's configured model",
                model_type=type(model).__name__ if not isinstance(model, str) else "string",
            )
            return model
        else:
            # Fallback to default if user not found
            self.log_with_context(
                "warning", "User not found, using default model", model=DEFAULT_GENERATION_MODEL
            )
            return DEFAULT_GENERATION_MODEL


def _build_task_result(
    self,
    db_test_set,
    num_tests: int,
    synthesizer,
    log_kwargs: dict,
    batch_size: int,
    org_id: str,
    user_id: str,
) -> dict:
    """Build the comprehensive task result dictionary."""
    return {
        "test_set_id": str(db_test_set.id),
        "test_set_name": db_test_set.name,
        "description": db_test_set.description,
        "short_description": db_test_set.short_description,
        "num_tests_generated": len(db_test_set.tests),
        "num_tests_requested": num_tests,
        "synthesizer_class": synthesizer.__class__.__name__,
        "synthesizer_params": log_kwargs,  # Safe parameters for logging
        "batch_size": batch_size,
        "metadata": db_test_set.attributes.get("metadata", {}) if db_test_set.attributes else {},
        "organization_id": org_id,
        "user_id": user_id,
        "save_successful": True,
    }


@email_notification(
    template=EmailTemplate.TASK_COMPLETION,
    subject_template="Test Set Generation Complete: {task_name} - {status}",
)
@app.task(
    base=BaseTask,
    name="rhesis.backend.tasks.generate_and_save_test_set",
    bind=True,
    display_name="Generate and Save Test Set",
)
def generate_and_save_test_set(
    self,
    config: dict,
    num_tests: int,
    batch_size: int = 20,
    sources: Optional[List[dict]] = None,
    name: Optional[str] = None,
):
    """
    Generate and save test set using ConfigSynthesizer.

    This task uses the SAME logic as the services endpoint for consistency.

    Args:
        config: GenerationConfig as dict (will be converted to GenerationConfig)
        num_tests: Number of tests to generate
        batch_size: Batch size for generation (default: 20)
        sources: Optional list of SourceData dicts with IDs
        name: Optional custom name for test set

    Returns:
        dict: Information about the generated and saved test set including ID and metadata
    """
    org_id, user_id = self.get_tenant_context()

    # Parse config
    generation_config = GenerationConfig(**config)

    # Log the parameters (safely, without exposing sensitive data)
    log_kwargs = {k: v for k, v in config.items() if not k.lower().endswith("_key")}

    # Get SDK source specifications (with embedded source IDs)
    source_specifications = []

    if sources:
        with self.get_db_session() as db:
            source_specifications = get_source_specifications(
                sources=[SourceData(**s) for s in sources],
                db=db,
                organization_id=org_id,
                user_id=user_id,
            )

    # Get user's model
    model = _get_model_for_user(self, org_id, user_id)

    # Determine model info for logging
    model_info = model if isinstance(model, str) else f"{type(model).__name__} instance"

    self.log_with_context(
        "info",
        "Starting generate_and_save_test_set task",
        num_tests=num_tests,
        model=model_info,
        synthesizer_params=list(log_kwargs.keys()),
    )

    try:
        # Generate test set
        self.update_state(state="PROGRESS", meta={"status": f"Generating {num_tests} tests"})

        # Create synthesizer with full config
        synthesizer = ConfigSynthesizer(
            config=generation_config,  # ✅ Full config including all fields
            batch_size=batch_size,
            model=model,
            sources=source_specifications if source_specifications else None,
        )

        test_set = synthesizer.generate(num_tests=num_tests)

        self.log_with_context(
            "info",
            "Test set generated",
            actual_tests_generated=len(test_set.tests),
            requested_tests=num_tests,
        )

        # Note: Source IDs are already embedded in test metadata via SourceSpecification
        # The SDK automatically propagates metadata from SourceSpecification to generated tests

        # Save to database
        self.update_state(state="PROGRESS", meta={"status": "Saving to database"})
        db_test_set = _save_test_set_to_database(
            self,
            test_set,
            org_id,
            user_id,
            custom_name=name,
        )

        # Build and return result
        result = _build_task_result(
            self,
            db_test_set,
            num_tests,
            synthesizer,
            log_kwargs,
            batch_size,
            org_id,
            user_id,
        )

        self.log_with_context(
            "info",
            "Task completed successfully",
            test_set_id=str(db_test_set.id),
            tests_generated=len(test_set.tests),
        )

        return result

    except Exception as e:
        self.log_with_context("error", "Task failed", error=str(e))
        # The task will be automatically retried due to BaseTask settings
        raise Exception(f"Test set generation and save failed: {str(e)}")
