"""
User Model Utilities

Helper functions for managing user-configured AI models (LLMs and embeddings)
for different purposes (generation, evaluation, embedding, etc.)
"""

import logging
import os
from typing import Union

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.config.settings import get_model_settings, get_rhesis_settings
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.model_errors import ModelConfigurationError
from rhesis.sdk.models.base import BaseEmbedder, BaseLLM
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger(__name__)


def _default_generation_model() -> str:
    return get_model_settings().generation_model


def _default_evaluation_model() -> str:
    return get_model_settings().evaluation_model


def _default_execution_model() -> str:
    return get_model_settings().execution_model


def _default_embedding_model() -> str:
    return get_model_settings().embedding_model


def get_generation_model_with_override(
    db: Session, user: User, model_id: str = None
) -> Union[str, BaseLLM]:
    """
    Get a generation model, preferring an explicit override model_id over the user's default.

    If model_id is provided, fetch and configure that specific model (with org-level
    security filtering). Otherwise fall back to the user's configured default or
    the system generation model setting.

    Args:
        db: Database session
        user: Current user (organization_id is extracted for security)
        model_id: Optional model UUID to use instead of the user's default

    Returns:
        Either a string (provider name) or a configured BaseLLM instance
    """
    if model_id:
        logger.debug("Using per-request generation model override: model_id=%s", model_id)
        return _fetch_and_configure_model(
            db=db,
            model_id=str(model_id),
            organization_id=str(user.organization_id),
            default_model=_default_generation_model(),
            user=user,
        )
    return get_user_generation_model(db, user)


def get_user_generation_model(db: Session, user: User) -> Union[str, BaseLLM]:
    """
    Get the user's configured default generation model or fall back to the system setting.

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
    return _get_user_model(db, user, "generation", _default_generation_model())


def get_user_evaluation_model(db: Session, user: User) -> Union[str, BaseLLM]:
    """
    Get the user's configured default evaluation model or fall back to the system setting.

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
    return _get_user_model(db, user, "evaluation", _default_evaluation_model())


def get_user_execution_model(db: Session, user: User) -> Union[str, BaseLLM]:
    """
    Get the user's configured default execution model or fall back to the system setting.

    This function is used for multi-turn test execution (Penelope) where the user can
    specify their preferred language model for driving the conversation agent.

    Args:
        db: Database session
        user: Current user (organization_id is extracted from user for security)

    Returns:
        Either a string (provider name) or a configured BaseLLM instance
    """
    return _get_user_model(db, user, "execution", _default_execution_model())


def get_execution_model_with_override(
    db: Session, user: User, model_id: str = None
) -> Union[str, BaseLLM]:
    """
    Get an execution model, preferring an explicit override model_id over the user's default.

    If model_id is provided, fetch and configure that specific model (with org-level
    security filtering). Otherwise fall back to the user's configured default or
    the system execution model setting.

    Args:
        db: Database session
        user: Current user (organization_id is extracted for security)
        model_id: Optional model UUID to use instead of the user's default

    Returns:
        Either a string (provider name) or a configured BaseLLM instance
    """
    if model_id:
        logger.debug("Using per-request execution model override: model_id=%s", model_id)
        return _fetch_and_configure_model(
            db=db,
            model_id=str(model_id),
            organization_id=str(user.organization_id),
            default_model=_default_execution_model(),
            user=user,
        )
    return get_user_execution_model(db, user)


def get_evaluation_model_with_override(
    db: Session, user: User, model_id: str = None
) -> Union[str, BaseLLM]:
    """
    Get an evaluation model, preferring an explicit override model_id over the user's default.

    If model_id is provided, fetch and configure that specific model (with org-level
    security filtering). Otherwise fall back to the user's configured default or
    the system evaluation model setting.

    Args:
        db: Database session
        user: Current user (organization_id is extracted for security)
        model_id: Optional model UUID to use instead of the user's default

    Returns:
        Either a string (provider name) or a configured BaseLLM instance
    """
    if model_id:
        logger.debug("Using per-request evaluation model override: model_id=%s", model_id)
        return _fetch_and_configure_model(
            db=db,
            model_id=str(model_id),
            organization_id=str(user.organization_id),
            default_model=_default_evaluation_model(),
            user=user,
        )
    return get_user_evaluation_model(db, user)


