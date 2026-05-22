"""Observability utilities for Rhesis backend."""

import logging
import os

from rhesis.sdk.clients import DisabledClient, RhesisClient

logger = logging.getLogger(__name__)

# Tracer for internal Rhesis agent observability.
# Enabled by setting RHESIS_INTERNAL_OBSERVABILITY=true.
# Only RHESIS_API_KEY is needed alongside it.
# Disabled by default — customer usage of internal agents is never traced.
try:
    if os.getenv("RHESIS_INTERNAL_OBSERVABILITY", "false").lower() == "true":
        internal_tracer = RhesisClient.from_environment()
        logger.info("Internal observability enabled")
    else:
        internal_tracer = DisabledClient()
        logger.info("Internal observability disabled (RHESIS_INTERNAL_OBSERVABILITY not set)")
except Exception as e:
    logger.debug(f"Failed to initialize internal tracer: {e}")
    internal_tracer = None
