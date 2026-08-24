"""Observability utilities for Rhesis backend."""

import logging
import os

from rhesis.sdk.clients import RhesisClient

logger = logging.getLogger(__name__)


def _build_test_identity_override():
    """Build the local identity to use for connector-invoked endpoints.

    When this backend's own ``@endpoint`` functions (e.g. the architect) are
    triggered by a *remote* Rhesis instance over the SDK connector — for
    testing this backend as a connected endpoint of dev/stg/prod — the
    remote instance's organization/user identity would otherwise flow into
    local DB scoping, where it doesn't exist. Setting both
    RHESIS_TEST_ORGANIZATION_ID and RHESIS_TEST_USER_ID substitutes a local
    identity instead. RHESIS_TEST_PROJECT_ID is optional; unset means
    unscoped locally. Existence of these ids is checked once at startup in
    ``main.py``'s lifespan.
    """
    organization_id = os.getenv("RHESIS_TEST_ORGANIZATION_ID") or None
    user_id = os.getenv("RHESIS_TEST_USER_ID") or None
    if not organization_id or not user_id:
        return None

    from rhesis.sdk.context import EndpointContext

    logger.warning(
        "RHESIS_TEST_ORGANIZATION_ID/RHESIS_TEST_USER_ID set — connector-invoked "
        "endpoints will run as organization=%s, user=%s instead of the identity "
        "sent by the remote backend.",
        organization_id,
        user_id,
    )
    return EndpointContext(
        organization_id=organization_id,
        user_id=user_id,
        project_id=os.getenv("RHESIS_TEST_PROJECT_ID") or "",
    )


# Initialize RhesisClient at module import time (required for @endpoint decorators)
try:
    rhesis_client = RhesisClient.from_environment(identity_override=_build_test_identity_override())
    if rhesis_client and not getattr(rhesis_client, "project_id", None):
        logger.info("No project_id found, defaulting to DisabledClient")
        from rhesis.sdk.clients import DisabledClient

        rhesis_client = DisabledClient()
except Exception as e:
    logger.debug(f"RhesisClient initialization deferred (will retry in lifespan): {e}")
    rhesis_client = None
