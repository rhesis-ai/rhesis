"""
LLM Model Utilities

Helper functions for managing user-configured LLM models for different purposes
(generation, evaluation, etc.)
"""

import logging
from typing import Union

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL
from rhesis.backend.app.models.user import User
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger(__name__)


def get_user_generation_model(db: Session, user: User) -> Union[str, BaseLLM]:
    """
    Get the user's configured default generation model or fall back to DEFAULT_GENERATION_MODEL.

    This function is used for test generation workflows where the user can specify
    their preferred LLM model via the Models page in the UI.

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

    This function is used for LLM-as-a-judge scenarios where metrics are evaluated
    using an LLM. The user can specify their preferred model via the Models page.

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

    # Use SDK's get_model to create configured instance
    configured_model = get_model(provider=provider, model_name=model_name, api_key=api_key)
    logger.info(
        f"[LLM_UTILS] ✓ Returning configured BaseLLM instance: {type(configured_model).__name__}"
    )
    return configured_model


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
        model_type: Type of model ("generation" or "evaluation")
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
