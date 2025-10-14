import asyncio
from functools import partial
from typing import Dict, List, Optional, Union

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL
from rhesis.backend.app.models.user import User
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.synthesizers import (
    ConfigSynthesizer,
    DocumentSynthesizer,
    GenerationConfig,
)
from rhesis.sdk.types import Document


def get_user_generation_model(db: Session, user: User) -> Union[str, BaseLLM]:
    """
    Get the user's configured default generation model or fall back to DEFAULT_GENERATION_MODEL.
    
    Args:
        db: Database session
        user: Current user (organization_id is extracted from user for security)
    
    Returns:
        Either a string (provider name) or a configured BaseLLM instance
    """
    # Check if user has a default generation model set
    model_id = user.settings.models.generation.model_id
    
    if model_id:
        # SECURITY: Always use user's organization_id - never accept external organization_id
        model = crud.get_model(
            db=db, 
            model_id=model_id, 
            organization_id=str(user.organization_id)
        )
        
        if model and model.provider_type:
            # Get provider type value (e.g., "openai", "gemini")
            provider = model.provider_type.type_value
            model_name = model.model_name
            api_key = model.key  # Decrypted automatically by EncryptedString
            
            # Use SDK's get_model to create configured instance
            return get_model(provider=provider, model_name=model_name, api_key=api_key)
    
    # Fall back to default
    return DEFAULT_GENERATION_MODEL


async def generate_tests(
    db: Session,
    user: User,
    prompt: Dict,
    num_tests: int = 5,
    documents: Optional[List[Document]] = None,
) -> Dict:
    """
    Generate tests using the appropriate synthesizer based on input.
    Uses user's configured default model if available, otherwise falls back to DEFAULT_GENERATION_MODEL.

    Args:
        db: Database session
        user: Current user (organization_id extracted from user for security)
        prompt: The generation prompt configuration as a dictionary
        num_tests: Number of test cases to generate (default: 5)
        documents: Optional list of document objects. When provided, uses DocumentSynthesizer.
            Each document should contain:
            - name (str): Unique identifier or label for the document
            - description (str): Short description of the document's purpose or content
            - path (str): Local file path from upload endpoint
            - content (str): Pre-provided document content (optional)

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
        synthesizer = DocumentSynthesizer(prompt=prompt, model=model, config=config)
        generate_func = partial(synthesizer.generate, documents=documents, num_tests=num_tests)
    else:
        synthesizer = ConfigSynthesizer(config=config, model=model)
        generate_func = partial(synthesizer.generate, num_tests=num_tests)

    # Run the potentially blocking operation in a separate thread
    # to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    test_set = await loop.run_in_executor(None, generate_func)

    return test_set.to_dict()
