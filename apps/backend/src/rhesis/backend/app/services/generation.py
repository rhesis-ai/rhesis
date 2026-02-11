import asyncio
from functools import partial
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.services import GenerationConfig, SourceData
from rhesis.backend.app.utils.user_model_utils import get_user_generation_model
from rhesis.backend.logging import logger
from rhesis.sdk.services.extractor import SourceSpecification, SourceType
from rhesis.sdk.synthesizers import ConfigSynthesizer


def get_source_specifications(
    sources: List[SourceData],
    db: Session,
    organization_id: str,
    user_id: str,
) -> List[SourceSpecification]:
    """
    Get SDK SourceSpecification objects from backend SourceData.

    Fetches source content from database and creates SDK-compatible objects.
    The source database ID is embedded in the metadata as '_source_id' for
    later tracking when tests are generated.

    Args:
        sources: List of SourceData with database IDs
        db: Database session
        organization_id: Organization ID for filtering
        user_id: User ID for filtering

    Returns:
        List of SDK SourceSpecification objects with embedded source IDs

    Raises:
        HTTPException: If source not found
    """
    if not sources:
        return []

    # Normalize to SourceData objects if needed
    if sources and isinstance(sources[0], dict):
        sources = [SourceData(**source) for source in sources]

    source_specifications = []

    for source_data in sources:
        # Fetch full source from database
        db_source = crud.get_source_with_content(
            db=db,
            source_id=source_data.id,
            organization_id=organization_id,
            user_id=user_id,
        )

        if not db_source:
            raise HTTPException(status_code=404, detail=f"Source {source_data.id} not found")

        # Skip sources with no content (would cause chunker to fail)
        if not db_source.content or not db_source.content.strip():
            logger.warning(
                f"Skipping source {source_data.id} ({db_source.title}) - no content available"
            )
            continue

        # Convert to SDK SourceSpecification with embedded source ID
        source_spec = SourceSpecification(
            name=db_source.title,
            description=db_source.description or f"Source: {db_source.title}",
            type=SourceType.TEXT,
            metadata={
                "content": db_source.content,
                "_source_id": str(source_data.id),  # Embed DB ID for tracking
            },
        )

        source_specifications.append(source_spec)

    return source_specifications


async def generate_tests(
    db: Session,
    user: User,
    config: GenerationConfig,
    num_tests: int = 5,
    sources: Optional[List[SourceData]] = None,
) -> List[Dict]:
    """
    Generate tests using ConfigSynthesizer.

    This function is used for both sampling and bulk generation.

    Args:
        db: Database session
        user: Current user
        config: SDK GenerationConfig object
        num_tests: Number of tests to generate
        sources: Optional list of sources with database IDs

    Returns:
        List of test dictionaries (source IDs are embedded in test metadata)

    Raises:
        HTTPException: If no valid tokens are found for the user
    """
    # Get SDK source specifications (with embedded source IDs)
    source_specifications = []

    if sources:
        source_specifications = get_source_specifications(
            sources=sources,
            db=db,
            organization_id=str(user.organization_id),
            user_id=str(user.id),
        )

    # Get user's configured model
    model = get_user_generation_model(db, user)

    # Create synthesizer
    synthesizer = ConfigSynthesizer(
        config=config,
        model=model,
        sources=source_specifications if source_specifications else None,
    )

    # Generate tests
    generate_func = partial(synthesizer.generate, num_tests=num_tests)
    loop = asyncio.get_event_loop()
    test_set = await loop.run_in_executor(None, generate_func)

    # Return raw list of tests - router will wrap in response structure
    return test_set.to_dict()["tests"]


async def generate_multiturn_tests(
    db: Session,
    user: User,
    config: Dict,
    num_tests: int = 5,
) -> Dict:
    """
    Generate multi-turn test cases using MultiTurnSynthesizer.
    Uses user's configured default model if available,
    otherwise falls back to DEFAULT_GENERATION_MODEL.

    Args:
        db: Database session
        user: Current user (organization_id extracted from user for security)
        config: The generation configuration as a dictionary containing:
            - generation_prompt (str): The generation prompt describing what to test
            - behavior (str, optional): Behavior type (e.g., "Compliance", "Reliability")
            - category (str, optional): Category (e.g., "Harmful", "Harmless")
            - topic (str, optional): Specific topic
        num_tests: Number of test cases to generate (default: 5)

    Returns:
        Dict: The generated test set as a dictionary

    Raises:
        HTTPException: If no valid tokens are found for the user
    """
    from rhesis.sdk.synthesizers.multi_turn.base import GenerationConfig, MultiTurnSynthesizer

    # Get user's configured model or fallback to default
    model = get_user_generation_model(db, user)

    # Create configuration for multi-turn synthesizer from dict
    generation_config = GenerationConfig(**config)

    synthesizer = MultiTurnSynthesizer(config=generation_config, model=model)

    # Run the potentially blocking operation in a separate thread
    # to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    test_set = await loop.run_in_executor(None, synthesizer.generate, num_tests)

    return test_set.to_dict()
