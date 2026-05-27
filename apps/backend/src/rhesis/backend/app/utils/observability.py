"""Observability utilities for Rhesis backend."""

import logging

from rhesis.sdk.clients import RhesisClient

logger = logging.getLogger(__name__)

# Initialize RhesisClient at module import time (required for @endpoint decorators)
try:
    rhesis_client = RhesisClient.from_environment()
    if rhesis_client and not getattr(rhesis_client, "project_id", None):
        logger.info("No project_id found, defaulting to DisabledClient")
        from rhesis.sdk.clients import DisabledClient

        rhesis_client = DisabledClient()
except Exception as e:
    logger.debug(f"RhesisClient initialization deferred (will retry in lifespan): {e}")
    rhesis_client = None
