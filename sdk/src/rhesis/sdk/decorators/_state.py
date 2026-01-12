"""Internal module for managing the default client state."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from rhesis.sdk.client import Client

# Module-level default client (managed transparently)
_default_client: Optional["Client"] = None


def _register_default_client(client: "Client") -> None:  # pyright: ignore[reportUnusedFunction]
    """
    Internal: Automatically register client (called from Client.__init__).

    Args:
        client: Client instance to register
    """
    global _default_client
    _default_client = client


def get_default_client() -> Optional["Client"]:
    """
    Get the currently registered default client.

    Returns:
        The default client instance, or None if not registered
    """
    return _default_client
