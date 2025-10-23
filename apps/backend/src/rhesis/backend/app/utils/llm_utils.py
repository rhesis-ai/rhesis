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
    logger.info(f"[LLM_UTILS] Getting {model_type} model for user_id={user.id}, email={user.email}, org_id={user.organization_id}")
    
    # Get the appropriate model settings based on type
    model_settings = getattr(user.settings.models, model_type)
    model_id = model_settings.model_id
    
    logger.info(f"[LLM_UTILS] User settings: model_id={model_id}")
    
    if model_id:
        logger.info(f"[LLM_UTILS] User has configured model, fetching from database...")
        
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
            api_key_preview = f"{model.key[:8]}..." if model.key else "None"
            
            logger.info(f"[LLM_UTILS] Found configured model: name={model.name}, provider={provider}, model_name={model_name}, api_key={api_key_preview}")
            
            # Use SDK's get_model to create configured instance
            configured_model = get_model(provider=provider, model_name=model_name, api_key=model.key)
            logger.info(f"[LLM_UTILS] ✓ Returning configured BaseLLM instance: {type(configured_model).__name__}")
            return configured_model
        else:
            logger.warning(f"[LLM_UTILS] Model with id={model_id} not found or has no provider_type")
    else:
        logger.info(f"[LLM_UTILS] No configured model found in user settings")
    
    # Fall back to default
    logger.info(f"[LLM_UTILS] ✓ Falling back to default model: {default_model}")
    return default_model


def json_schema_to_pydantic(schema_dict: dict):
    """
    Convert a JSON schema dictionary to a Pydantic BaseModel class.
    
    This enables dynamic structured output by converting OpenAPI/JSON schema
    definitions into Pydantic models that can be used with LLM providers.
    
    Args:
        schema_dict: JSON schema dictionary with 'properties' and optional 'required' fields
        
    Returns:
        A dynamically created Pydantic BaseModel class
        
    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "name": {"type": "string"},
        ...         "age": {"type": "integer"}
        ...     },
        ...     "required": ["name"]
        ... }
        >>> PersonModel = json_schema_to_pydantic(schema)
        >>> # Now use PersonModel as a Pydantic schema with LLM
        
    Supported JSON Schema Types:
        - string -> str
        - integer -> int
        - number -> float
        - boolean -> bool
        - array -> list
        - object -> dict
    """
    from pydantic import create_model
    
    # Extract properties from JSON schema
    properties = schema_dict.get("properties", {})
    required_fields = schema_dict.get("required", [])
    
    # Build field definitions for Pydantic model
    field_definitions = {}
    for field_name, field_info in properties.items():
        field_type = field_info.get("type")
        
        # Map JSON schema types to Python types
        type_mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        
        python_type = type_mapping.get(field_type, str)
        
        # Mark as optional if not in required fields
        # ... means required (no default), None means optional (default=None)
        if field_name in required_fields:
            field_definitions[field_name] = (python_type, ...)
        else:
            field_definitions[field_name] = (python_type, None)
    
    # Dynamically create and return Pydantic model
    return create_model("DynamicSchema", **field_definitions)

