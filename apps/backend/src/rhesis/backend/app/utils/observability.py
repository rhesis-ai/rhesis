"""Observability utilities for Rhesis backend."""

import logging

from rhesis.sdk.clients import RhesisClient

logger = logging.getLogger(__name__)

# SDK client for @endpoint / @observe on backend-resident agents (MCP, etc.).
# RHESIS_CONNECTOR_DISABLED=true (default in compose) → DisabledClient (no SDK overhead).
# RHESIS_CONNECTOR_DISABLED=false → RhesisClient (tracing when credentials are set).
try:
    internal_tracer = RhesisClient.from_environment()
except Exception as e:
    logger.debug(f"Failed to initialize internal tracer: {e}")
    internal_tracer = None
