"""
LLM Model Utilities

Helper functions for managing user-configured LLM models for different purposes
(generation, evaluation, etc.)
"""

from typing import Union
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL
from rhesis.backend.app.models.user import User
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model


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


def _get_user_model(
    db: Session, 
    user: User, 
    model_type: str,
    default_model: str
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
    # Get the appropriate model settings based on type
    model_settings = getattr(user.settings.models, model_type)
    model_id = model_settings.model_id
    
    if model_id:
        # SECURITY: Always use user's organization_id - never accept external organization_id
        model = crud.get_model(
            db=db, 
            model_id=model_id, 
            organization_id=str(user.organization_id)
        )
        
        if model and model.provider_type:
            # Get provider configuration
            provider = model.provider_type.type_value
            model_name = model.model_name
            api_key = model.key  # Decrypted automatically by EncryptedString
            
            # Use SDK's get_model to create configured instance
            return get_model(provider=provider, model_name=model_name, api_key=api_key)
    
    # Fall back to default
    return default_model

