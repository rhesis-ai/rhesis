import os
import sys
from typing import Optional, Any, Callable, TypeVar

# Default values
DEFAULT_BASE_URL = "https://api.rhesis.ai"

# Module level variables
api_key: Optional[str] = None
base_url: Optional[str] = None

T = TypeVar('T')

def _get_config_value(
    var_name: str,
    module_var: Optional[T],
    env_var_name: str,
    default_value: Optional[T] = None,
    required: bool = False
) -> T:
    """
    Generic function to get configuration values from various sources.
    
    Args:
        var_name: The variable name in the SDK
        module_var: The current module-level variable value
        env_var_name: The environment variable name to check
        default_value: Default value to return if no value is found
        required: Whether the value is required (raises ValueError if not found)
        
    Returns:
        The configuration value
        
    Raises:
        ValueError: If the value is required but not found
    """
    global api_key, base_url
    
    # Use the correct global variable based on var_name
    if var_name == 'api_key':
        global_var_ref = 'api_key'
    elif var_name == 'base_url':
        global_var_ref = 'base_url'
    else:
        global_var_ref = None
    
    # First check module level variable
    if module_var is not None:
        return module_var
        
    # Then check if it was set at the SDK level
    try:
        import rhesis.sdk
        if hasattr(rhesis.sdk, var_name) and getattr(rhesis.sdk, var_name) is not None:
            # Update our module level variable to match
            value = getattr(rhesis.sdk, var_name)
            if global_var_ref:
                # Update the module-level variable
                if global_var_ref == 'api_key':
                    api_key = value
                elif global_var_ref == 'base_url':
                    base_url = value
            return value
    except (ImportError, AttributeError):
        pass

    # Then check environment variable
    env_value = os.getenv(env_var_name)
    if env_value:
        return env_value

    # Return default or raise error
    if default_value is not None or not required:
        return default_value
    else:
        raise ValueError(
            f"No {var_name} found. Set it using rhesis.sdk.{var_name} = 'your-value' "
            f"or set the environment variable {env_var_name}"
        )


def get_api_key() -> str:
    """
    Get the API key from module level variable or environment variable.
    Raises ValueError if no API key is found.
    """
    return _get_config_value('api_key', api_key, "RHESIS_API_KEY", required=True)


def get_base_url() -> str:
    """
    Get the base URL from module level variable or environment variable.
    Falls back to default if neither is set.
    """
    return _get_config_value('base_url', base_url, "RHESIS_BASE_URL", DEFAULT_BASE_URL)
