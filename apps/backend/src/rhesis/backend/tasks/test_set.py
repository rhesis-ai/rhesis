import logging
import os

from rhesis.backend.app import crud
from rhesis.backend.app.crud import get_user_tokens
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.tasks.base import BaseTask, with_tenant_context
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
@with_tenant_context
def count_test_sets(self, db=None):
    """
    Task that counts the total number of test sets in the database.

    Using the with_tenant_context decorator, this task automatically:
    1. Creates a database session
    2. Sets the tenant context from the task headers
    3. Passes the session to the task function
    4. Closes the session when done

    All database operations will have the correct tenant context automatically.
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()

    self.log_with_context("info", "Starting count_test_sets task")

    try:
        # Update task state to show progress
        self.update_state(state="PROGRESS", meta={"status": "Counting test sets"})
        self.log_with_context("info", "Starting database queries")

        # Get all test sets with the proper tenant context
        # The db session is already configured with the tenant context by the decorator
        test_sets = crud.get_test_sets(db)
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


@app.task(
    base=BaseTask,
    name="rhesis.backend.tasks.generate_and_upload_test_set",
    bind=True,
    display_name="Generate and Upload Test Set",
)
@with_tenant_context
def generate_and_upload_test_set(
    self,
    synthesizer_type: str,
    num_tests: int = 5,
    batch_size: int = 20,
    db=None,
    **synthesizer_kwargs,
):
    """
    Task that generates test cases using SDK synthesizers and uploads them as a test set.

    This task is flexible and can work with any synthesizer type by accepting arbitrary
    parameters through **synthesizer_kwargs.

    Args:
        synthesizer_type: Type of synthesizer to use (e.g., "prompt", "paraphrasing")
        num_tests: Number of test cases to generate (default: 5)
        batch_size: Batch size for the synthesizer (default: 20)
        db: Database session (provided by decorator)
        **synthesizer_kwargs: Additional parameters specific to the synthesizer type
            For PromptSynthesizer:
                - prompt (str, required): The generation prompt
                - documents (List[Dict], optional): List of documents with:
                    - name (str): Document identifier
                    - description (str): Document description
                    - path (str): Local file path from upload endpoint
                    - content (str, optional): Pre-provided content
            For ParaphrasingSynthesizer: source_test_set_id (str, required)
            Any future synthesizers can define their own required parameters

    Returns:
        dict: Information about the generated and uploaded test set including ID and metadata

    Examples:
        # Using PromptSynthesizer
        generate_and_upload_test_set.delay(
            synthesizer_type="prompt",
            prompt="Generate math tests",
            num_tests=10
        )

        # Using ParaphrasingSynthesizer
        generate_and_upload_test_set.delay(
            synthesizer_type="paraphrasing",
            source_test_set_id="test-set-123",
            num_tests=5
        )
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()

    # Log the parameters (safely, without exposing sensitive data)
    log_kwargs = {k: v for k, v in synthesizer_kwargs.items() if not k.lower().endswith("_key")}
    self.log_with_context(
        "info",
        "Starting generate_and_upload_test_set task",
        num_tests=num_tests,
        synthesizer_type=synthesizer_type,
        synthesizer_params=list(log_kwargs.keys()),
    )

    try:
        # Update task state to show progress
        self.update_state(
            state="PROGRESS", meta={"status": "Initializing SDK and getting user tokens"}
        )

        # Get user tokens for SDK authentication
        tokens = get_user_tokens(db, user_id, valid_only=True)
        if not tokens:
            raise ValueError("No valid API tokens found for user. Please create a new API token.")

        # Configure SDK using the factory method
        base_url = os.getenv("RHESIS_BASE_URL", "https://api.rhesis.ai")
        SynthesizerFactory.configure_sdk(base_url=base_url, api_key=tokens[0].token)

        self.log_with_context("info", "SDK configured", base_url=base_url)

        # Update task state
        self.update_state(state="PROGRESS", meta={"status": "Initializing synthesizer"})

        # Override synthesizer type if documents are provided
        if "documents" in synthesizer_kwargs and synthesizer_kwargs["documents"]:
            # Automatically use DocumentSynthesizer when documents are provided
            synth_type = SynthesizerType.DOCUMENT
            self.log_with_context(
                "info",
                f"Documents detected, using DocumentSynthesizer instead of {synthesizer_type}",
            )
        else:
            # Convert string to enum and validate
            try:
                synth_type = SynthesizerType(synthesizer_type.lower())
            except ValueError:
                supported_types = SynthesizerFactory.get_supported_types()
                raise ValueError(
                    f"Unsupported synthesizer type: {synthesizer_type}."
                    f"Supported types: {', '.join(supported_types)}"
                )

        # Prepare synthesizer parameters based on type
        processed_kwargs = {}

        # Handle special parameters that need processing
        if (
            synth_type == SynthesizerType.PARAPHRASING
            and "source_test_set_id" in synthesizer_kwargs
        ):
            # Load the source test set for paraphrasing synthesizer
            source_test_set_id = synthesizer_kwargs["source_test_set_id"]
            source_test_set = SynthesizerFactory.load_source_test_set(source_test_set_id)
            processed_kwargs["test_set"] = source_test_set
            # Remove the original parameter since we've processed it
            processed_kwargs.update(
                {k: v for k, v in synthesizer_kwargs.items() if k != "source_test_set_id"}
            )
        else:
            # For other synthesizers, pass parameters as-is
            processed_kwargs = synthesizer_kwargs

        # Create the synthesizer using the factory
        synthesizer = SynthesizerFactory.create_synthesizer(
            synthesizer_type=synth_type, batch_size=batch_size, **processed_kwargs
        )

        self.log_with_context(
            "info",
            "Synthesizer initialized",
            synthesizer_type=synthesizer_type,
            synthesizer_class=synthesizer.__class__.__name__,
        )

        # Update task state
        self.update_state(state="PROGRESS", meta={"status": f"Generating {num_tests} test cases"})

        # Generate the test set
        test_set = synthesizer.generate(num_tests=num_tests)

        self.log_with_context(
            "info",
            "Test set generated",
            actual_tests_generated=len(test_set.tests),
            requested_tests=num_tests,
        )

        # Update task state
        self.update_state(state="PROGRESS", meta={"status": "Uploading test set to API"})

        # Upload the test set
        test_set.upload()

        self.log_with_context(
            "info",
            "Test set uploaded successfully",
            test_set_id=test_set.id,
            test_set_name=test_set.name,
        )

        # Prepare result with comprehensive information
        result = {
            "test_set_id": test_set.id,
            "test_set_name": test_set.name,
            "description": test_set.description,
            "short_description": test_set.short_description,
            "num_tests_generated": len(test_set.tests),
            "num_tests_requested": num_tests,
            "synthesizer_type": synthesizer_type,
            "synthesizer_class": synthesizer.__class__.__name__,
            "synthesizer_params": log_kwargs,  # Safe parameters for logging
            "batch_size": batch_size,
            "metadata": test_set.metadata,
            "organization_id": org_id,
            "user_id": user_id,
            "upload_successful": True,
        }

        self.log_with_context(
            "info",
            "Task completed successfully",
            test_set_id=test_set.id,
            tests_generated=len(test_set.tests),
        )

        return result

    except Exception as e:
        self.log_with_context("error", "Task failed", error=str(e))
        # Return error information for debugging
        error_result = {
            "upload_successful": False,
            "error": str(e),
            "num_tests_requested": num_tests,
            "synthesizer_type": synthesizer_type,
            "synthesizer_params": log_kwargs,  # Safe parameters for logging
            "organization_id": org_id,
            "user_id": user_id,
        }
        # The task will be automatically retried due to BaseTask settings
        raise Exception(f"Test set generation and upload failed: {str(e)}")
