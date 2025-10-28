import asyncio
from functools import partial
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.services import SourceData
from rhesis.backend.app.utils.llm_utils import get_user_generation_model
from rhesis.sdk.synthesizers import (
    ConfigSynthesizer,
    DocumentSynthesizer,
    GenerationConfig,
)
from rhesis.sdk.types import Document


def process_sources_to_documents(
    sources: List[SourceData],
    db: Session,
    organization_id: str,
    user_id: str,
) -> Tuple[List[Document], List[str], Dict[str, str]]:
    """
    Process SourceData list into SDK Document objects with source tracking.

    Fetches full source data from database if source_data.id is provided.
    Uses database values as defaults, but allows provided values to override.
    Returns SDK documents along with source ID tracking information.

    Args:
        sources: List of SourceData objects (only id is required)
        db: Database session
        organization_id: Organization ID for filtering sources
        user_id: User ID for filtering sources

    Returns:
        Tuple containing:
            - List of SDK Document objects
            - List of source IDs in the same order as documents
            - Mapping of document names to source IDs

    Raises:
        HTTPException: If a source is not found in the database
    """
    documents_sdk = []
    source_ids_list = []
    source_ids_to_documents = {}

    if not sources:
        return documents_sdk, source_ids_list, source_ids_to_documents

    for source_data in sources:
        # Fetch source from database if id is provided
        if source_data.id:
            db_source = crud.get_source_with_content(
                db=db,
                source_id=source_data.id,
                organization_id=organization_id,
                user_id=user_id,
            )
            if db_source is None:
                raise HTTPException(
                    status_code=404, detail=f"Source with id {source_data.id} not found"
                )
            # Use database values as defaults, allow provided values to override
            source_name = source_data.name or db_source.title
            source_description = source_data.description or db_source.description
            source_content = source_data.content or db_source.content or ""
        else:
            # No ID provided, use provided values as-is
            source_name = source_data.name
            source_description = source_data.description
            source_content = source_data.content or ""

        # Create Document object from SourceData
        document_sdk = Document(
            name=source_name,
            description=source_description or (f"Source document: {source_name}"),
            content=source_content or (f"No content available for source: {source_name}"),
            path=None,  # Sources don't have file paths
        )
        documents_sdk.append(document_sdk)

        # Track source IDs only if an ID was provided
        if source_data.id:
            source_ids_list.append(str(source_data.id))
            # Store mapping: document name -> source_id for later lookup
            source_ids_to_documents[source_name] = str(source_data.id)

    return documents_sdk, source_ids_list, source_ids_to_documents


async def generate_tests(
    db: Session,
    user: User,
    prompt: Dict,
    num_tests: int = 5,
    documents: Optional[List[Document]] = None,
    chip_states: Optional[List[Dict]] = None,
    rated_samples: Optional[List[Dict]] = None,
    previous_messages: Optional[List[Dict]] = None,
) -> Dict:
    """
    Generate tests using the appropriate synthesizer based on input.
    Uses user's configured default model if available,
    otherwise falls back to DEFAULT_GENERATION_MODEL.

    Args:
        db: Database session
        user: Current user (organization_id extracted from user for security)
        prompt: The generation prompt configuration as a dictionary
        num_tests: Number of test cases to generate (default: 5)
        documents: Optional list of document objects. When provided, uses DocumentSynthesizer.
            Each document should contain:
            - name (str): Unique identifier or label for the document
            - description (str): Short description of the document's purpose or content
            - content (str): The document content
        chip_states: Optional list of chip states for iteration context
        rated_samples: Optional list of rated samples for iteration context
        previous_messages: Optional list of previous messages for iteration context

    Returns:
        Dict: The generated test set as a dictionary

    Raises:
        HTTPException: If no valid tokens are found for the user
    """

    # Get user's configured model or fallback to default
    model = get_user_generation_model(db, user)

    # Choose synthesizer based on whether documents are provided
    config = GenerationConfig(**prompt)
    if documents:
        # For DocumentSynthesizer, we need a simple prompt string
        # The detailed config is passed via the config parameter
        prompt_string = str(
            prompt.get("specific_requirements") or prompt.get("test_type", "Generate test cases")
        )
        synthesizer = DocumentSynthesizer(
            prompt=prompt_string,
            model=model,
            config=config,
            chip_states=chip_states,
            rated_samples=rated_samples,
            previous_messages=previous_messages,
        )
        generate_func = partial(synthesizer.generate, documents=documents, num_tests=num_tests)
    else:
        synthesizer = ConfigSynthesizer(
            config=config,
            model=model,
            chip_states=chip_states,
            rated_samples=rated_samples,
            previous_messages=previous_messages,
        )
        generate_func = partial(synthesizer.generate, num_tests=num_tests)

    # Run the potentially blocking operation in a separate thread
    # to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    test_set = await loop.run_in_executor(None, generate_func)

    return test_set.to_dict()
