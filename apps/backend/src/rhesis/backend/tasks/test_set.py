import logging
from typing import Union

from rhesis.backend.app import crud
from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.services.generation import (
    process_sources_to_documents,
)
from rhesis.backend.app.services.test_set import bulk_create_test_set
from rhesis.backend.app.utils.llm_utils import get_user_generation_model
from rhesis.backend.notifications.email.template_service import EmailTemplate
from rhesis.backend.tasks.base import BaseTask, email_notification
from rhesis.backend.worker import app

# Import SDK components for test generation
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers import ConfigSynthesizer, SynthesizerFactory, SynthesizerType
from rhesis.sdk.synthesizers.config_synthesizer import GenerationConfig

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


def _create_synthesizer(
    self,
    synth_type: SynthesizerType,
    batch_size: int,
    model: Union[str, BaseLLM],
    processed_kwargs: dict,
):
    """Create and initialize the synthesizer."""
    synthesizer = SynthesizerFactory.create_synthesizer(
        synthesizer_type=synth_type, batch_size=batch_size, model=model, **processed_kwargs
    )

    # Determine model info for logging
    model_info = model if isinstance(model, str) else f"{type(model).__name__} instance"

    self.log_with_context(
        "info",
        "Synthesizer initialized",
        synthesizer_type=synth_type.value,
        synthesizer_class=synthesizer.__class__.__name__,
        model=model_info,
    )

    return synthesizer


def _save_test_set_to_database(
    self,
    test_set,
    org_id: str,
    user_id: str,
    custom_name: str = None,
    source_ids: list = None,
    source_ids_to_documents: dict = None,
):
    """Save the generated test set directly to the database.

    Args:
        test_set: The SDK TestSet with generated tests
        org_id: Organization ID
        user_id: User ID
        custom_name: Optional custom name to use instead of auto-generated name
        source_ids: List of source_ids in order corresponding to documents
        source_ids_to_documents: Optional mapping of document names to source_ids
    """
    if not test_set.tests:
        raise ValueError("No tests to save. Please add tests to the test set first.")

    # If we have source_ids, add them to each test based on document name in metadata
    if source_ids and source_ids_to_documents:
        for i, test in enumerate(test_set.tests):
            # Try to access metadata - tests can be dict or object
            test_metadata = (
                test.get("metadata", {})
                if isinstance(test, dict)
                else getattr(test, "metadata", {})
            )

            if test_metadata and "sources" in test_metadata:
                sources = test_metadata.get("sources", [])
                if sources and "name" in sources[0]:
                    doc_name = sources[0]["name"]
                    if doc_name in source_ids_to_documents:
                        # Add source_id to the test metadata for later extraction
                        source_id = source_ids_to_documents[doc_name]
                        if isinstance(test, dict):
                            if "metadata" not in test:
                                test["metadata"] = {}
                            test["metadata"]["_source_id"] = source_id
                        else:
                            if not hasattr(test, "metadata") or not test.metadata:
                                test.metadata = {}
                            elif not isinstance(test.metadata, dict):
                                test.metadata = dict(test.metadata)
                            test.metadata["_source_id"] = source_id

    test_set_data = {
        "name": custom_name if custom_name else test_set.name,
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
    request: dict = None,
):
    """
    Task that generates test cases using SDK synthesizers and saves them directly to the database.

    This task is flexible and can work with any synthesizer type by accepting arbitrary
    parameters through **synthesizer_kwargs.

    Args:
        synthesizer_type: Type of synthesizer to use (e.g., "prompt", "paraphrasing")
        num_tests: Number of test cases to generate (default: 5)
        batch_size: Batch size for the synthesizer (default: 20)
        model: Optional model to use for generation. If None (default), the task will
               fetch the user's configured default model from their settings.
               Can be either:
               - None: Fetch user's configured model or use DEFAULT_GENERATION_MODEL
               - A string provider name (e.g., "gemini", "openai")
               - A configured BaseLLM instance with API key and settings
        name: Optional custom name for the test set. If not provided, a name will be
              auto-generated based on the test set content.
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

    """

    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()

    with self.get_db_session() as db:
        documents_to_use, source_ids_list, source_ids_to_documents = process_sources_to_documents(
            sources=request["sources"],
            db=db,
            organization_id=org_id,
            user_id=user_id,
        )

    if request is None:
        raise ValueError("request parameter is required")

    num_tests = request["num_tests"]
    batch_size = request["batch_size"]
    test_set_name = request["name"]

    # Log the parameters (safely, without exposing sensitive data)
    log_kwargs = {k: v for k, v in request["config"].items() if not k.lower().endswith("_key")}

    # If no model specified, fetch user's configured model
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
        # Step 4: Generate test set
        self.update_state(state="PROGRESS", meta={"status": f"Generating {num_tests} test cases"})

        config = GenerationConfig(behaviors=request["config"]["behaviors"])
        synthesizer = ConfigSynthesizer(config=config, model=model, sources=documents_to_use)
        test_set = synthesizer.generate(num_tests=num_tests)

        self.log_with_context(
            "info",
            "Test set generated",
            actual_tests_generated=len(test_set.tests),
            requested_tests=num_tests,
        )

        # Step 5: Save to database
        self.update_state(state="PROGRESS", meta={"status": "Saving test set to database"})
        db_test_set = _save_test_set_to_database(
            self,
            test_set,
            org_id,
            user_id,
            custom_name=test_set_name,
            source_ids=source_ids,
            source_ids_to_documents=source_ids_to_documents,
        )

        # Step 6: Build and return result
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
