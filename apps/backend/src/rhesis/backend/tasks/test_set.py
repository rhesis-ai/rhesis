import logging
import os

from rhesis.backend.app import crud
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.services.test_set import bulk_create_test_set
from rhesis.backend.tasks.base import BaseTask
from rhesis.backend.worker import app

# Import SDK components for test generation
from rhesis.sdk.synthesizers import SynthesizerFactory, SynthesizerType

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
def _configure_synthesizer_sdk(self) -> str:
    """Configure the SDK for synthesizer operations."""
    base_url = os.getenv("RHESIS_BASE_URL", "https://api.rhesis.ai")
    SynthesizerFactory.configure_sdk(base_url=base_url, api_key="")
    self.log_with_context("info", "SDK configured", base_url=base_url)
    return base_url


def _determine_synthesizer_type(
    self, synthesizer_type: str, synthesizer_kwargs: dict
) -> SynthesizerType:
    """Determine the appropriate synthesizer type based on input parameters."""
    if synthesizer_kwargs.get("documents"):
        # Automatically use DocumentSynthesizer when documents are provided
        self.log_with_context(
            "info",
            f"Documents detected, using DocumentSynthesizer instead of {synthesizer_type}",
        )
        return SynthesizerType.DOCUMENT

    # Convert string to enum and validate
    try:
        return SynthesizerType(synthesizer_type.lower())
    except ValueError:
        supported_types = SynthesizerFactory.get_supported_types()
        raise ValueError(
            f"Unsupported synthesizer type: {synthesizer_type}. "
            f"Supported types: {', '.join(supported_types)}"
        )


def _process_synthesizer_parameters(
    self, synth_type: SynthesizerType, synthesizer_kwargs: dict
) -> dict:
    """Process and prepare synthesizer parameters based on type."""
    if synth_type == SynthesizerType.PARAPHRASING and "source_test_set_id" in synthesizer_kwargs:
        # Load the source test set for paraphrasing synthesizer
        source_test_set_id = synthesizer_kwargs["source_test_set_id"]
        source_test_set = SynthesizerFactory.load_source_test_set(source_test_set_id)
        processed_kwargs = {"test_set": source_test_set}
        # Add other parameters except the processed one
        processed_kwargs.update(
            {k: v for k, v in synthesizer_kwargs.items() if k != "source_test_set_id"}
        )
        return processed_kwargs

    # For other synthesizers, pass parameters as-is
    return synthesizer_kwargs


def _create_synthesizer(self, synth_type: SynthesizerType, batch_size: int, processed_kwargs: dict):
    """Create and initialize the synthesizer."""
    synthesizer = SynthesizerFactory.create_synthesizer(
        synthesizer_type=synth_type, batch_size=batch_size, model="gemini", **processed_kwargs
    )

    self.log_with_context(
        "info",
        "Synthesizer initialized",
        synthesizer_type=synth_type.value,
        synthesizer_class=synthesizer.__class__.__name__,
    )

    return synthesizer


