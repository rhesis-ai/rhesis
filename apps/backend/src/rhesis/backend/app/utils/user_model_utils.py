"""
User Model Utilities

Helper functions for managing user-configured AI models (LLMs and embeddings)
for different purposes (generation, evaluation, embedding, etc.)
"""

import logging
from typing import Union

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.constants import DEFAULT_EMBEDDING_MODEL, DEFAULT_GENERATION_MODEL
from rhesis.backend.app.models.user import User
from rhesis.sdk.models.base import BaseEmbedder, BaseLLM
from rhesis.sdk.models.factory import get_embedder, get_model

logger = logging.getLogger(__name__)


def get_user_generation_model(db: Session, user: User) -> Union[str, BaseLLM]:
    """
    Get the user's configured default generation model or fall back to DEFAULT_GENERATION_MODEL.

    This function is used for test generation workflows where the user can specify
    their preferred language model via the Models page in the UI.

    Args:
        db: Database session
        user: Current user (organization_id is extracted from user for security)

    Returns:
        Either a string (provider name) or a configured BaseLLM instance

    Example:
        >>> model = get_user_generation_model(db, current_user)
        >>> synthesizer = ConfigSynthesizer(config=config, model=model)
    """
    return _get_user_model(db, user, "generation", DEFAULT_GENERATION_MODEL)


def get_user_evaluation_model(db: Session, user: User) -> Union[str, BaseLLM]:
    """
    Get the user's configured default evaluation model or fall back to DEFAULT_GENERATION_MODEL.

    This function is used for language-model-as-a-judge scenarios where metrics are evaluated
    using a language model. The user can specify their preferred model via the Models page.

    Args:
        db: Database session
        user: Current user (organization_id is extracted from user for security)

    Returns:
        Either a string (provider name) or a configured BaseLLM instance

    Example:
        >>> model = get_user_evaluation_model(db, current_user)
        >>> # Use model for metric evaluation
    """
    return _get_user_model(db, user, "evaluation", DEFAULT_GENERATION_MODEL)


def get_user_embedding_model(db: Session, user: User) -> Union[str, BaseLLM]:
    """
    Get the user's configured default embedding model or fall back to DEFAULT_EMBEDDING_MODEL.

    This function is used for generating embeddings for semantic search and similarity
    matching. The user can specify their preferred embedding model via the Models page.

    Args:
        db: Database session
        user: Current user (organization_id is extracted from user for security)

    Returns:
        Either a string (provider name) or a configured BaseEmbedder instance

    Example:
        >>> model = get_user_embedding_model(db, current_user)
        >>> # Use model for embedding generation
    """
    return _get_user_embedding_model_with_settings(db, user)


def validate_user_evaluation_model(db: Session, user: User) -> None:
    """
    Validate that the user's configured evaluation model can be initialized.

    This function checks if the user has a configured evaluation model and
    validates that it can be properly initialized before test execution begins.
    Raises ValueError with a user-friendly message if validation fails.

    Args:
        db: Database session
        user: Current user

    Raises:
        ValueError: If the user's configured model cannot be initialized,
                   with a specific error message about the configuration issue
    """
    logger.info(
        f"[LLM_UTILS] Validating evaluation model for user_id={user.id}, "
        f"email={user.email}, org_id={user.organization_id}"
    )

    # Get the evaluation model settings
    model_settings = getattr(user.settings.models, "evaluation")
    model_id = model_settings.model_id

    # If no model configured, default model will be used (always valid)
    if not model_id:
        logger.info("[LLM_UTILS] No custom evaluation model configured, default will be used")
        return

    # Try to fetch and configure the model to validate it
    logger.info("[LLM_UTILS] Validating user's configured evaluation model...")
    try:
        _fetch_and_configure_model(
            db=db,
            model_id=str(model_id),
            organization_id=str(user.organization_id),
            default_model=DEFAULT_GENERATION_MODEL,
        )
        logger.info("[LLM_UTILS] ✓ Evaluation model validation successful")
    except ValueError:
        # Re-raise ValueError as-is (it already has a user-friendly message)
        raise


def validate_user_generation_model(db: Session, user: User) -> None:
    """
    Validate that the user's configured generation model can be initialized.

    This function checks if the user has a configured generation model and
    validates that it can be properly initialized before test generation begins.
    Raises ValueError with a user-friendly message if validation fails.

    Args:
        db: Database session
        user: Current user

    Raises:
        ValueError: If the user's configured model cannot be initialized,
                   with a specific error message about the configuration issue
    """
    logger.info(
        f"[LLM_UTILS] Validating generation model for user_id={user.id}, "
        f"email={user.email}, org_id={user.organization_id}"
    )

    # Get the generation model settings
    model_settings = getattr(user.settings.models, "generation")
    model_id = model_settings.model_id

    # If no model configured, default model will be used (always valid)
    if not model_id:
        logger.info("[LLM_UTILS] No custom generation model configured, default will be used")
        return

    # Try to fetch and configure the model to validate it
    logger.info("[LLM_UTILS] Validating user's configured generation model...")
    try:
        _fetch_and_configure_model(
            db=db,
            model_id=str(model_id),
            organization_id=str(user.organization_id),
            default_model=DEFAULT_GENERATION_MODEL,
        )
        logger.info("[LLM_UTILS] ✓ Generation model validation successful")
    except ValueError:
        # Re-raise ValueError as-is (it already has a user-friendly message)
        raise


