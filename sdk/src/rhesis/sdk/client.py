from typing import Optional

from rhesis.sdk.config import get_api_key, get_base_url


class Client:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the Rhesis client.

        Args:
            api_key: Optional API key. If not provided, will try to get it from
                    module level variable or environment variable.
            base_url: Optional base URL. If not provided, will try to get it from
                     module level variable or environment variable.
        """
        self.api_key = api_key if api_key is not None else get_api_key()
        self._base_url = base_url if base_url is not None else get_base_url()

    @property
    def base_url(self) -> str:
        """Get the base URL with trailing slash removed."""
        return self._base_url.rstrip("/")

    def get_url(self, endpoint: str) -> str:
        """
        Construct a URL by combining base_url and endpoint.

        Args:
            endpoint: The API endpoint path.

        Returns:
            str: The complete URL with proper formatting.
        """
        # Remove leading slash from endpoint if present
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/{endpoint}"
