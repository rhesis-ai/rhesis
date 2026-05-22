"""Observability utilities for Rhesis backend."""

import logging

from rhesis.sdk.clients import RhesisClient

logger = logging.getLogger(__name__)

# Tracer for internal Rhesis agent observability.
# RHESIS_INTERNAL_OBSERVABILITY=false|unset → DisabledClient (no traces).
# RHESIS_INTERNAL_OBSERVABILITY=true → RhesisClient (traces to Rhesis's own org).
# Disabled by default — customer usage of internal agents is never traced.
try:
    internal_tracer = RhesisClient.from_internal_environment()
except Exception as e:
    logger.debug(f"Failed to initialize internal tracer: {e}")
    internal_tracer = None