def get_user_embedding_model(db: Session, user: User) -> Union[str, BaseLLM]:
    """
    Get the user's configured default embedding model or fall back to the system setting.

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
        "Validating evaluation model for user_id=%s, org_id=%s",
        user.id,
        user.organization_id,
    )

    # Get the evaluation model settings
    model_settings = getattr(user.settings.models, "evaluation")
    model_id = model_settings.model_id

    # If no model configured, default model will be used (always valid)
    if not model_id:
        return

    # Try to fetch and configure the model to validate it
    try:
        _fetch_and_configure_model(
            db=db,
            model_id=str(model_id),
            organization_id=str(user.organization_id),
            default_model=_default_evaluation_model(),
            user=user,
        )
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
        "Validating generation model for user_id=%s, org_id=%s",
        user.id,
        user.organization_id,
    )

    # Get the generation model settings
    model_settings = getattr(user.settings.models, "generation")
    model_id = model_settings.model_id

    # If no model configured, default model will be used (always valid)
    if not model_id:
        return

    # Try to fetch and configure the model to validate it
    try:
        _fetch_and_configure_model(
            db=db,
            model_id=str(model_id),
            organization_id=str(user.organization_id),
            default_model=_default_generation_model(),
            user=user,
        )
    except ValueError:
        # Re-raise ValueError as-is (it already has a user-friendly message)
        raise


def validate_user_execution_model(db: Session, user: User) -> None:
    """
    Validate that the user's configured execution model can be initialized.

    This function checks if the user has a configured execution model and
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
        "Validating execution model for user_id=%s, org_id=%s",
        user.id,
        user.organization_id,
    )

    model_settings = getattr(user.settings.models, "execution")
    model_id = model_settings.model_id

    if not model_id:
        return

    try:
        _fetch_and_configure_model(
            db=db,
            model_id=str(model_id),
            organization_id=str(user.organization_id),
            default_model=_default_execution_model(),
            user=user,
        )
    except ValueError:
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


def _call_polyphemus_with_delegation(user: User, model_name: str, **kwargs):
    """
    Create Polyphemus client with delegation token.

    Uses service delegation tokens to allow the backend to call Polyphemus
    on behalf of a user while maintaining user attribution.

    Args:
        user: User on whose behalf the request is made
        model_name: Polyphemus model name (e.g., "default")
        **kwargs: Additional arguments to pass to PolyphemusLLM

    Returns:
        Configured PolyphemusLLM instance

    Raises:
        ValueError: If user is not active or not verified
    """
    from rhesis.backend.app.auth.token_utils import create_service_delegation_token
    from rhesis.sdk.models.providers.polyphemus import PolyphemusLLM

    # Verify user is active and verified before creating delegation token
    if not user.is_active:
        logger.error("Cannot create delegation token: user %s is inactive", user.email)
        raise ValueError("User account is inactive")

    if not user.is_verified:
        logger.error("Cannot create delegation token: user %s is not verified", user.email)
        raise ValueError("User account is not verified")

    delegation_token = create_service_delegation_token(user, "polyphemus")
    polyphemus_url = os.environ.get("DEFAULT_POLYPHEMUS_URL", "https://polyphemus.rhesis.ai")

    return PolyphemusLLM(
        model_name=model_name,
        api_key=delegation_token,
        base_url=polyphemus_url,
        **kwargs,
    )


