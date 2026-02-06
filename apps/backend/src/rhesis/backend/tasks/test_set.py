import logging
from typing import List, Optional, Union

from rhesis.backend.app import crud
from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL
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
from rhesis.sdk.synthesizers import ConfigSynthesizer, MultiTurnSynthesizer

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
    from rhesis.backend.app.schemas.test_set import TestData

    converted_tests = []
    for test in test_set.tests:
        # Get dict from test (handles both dict and Pydantic model)
        if isinstance(test, dict):
            test_dict = test.copy()
        else:
            test_dict = test.model_dump(exclude={"id", "endpoint"})

        # Ensure required string fields have values (TestData requires non-None)
        test_dict["behavior"] = test_dict.get("behavior") or ""
        test_dict["category"] = test_dict.get("category") or ""
        test_dict["topic"] = test_dict.get("topic") or ""

        converted_tests.append(TestData(**test_dict))

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
            test_set_type=test_set.test_set_type,  # ConfigSynthesizer generates single-turn tests
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
    test_type: Optional[str] = "single_turn",
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
        if test_type == "single_turn":
            synthesizer = ConfigSynthesizer(
                config=generation_config,  # ✅ Full config including all fields
                batch_size=batch_size,
                model=model,
                sources=source_specifications if source_specifications else None,
            )
        elif test_type == "multi_turn":
            synthesizer = MultiTurnSynthesizer(
                config=generation_config,
                model=model,
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

    except ValueError as e:
        error_msg = str(e)
        error_msg_lower = error_msg.lower()

        # Check for various model configuration issues
        if any(
            keyword in error_msg_lower
            for keyword in [
                "api_key",
                "not set",
                "not configured",
                "api key",
                "authentication",
                "provider",
                "not supported",
                "model",
                "not found",
                "invalid",
            ]
        ):
            self.log_with_context("error", "User model configuration error", error=error_msg)
            raise ValueError(
                f"Cannot generate tests due to a problem with your configured model: {error_msg}. "
                "Please check your model settings in the Models page."
            )
        # Other configuration errors
        self.log_with_context("error", "Configuration error", error=error_msg)
        raise ValueError(f"Test set generation failed: {error_msg}")
    except Exception as e:
        self.log_with_context("error", "Task failed", error=str(e))
        # The task will be automatically retried due to BaseTask settings
        raise Exception(f"Test set generation and save failed: {str(e)}")
