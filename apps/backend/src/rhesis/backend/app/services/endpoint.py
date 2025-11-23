"""
Backward compatibility module - imports from the refactored endpoint module.

This file maintains backward compatibility for existing imports.
New code should import directly from rhesis.backend.app.services.endpoint.
"""

from rhesis.backend.app.services.endpoint import (
    EndpointService,
    endpoint_service,
    get_schema,
    invoke,
    sync_sdk_endpoints,
)

# Re-export for backward compatibility
__all__ = [
    "EndpointService",
    "endpoint_service",
    "invoke",
    "get_schema",
    "sync_sdk_endpoints",
]
