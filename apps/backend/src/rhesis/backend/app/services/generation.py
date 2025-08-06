import os
from typing import Dict
import asyncio
from functools import partial

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

# Remove the Rhesis import and import the entire sdk module
import rhesis.sdk
from rhesis.sdk.synthesizers import PromptSynthesizer

from rhesis.backend.app.crud import get_user_tokens
from rhesis.backend.app.models.user import User


async def generate_tests(
    db: Session, 
    user: User, 
    prompt: str, 
    num_tests: int = 5,
    documents: Optional[List[Dict]] = None
) -> Dict:
    """
    Generate tests using the prompt synthesizer.

    Args:
        db: Database session
        user: Current user
        prompt: The generation prompt to use
        num_tests: Number of test cases to generate (default: 5)
        documents: Optional list of document objects. Each document should contain:
            - name (str): Unique identifier or label for the document
            - description (str): Short description of the document's purpose or content
            - path (str): Local file path from upload endpoint
            - content (str): Pre-provided document content (optional)

    Returns:
        Dict: The generated test set as a dictionary

    Raises:
        HTTPException: If no valid tokens are found for the user
    """
    # Get a valid token for the user
    tokens = get_user_tokens(db, user.id, valid_only=True)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No valid API tokens found. Please create a new API token.",
        )

    # Set the SDK configuration at the module level
    rhesis.sdk.base_url = os.getenv('RHESIS_BASE_URL', "https://api.rhesis.ai")
    rhesis.sdk.api_key = tokens[0].token

    print("This is configured in Rhesis Base URL: ", rhesis.sdk.base_url)
    
    synthesizer = PromptSynthesizer(prompt=prompt, documents=documents)

    # Run the potentially blocking operation in a separate thread
    # to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    test_set = await loop.run_in_executor(
        None, 
        partial(synthesizer.generate, num_tests=num_tests)
    )

    return test_set.to_dict()
