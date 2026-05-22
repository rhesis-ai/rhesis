"""Internal module for managing the default client state."""

import contextvars
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from rhesis.sdk.clients import Client
    from rhesis.sdk.models.parameters import ResolvedParameters

# Module-level default client (managed transparently)
_default_client: Optional["Client"] = None
_parameters_context: contextvars.ContextVar[Optional["ResolvedParameters"]] = (
    contextvars.ContextVar("rhesis_parameters", default=None)
)


def get_parameters() -> Optional["ResolvedParameters"]:
    """Get the currently resolved parameters (populated during remote test execution)."""
    return _parameters_context.get()


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
    Check if the default client is a DisabledClient instance.

    This is a convenience function for decorators and other SDK components
    to quickly check if they should bypass their functionality.

    Returns:
        True if client is disabled or not initialized, False otherwise
    """
    if _default_client is None:
        return False  # No client means we'll raise an error elsewhere
    return getattr(_default_client, "is_disabled", False)
