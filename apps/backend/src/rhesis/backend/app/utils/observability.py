"""Observability utilities for Rhesis backend."""

import logging
import os
import uuid
from typing import Dict, Optional, Tuple

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


# api_key -> (organization_id, project_id), or None when the key is not one of ours.
_ingest_scopes: Dict[str, Optional[Tuple[str, str]]] = {}


def sdk_ingest_scope() -> Optional[Tuple[str, str]]:
    """The (organization_id, project_id) this process's own SDK spans are ingested under.

    Mirrors what ``POST /telemetry/traces`` derives from the client's API key, so
    the backend can park data for its own spans in the right tenant scope.
    Returns None when tracing is off or the key belongs to another instance.
    """
    from rhesis.sdk.decorators._state import get_default_client

    client = get_default_client()
    api_key = getattr(client, "api_key", None)
    project_id = getattr(client, "project_id", None)
    if not api_key or not project_id:
        return None
    if api_key not in _ingest_scopes:
        organization_id = _organization_for_api_key(api_key)
        # Same form the ingest route keys by (str of a parsed UUID).
        try:
            project_id = str(uuid.UUID(str(project_id)))
        except ValueError:
            organization_id = None
        _ingest_scopes[api_key] = (
            (organization_id, project_id) if organization_id is not None else None
        )
    return _ingest_scopes[api_key]


def _organization_for_api_key(api_key: str) -> Optional[str]:
    from rhesis.backend.app.crud import user as user_crud
    from rhesis.backend.app.crud.token import get_token_by_value
    from rhesis.backend.app.database import get_db

    with get_db() as db:
        token = get_token_by_value(db, api_key)
        user = user_crud.get_user_by_id(db, token.user_id) if token else None
        if user is None or user.organization_id is None:
            return None
        return str(user.organization_id)
