"""
Middleware package for the Rhesis backend application.

This package contains middleware components for handling cross-cutting concerns
such as security, logging, and request processing.
"""

from .organization_filter import (
    OrganizationFilterMiddleware,
    SessionWithOrganizationFilter,
    bypass_organization_filter,
    configure_organization_filtering,
    get_organization_aware_session,
    organization_aware_query,
    organization_filter,
    setup_query_logging,
    with_organization_context,
)

__all__ = [
    "OrganizationFilterMiddleware",
    "organization_filter",
    "with_organization_context",
    "bypass_organization_filter",
    "organization_aware_query",
    "SessionWithOrganizationFilter",
    "get_organization_aware_session",
    "configure_organization_filtering",
    "setup_query_logging",
]
