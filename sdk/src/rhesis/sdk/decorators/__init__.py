"""
Rhesis SDK decorators for observability and endpoint registration.

This module provides decorators for:
- Function observability with OpenTelemetry (@observe)
- Endpoint registration for remote testing (@endpoint)
- Custom observer builders for domain-specific patterns

Backward compatible imports:
    from rhesis.sdk import observe, endpoint
    from rhesis.sdk.decorators import create_observer, ObserverBuilder
"""

# Re-export for backward compatibility
# Import _state module itself for test monkeypatching
from . import _state
from ._state import _register_default_client, get_default_client
from .builders import ObserverBuilder, create_observer
from .endpoint import collaborate, endpoint
from .observe import observe

__all__ = [
    # Decorators
    "observe",
    "endpoint",
    "collaborate",
    # Builders
    "create_observer",
    "ObserverBuilder",
    # Internal (for SDK use)
    "_register_default_client",
    "get_default_client",
    "_state",
]
