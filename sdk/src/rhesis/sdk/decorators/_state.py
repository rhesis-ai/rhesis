"""Internal module for managing the default client state."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from rhesis.sdk.clients import Client

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


def is_client_disabled() -> bool:
    """
    Check if the default client is disabled (RHESIS_CONNECTOR_DISABLED enabled).

    This is a convenience function for decorators and other SDK components
    to quickly check if they should bypass their functionality.

    Accepts: true, 1, yes, on (case-insensitive)

    Returns:
        True if client is disabled or not initialized, False otherwise
    """
    if _default_client is None:
        return False  # No client means we'll raise an error elsewhere
    return getattr(_default_client, "is_disabled", False)
