import os
from typing import Optional

# Default values
DEFAULT_BASE_URL = "https://api.rhesis.com"

# Module level variables
api_key: Optional[str] = None
base_url: Optional[str] = None


def get_api_key() -> str:
    """
    Get the API key from module level variable or environment variable.
    Raises ValueError if no API key is found.
    """
    # First check module level variable
    if api_key is not None:
        return api_key

    # Then check environment variable
    env_api_key = os.getenv("RHESIS_API_KEY")
    if env_api_key:
        return env_api_key

    raise ValueError(
        "No API key found. Set it using rhesis.api_key = 'your-key' "
        "or set the environment variable RHESIS_API_KEY"
    )


def get_base_url() -> str:
    """
    Get the base URL from module level variable or environment variable.
    Falls back to default if neither is set.
    """
    # First check module level variable
    if base_url is not None:
        return base_url

    # Then check environment variable
    env_base_url = os.getenv("RHESIS_BASE_URL")
    if env_base_url:
        return env_base_url

    return DEFAULT_BASE_URL