def _save_test_set_to_database(self, test_set, org_id: str, user_id: str):
    """Save the generated test set directly to the database."""
    if not test_set.tests:
        raise ValueError("No tests to save. Please add tests to the test set first.")

    test_set_data = {
        "name": test_set.name,
        "description": test_set.description,
        "short_description": test_set.short_description,
        "metadata": test_set.metadata,
        "tests": test_set.tests,
    }

    with self.get_db_session() as db:
        db_test_set = bulk_create_test_set(
            db=db,
            test_set_data=test_set_data,
            organization_id=org_id,
            user_id=user_id,
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


def _build_task_result(
    self,
    db_test_set,
    num_tests: int,
    synthesizer_type: str,
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
        "synthesizer_type": synthesizer_type,
        "synthesizer_class": synthesizer.__class__.__name__,
        "synthesizer_params": log_kwargs,  # Safe parameters for logging
        "batch_size": batch_size,
        "metadata": db_test_set.attributes.get("metadata", {}) if db_test_set.attributes else {},
        "organization_id": org_id,
        "user_id": user_id,
        "save_successful": True,
    }


@app.task(
    base=BaseTask,
    name="rhesis.backend.tasks.generate_and_save_test_set",
    bind=True,
    display_name="Generate and Save Test Set",
)
def generate_and_save_test_set(
    self,
    synthesizer_type: str,
    num_tests: int = 5,
    batch_size: int = 20,
    **synthesizer_kwargs,
):
    """
    Task that generates test cases using SDK synthesizers and saves them directly to the database.

    This task is flexible and can work with any synthesizer type by accepting arbitrary
    parameters through **synthesizer_kwargs.

    Args:
        synthesizer_type: Type of synthesizer to use (e.g., "prompt", "paraphrasing")
        num_tests: Number of test cases to generate (default: 5)
        batch_size: Batch size for the synthesizer (default: 20)
        **synthesizer_kwargs: Additional parameters specific to the synthesizer type
            For PromptSynthesizer:
                - prompt (str, required): The generation prompt
            For DocumentSynthesizer:
                - prompt (str, required): The generation prompt
                - documents (List[Document], optional): List of documents with:
                    - name (str): Document identifier
                    - description (str): Document description
                    - path (str): Local file path from upload endpoint
                    - content (str, optional): Pre-provided content
            For ParaphrasingSynthesizer: source_test_set_id (str, required)
            Any future synthesizers can define their own required parameters

    Returns:
        dict: Information about the generated and saved test set including ID and metadata

    Examples:
        # Using PromptSynthesizer
        generate_and_save_test_set.delay(
            synthesizer_type="prompt",
            prompt="Generate insurance claim tests",
            num_tests=10
        )

        # Using ParaphrasingSynthesizer
        generate_and_save_test_set.delay(
            synthesizer_type="paraphrasing",
            source_test_set_id="test-set-123",
            num_tests=5
        )

        # Using DocumentSynthesizer
        generate_and_save_test_set.delay(
            synthesizer_type="document",
            prompt="Generate insurance claim tests",
            documents=[{
                "name": "policy_doc.pdf",
                "description": "Insurance policy terms",
                "path": "/uploads/policy_doc.pdf"
            }],
            num_tests=10
        )
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()

    # Log the parameters (safely, without exposing sensitive data)
    log_kwargs = {k: v for k, v in synthesizer_kwargs.items() if not k.lower().endswith("_key")}
    self.log_with_context(
        "info",
        "Starting generate_and_save_test_set task",
        num_tests=num_tests,
        synthesizer_type=synthesizer_type,
        synthesizer_params=list(log_kwargs.keys()),
    )

    try:
        # Step 1: Configure SDK
        self.update_state(state="PROGRESS", meta={"status": "Initializing synthesizer"})
        _configure_synthesizer_sdk(self)

        # Step 2: Determine synthesizer type
        synth_type = _determine_synthesizer_type(self, synthesizer_type, synthesizer_kwargs)

        # Step 3: Process parameters
        processed_kwargs = _process_synthesizer_parameters(self, synth_type, synthesizer_kwargs)

        # Step 4: Create synthesizer
        synthesizer = _create_synthesizer(self, synth_type, batch_size, processed_kwargs)

        # Step 5: Generate test set
        self.update_state(state="PROGRESS", meta={"status": f"Generating {num_tests} test cases"})
        test_set = synthesizer.generate(num_tests=num_tests)

        self.log_with_context(
            "info",
            "Test set generated",
            actual_tests_generated=len(test_set.tests),
            requested_tests=num_tests,
        )

        # Step 6: Save to database
        self.update_state(state="PROGRESS", meta={"status": "Saving test set to database"})
        db_test_set = _save_test_set_to_database(self, test_set, org_id, user_id)

        # Step 7: Build and return result
        result = _build_task_result(
            self,
            db_test_set,
            num_tests,
            synthesizer_type,
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