def _is_rhesis_system_model(provider: str, api_key: str) -> bool:
    """
    Check if a model is a Rhesis system model.

    Rhesis system models use the backend's infrastructure and have no user-provided API key.

    Args:
        provider: The provider type value (e.g., "rhesis", "openai", "gemini")
        api_key: The API key stored for the model

    Returns:
        True if this is a Rhesis system model, False otherwise
    """
    return provider == "rhesis" and not api_key


def _fetch_and_configure_model(
    db: Session, model_id: str, organization_id: str, default_model: str
) -> Union[str, BaseLLM]:
    """
    Fetch a model from the database and configure it for use.

    Args:
        db: Database session
        model_id: ID of the model to fetch
        organization_id: Organization ID for security filtering
        default_model: Default model to fall back to

    Returns:
        Either a string (provider name) or a configured BaseLLM instance,
        or default_model if the configured model cannot be loaded
    """
    # SECURITY: Always use organization_id for filtering
    model = crud.get_model(db=db, model_id=model_id, organization_id=organization_id)

    if not model or not model.provider_type:
        logger.warning(f"[LLM_UTILS] Model with id={model_id} not found or has no provider_type")
        return default_model

    # Get provider configuration
    provider = model.provider_type.type_value
    model_name = model.model_name
    api_key = model.key
    api_key_preview = f"{model.key[:8]}..." if model.key else "None"

    logger.info(
        f"[LLM_UTILS] Found configured model: name={model.name}, provider={provider}, "
        f"model_name={model_name}, api_key={api_key_preview}"
    )

    # Special handling for Rhesis system models
    if _is_rhesis_system_model(provider, api_key):
        logger.info(
            "[LLM_UTILS] Rhesis system model detected - "
            "using backend's default model infrastructure"
        )
        logger.info(f"[LLM_UTILS] ✓ Falling back to default model: {default_model}")
        return default_model

    # Use SDK's get_model to create configured instance with error handling
    try:
        configured_model = get_model(provider=provider, model_name=model_name, api_key=api_key)
        logger.info(
            f"[LLM_UTILS] ✓ Returning configured BaseLLM instance: "
            f"{type(configured_model).__name__}"
        )
        return configured_model
    except ValueError as e:
        error_msg = str(e)
        error_msg_lower = error_msg.lower()

        # Provide specific error messages based on the type of configuration issue
        if "api_key" in error_msg_lower or "not set" in error_msg_lower:
            logger.error(f"[LLM_UTILS] User model API key not configured: {error_msg}")
            raise ValueError(
                f"Your configured model '{model.name}' ({provider}/{model_name}) requires "
                f"an API key that is missing or invalid. "
                f"Please update your API key in the Models settings."
            )
        elif "provider" in error_msg_lower or "not supported" in error_msg_lower:
            logger.error(f"[LLM_UTILS] Invalid provider for user model: {error_msg}")
            raise ValueError(
                f"Your configured model '{model.name}' uses an unsupported provider ({provider}). "
                f"Please select a different model in the Models settings."
            )
        elif "model" in error_msg_lower and (
            "not found" in error_msg_lower or "invalid" in error_msg_lower
        ):
            logger.error(f"[LLM_UTILS] Invalid model name for user model: {error_msg}")
            raise ValueError(
                f"Your configured model '{model.name}' has an invalid model name ({model_name}). "
                f"Please select a valid model in the Models settings."
            )
        else:
            # Generic configuration error
            logger.error(f"[LLM_UTILS] Failed to configure user model: {error_msg}")
            raise ValueError(
                f"Failed to initialize your configured model '{model.name}': {error_msg}"
            )


def _get_user_model(
    db: Session, user: User, model_type: str, default_model: str
) -> Union[str, BaseLLM]:
    """
    Internal helper to get user's configured model for a specific purpose.

    This function:
    1. Checks user settings for a configured model ID
    2. Fetches the model from database with organization filtering
    3. Creates a configured BaseLLM instance with provider, model name, and API key
    4. Falls back to default if no configuration exists

    Args:
        db: Database session
        user: Current user
        model_type: Type of model ("generation", "evaluation", or "embedding")
        default_model: Default model to use if user hasn't configured one

    Returns:
        Either a string (provider name) or a configured BaseLLM instance

    Security:
        Always uses user.organization_id for model lookup to prevent privilege escalation.
        Never accepts organization_id as a parameter that could be manipulated.
    """
    logger.info(
        f"[LLM_UTILS] Getting {model_type} model for user_id={user.id}, "
        f"email={user.email}, org_id={user.organization_id}"
    )

    # Get the appropriate model settings based on type
    model_settings = getattr(user.settings.models, model_type)
    model_id = model_settings.model_id

    logger.info(f"[LLM_UTILS] User settings: model_id={model_id}")

    if not model_id:
        logger.info("[LLM_UTILS] No configured model found in user settings")
        logger.info(f"[LLM_UTILS] ✓ Falling back to default model: {default_model}")
        return default_model

    # Fetch and configure the user's model
    logger.info("[LLM_UTILS] User has configured model, fetching from database...")
    return _fetch_and_configure_model(
        db=db,
        model_id=str(model_id),
        organization_id=str(user.organization_id),
        default_model=default_model,
    )