def _fetch_and_configure_model(
    db: Session,
    model_id: str,
    organization_id: str,
    default_model: str,
    user: User = None,
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
        logger.warning("Model with id=%s not found or has no provider_type", model_id)
        return default_model

    # Get provider configuration
    provider = model.provider_type.type_value
    model_name = model.model_name
    api_key = model.key

    # Special handling for Rhesis system models
    if _is_rhesis_system_model(provider, api_key):
        return default_model

    # Special handling for Polyphemus models without a stored API key.
    #
    # - Self-hosted deployments configure a real RHESIS_API_KEY and call
    #   Polyphemus directly with it (same path as any other provider below).
    # - Rhesis-hosted (SaaS) deployments have no such key configured, so we
    #   mint a short-lived delegation token on the user's behalf instead.
    #   Delegation only validates because the backend and Polyphemus share
    #   the same JWT_SECRET_KEY there; a self-hosted backend's secret would
    #   be meaningless to the externally-hosted Polyphemus service, so a
    #   configured RHESIS_API_KEY always takes precedence when present.
    if provider == "polyphemus" and not api_key:
        if get_rhesis_settings().api_key:
            logger.debug("Using configured RHESIS_API_KEY for Polyphemus (self-hosted mode)")
        elif user:
            return _call_polyphemus_with_delegation(user, model_name)

    # Use SDK's get_model to create configured instance with error handling
    try:
        extra_params = {}
        if model.endpoint and model.endpoint.strip():
            extra_params["api_base"] = model.endpoint.strip()
        return get_model(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            model_type="language",
            **extra_params,
        )
    except ValueError as e:
        error_msg = str(e)
        error_msg_lower = error_msg.lower()

        # Provide specific error messages based on the type of configuration issue
        if "api_key" in error_msg_lower or "not set" in error_msg_lower:
            logger.error("User model API key not configured: %s", error_msg)
            raise ModelConfigurationError(
                f"Your configured model '{model.name}' ({provider}/{model_name}) requires "
                f"an API key that is missing or invalid. "
                f"Please update your API key in the Models settings.",
                original_error=e,
            )
        elif "provider" in error_msg_lower or "not supported" in error_msg_lower:
            logger.error("Invalid provider for user model: %s", error_msg)
            raise ModelConfigurationError(
                f"Your configured model '{model.name}' uses an unsupported provider ({provider}). "
                f"Please select a different model in the Models settings.",
                original_error=e,
            )
        elif "model" in error_msg_lower and (
            "not found" in error_msg_lower or "invalid" in error_msg_lower
        ):
            logger.error("Invalid model name for user model: %s", error_msg)
            raise ModelConfigurationError(
                f"Your configured model '{model.name}' has an invalid model name ({model_name}). "
                f"Please select a valid model in the Models settings.",
                original_error=e,
            )
        else:
            # Generic configuration error
            logger.error("Failed to configure user model: %s", error_msg)
            raise ModelConfigurationError(
                f"Failed to initialize your configured model '{model.name}': {error_msg}",
                original_error=e,
            )


def _get_user_model(
    db: Session, user: User, purpose: str, default_model: str
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
        purpose: What the model is used for ("generation", "evaluation", or "embedding")
        default_model: Default model to use if user hasn't configured one

    Returns:
        Either a string (provider name) or a configured BaseLLM instance

    Security:
        Always uses user.organization_id for model lookup to prevent privilege escalation.
        Never accepts organization_id as a parameter that could be manipulated.
    """
    # Get the appropriate model settings based on type
    model_settings = getattr(user.settings.models, purpose)
    model_id = model_settings.model_id

    if not model_id:
        return default_model

    return _fetch_and_configure_model(
        db=db,
        model_id=str(model_id),
        organization_id=str(user.organization_id),
        default_model=default_model,
        user=user,
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
        logger.warning("Model with id=%s not found or has no provider_type", model_id)
        return default_model

    # Get provider configuration
    provider = model.provider_type.type_value
    model_name = model.model_name
    api_key = model.key

    # Special handling for Rhesis system models
    if _is_rhesis_system_model(provider, api_key):
        return default_model

    # Use SDK's get_model to create configured instance with error handling
    try:
        extra_params = {}
        if model.endpoint and model.endpoint.strip():
            extra_params["api_base"] = model.endpoint.strip()
        return get_model(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            model_type="embedding",
            **extra_params,
        )
    except ValueError as e:
        error_msg = str(e)
        error_msg_lower = error_msg.lower()

        # Provide specific error messages based on the type of configuration issue
        if "api_key" in error_msg_lower or "not set" in error_msg_lower:
            logger.error("Embedder API key not configured: %s", error_msg)
            raise ModelConfigurationError(
                f"Your configured embedding model '{model.name}' ({provider}/{model_name}) "
                f"requires an API key that is missing or invalid. "
                f"Please update your API key in the Models settings.",
                original_error=e,
            )
        elif "provider" in error_msg_lower or "not supported" in error_msg_lower:
            logger.error("Invalid provider for embedder: %s", error_msg)
            raise ModelConfigurationError(
                f"Your configured embedding model '{model.name}' uses an unsupported "
                f"provider ({provider}). Please select a different model in the Models settings.",
                original_error=e,
            )
        else:
            logger.error("Failed to configure embedder: %s", error_msg)
            raise ModelConfigurationError(
                f"Failed to configure your embedding model '{model.name}': {error_msg}. "
                f"Please check your model configuration in the Models settings.",
                original_error=e,
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
    # Get embedding model settings
    model_settings = user.settings.models.embedding
    model_id = model_settings.model_id

    if not model_id:
        return _default_embedding_model()

    return _fetch_and_configure_embedder(
        db=db,
        model_id=str(model_id),
        organization_id=str(user.organization_id),
        default_model=_default_embedding_model(),
    )
