import asyncio
from functools import partial
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

# Remove the Rhesis import and import the entire sdk module
from rhesis.backend.app.models.user import User
from rhesis.sdk.synthesizers import DocumentSynthesizer, PromptSynthesizer
from rhesis.sdk.types import Document

DEFAULT_MODEL = "gemini"


async def generate_tests(
    db: Session,
    user: User,
    prompt: str,
    num_tests: int = 5,
    documents: Optional[List[Document]] = None,
) -> Dict:
    """
    Generate tests using the appropriate synthesizer based on input.

    Args:
        db: Database session
        user: Current user
        prompt: The generation prompt to use
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

    # Set the SDK configuration at the module level
    # Choose synthesizer based on whether documents are provided
    if documents:
        synthesizer = DocumentSynthesizer(prompt=prompt, model=DEFAULT_MODEL)
        generate_func = partial(synthesizer.generate, documents=documents, num_tests=num_tests)
    else:
        synthesizer = PromptSynthesizer(prompt=prompt, model=DEFAULT_MODEL)
        generate_func = partial(synthesizer.generate, num_tests=num_tests)

    # Run the potentially blocking operation in a separate thread
    # to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    test_set = await loop.run_in_executor(None, generate_func)

    return test_set.to_dict()