def _fetch_and_configure_embedder(
    db: Session, model_id: str, organization_id: str, default_model: str
) -> Union[str, BaseEmbedder]:
    """
    Fetch a model from the database and configure it as an embedder.

    Args:
        db: Database session
        model_id: UUID of the configured Model
        organization_id: Organization ID (for security filtering)
        default_model: Default embedder provider to fall back to

    Returns:
        Either a string (provider name) or a configured BaseEmbedder instance,
        or default_model if the configured model cannot be loaded
    """
    # SECURITY: Always use organization_id for filtering
    model = crud.get_model(db=db, model_id=model_id, organization_id=organization_id)

    if not model or not model.provider_type:
        logger.warning(f"[LLM_UTILS] Model with id={model_id} not found or has no provider_type")
        return default_model

    # Get provider configuration
    provider = model.provider_type.type_value
    model_name = model.model_name
    api_key = model.key
    api_key_preview = f"{model.key[:8]}..." if model.key else "None"

    logger.info(
        f"[LLM_UTILS] Found configured embedder: name={model.name}, provider={provider}, "
        f"model_name={model_name}, api_key={api_key_preview}"
    )

    # Special handling for Rhesis system models
    if _is_rhesis_system_model(provider, api_key):
        logger.info(
            "[LLM_UTILS] Rhesis system model detected - "
            "using backend's default embedder infrastructure"
        )
        logger.info(f"[LLM_UTILS] ✓ Falling back to default embedder: {default_model}")
        return default_model

    # Use SDK's get_embedder to create configured instance with error handling
    try:
        configured_embedder = get_embedder(
            provider=provider, model_name=model_name, api_key=api_key
        )
        logger.info(
            f"[LLM_UTILS] ✓ Returning configured BaseEmbedder instance: "
            f"{type(configured_embedder).__name__}"
        )
        return configured_embedder
    except ValueError as e:
        error_msg = str(e)
        error_msg_lower = error_msg.lower()

        # Provide specific error messages based on the type of configuration issue
        if "api_key" in error_msg_lower or "not set" in error_msg_lower:
            logger.error(f"[LLM_UTILS] Embedder API key not configured: {error_msg}")
            raise ValueError(
                f"Your configured embedding model '{model.name}' ({provider}/{model_name}) "
                f"requires an API key that is missing or invalid. "
                f"Please update your API key in the Models settings."
            )
        elif "provider" in error_msg_lower or "not supported" in error_msg_lower:
            logger.error(f"[LLM_UTILS] Invalid provider for embedder: {error_msg}")
            raise ValueError(
                f"Your configured embedding model '{model.name}' uses an unsupported "
                f"provider ({provider}). Please select a different model in the Models settings."
            )
        else:
            logger.error(f"[LLM_UTILS] Failed to configure embedder: {error_msg}")
            raise ValueError(
                f"Failed to configure your embedding model '{model.name}': {error_msg}. "
                f"Please check your model configuration in the Models settings."
            )


def _get_user_embedding_model_with_settings(db: Session, user: User):
    """
    Internal helper to get user's configured embedding model.

    This function:
    1. Checks user settings for a configured embedding model ID
    2. Fetches the model from database with organization filtering
    3. Creates a configured BaseEmbedder instance with provider, model name, and API key
    4. Falls back to default if no configuration exists

    Args:
        db: Database session
        user: Current user

    Returns:
        Either a string (provider name) or a configured BaseEmbedder instance

    Security:
        Always uses user.organization_id for model lookup to prevent privilege escalation.
    """
    logger.info(
        f"[LLM_UTILS] Getting embedding model for user_id={user.id}, "
        f"email={user.email}, org_id={user.organization_id}"
    )

    # Get embedding model settings
    model_settings = user.settings.models.embedding
    model_id = model_settings.model_id

    logger.info(f"[LLM_UTILS] User settings: model_id={model_id}")

    if not model_id:
        logger.info("[LLM_UTILS] No configured embedding model found in user settings")
        logger.info(f"[LLM_UTILS] ✓ Falling back to default embedder: {DEFAULT_EMBEDDING_MODEL}")
        return DEFAULT_EMBEDDING_MODEL

    # Fetch and configure the user's embedder
    logger.info("[LLM_UTILS] User has configured embedding model, fetching from database...")
    return _fetch_and_configure_embedder(
        db=db,
        model_id=str(model_id),
        organization_id=str(user.organization_id),
        default_model=DEFAULT_EMBEDDING_MODEL,
    )
