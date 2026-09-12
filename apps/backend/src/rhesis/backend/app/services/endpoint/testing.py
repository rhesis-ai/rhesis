"""Endpoint test-configuration invocation.

Provides ``test_endpoint``, which invokes a transient (unsaved) endpoint
configuration so users can validate connectivity and request/response
mappings without persisting anything to the database.

Only REST endpoints with BEARER_TOKEN auth are supported for testing.

Neither entry point takes a database session. Both invoke a transient
``Endpoint`` that is never added to a session, and the invoker only reaches for
one to refresh a client-credentials token (a write to the *stored* row) or to
resume a conversation trace (needs ``project_id``, which a transient endpoint
has not got). Both callers here are coroutines on the event loop, so a session
they could reach for would be a psycopg2 call on it -- see
``tests/backend/test_no_sync_db_on_loop.py``.
"""

import logging
from typing import Any, Dict

from fastapi import HTTPException

from rhesis.backend.app.error_handlers import internal_error
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import (
    EndpointAuthType,
    EndpointConfigSource,
    EndpointConnectionType,
    EndpointEnvironment,
    EndpointResponseFormat,
)
from rhesis.backend.app.schemas.endpoint import EndpointTestRequest
from rhesis.backend.app.services.invokers import create_invoker
from rhesis.backend.app.services.invokers.context import InvocationContext
from rhesis.backend.app.services.invokers.conversation import ConversationTracker

logger = logging.getLogger(__name__)


async def test_endpoint(
    test_config: EndpointTestRequest,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Dict[str, Any]:
    """Invoke a transient endpoint configuration without persisting it.

    Validates that the configuration is testable (REST + BEARER_TOKEN), builds
    a temporary ``Endpoint`` ORM object, enriches the input with org/user
    context, handles stateless message history for one-shot testing, and
    delegates to the standard invoker pipeline.

    Args:
        test_config: Endpoint test configuration supplied by the caller.
        organization_id: Organization ID injected into request context (CRITICAL).
        user_id: User ID injected into request context (CRITICAL).

    Returns:
        Dict containing the mapped response from the endpoint.

    Raises:
        HTTPException: If the configuration is invalid or invocation fails.
    """

    def _enum_value(enum_or_str, _cls) -> str:
        return enum_or_str.value if hasattr(enum_or_str, "value") else str(enum_or_str)

    connection_type_str = _enum_value(test_config.connection_type, EndpointConnectionType)
    auth_type_str = _enum_value(test_config.auth_type, EndpointAuthType)
    response_format_str = _enum_value(test_config.response_format, EndpointResponseFormat)

    if connection_type_str != EndpointConnectionType.REST.value:
        raise HTTPException(
            status_code=400,
            detail=(f"Only REST endpoints are supported for testing. Got: {connection_type_str}"),
        )

    if auth_type_str != EndpointAuthType.BEARER_TOKEN.value:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Only BEARER_TOKEN authentication is supported for testing. Got: {auth_type_str}"
            ),
        )

    logger.debug("Testing endpoint configuration: %s (%s)", test_config.url, connection_type_str)

    try:
        endpoint = Endpoint(
            name="test",
            connection_type=connection_type_str,
            url=test_config.url,
            method=test_config.method,
            endpoint_path=test_config.endpoint_path,
            request_headers=test_config.request_headers,
            query_params=test_config.query_params,
            request_mapping=test_config.request_mapping,
            response_mapping=test_config.response_mapping,
            response_format=response_format_str,
            auth_type=auth_type_str,
            auth_token=test_config.auth_token,
            environment=EndpointEnvironment.DEVELOPMENT.value,
            config_source=EndpointConfigSource.MANUAL.value,
        )

        enriched_input_data = test_config.input_data.copy()
        if organization_id:
            enriched_input_data["organization_id"] = organization_id
        if user_id:
            enriched_input_data["user_id"] = user_id

        # Stateless endpoint: build a one-shot messages array (no session store).
        if (
            ConversationTracker.detect_stateless_mode(endpoint)
            and "messages" not in enriched_input_data
        ):
            messages: list = []
            system_prompt = ConversationTracker.extract_system_prompt(endpoint)
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            user_input = enriched_input_data.get("input", "")
            if user_input:
                messages.append({"role": "user", "content": user_input})
            enriched_input_data["messages"] = messages
            enriched_input_data.pop("conversation_id", None)

        # No session: a REST + BEARER_TOKEN config reads its token off the
        # transient endpoint above, and nothing here is persisted.
        context = InvocationContext(
            db=None,
            endpoint=endpoint,
            input_data=enriched_input_data,
        )
        result = await create_invoker(context).invoke()
        logger.debug("Endpoint test invocation completed")
        return result
    except HTTPException:
        # What the user ran the test to find out -- a refused connection, a
        # rejected token, an unparseable body -- is *returned* by invoke() as an
        # ErrorResponse, not raised (services/invokers/rest_invoker.py). The only
        # thing raised out of it is a configuration HTTPException carrying its own
        # status, so wrapping it here would turn a 400 into a 500.
        raise
    except ValueError as exc:
        logger.warning("Invalid endpoint test configuration: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise internal_error(exc, context="testing endpoint") from exc


def build_mapping_test_endpoint(
    endpoint: Endpoint,
    request_mapping: dict,
    response_mapping: dict,
    response_format: str | None = None,
) -> Endpoint:
    """Copy a stored endpoint, swapping in the caller's draft mappings.

    Synchronous and session-touching by nature: every attribute read below can
    lazy-load off ``endpoint``'s session, so callers on the event loop must run
    this in a worker thread (``anyio.to_thread.run_sync``). The copy is
    transient -- never added to a session -- which is what keeps the draft out
    of the stored row.
    """
    return Endpoint(
        name=endpoint.name,
        connection_type=endpoint.connection_type,
        url=endpoint.url,
        method=endpoint.method,
        endpoint_path=endpoint.endpoint_path,
        request_headers=endpoint.request_headers,
        query_params=endpoint.query_params,
        request_mapping=request_mapping,
        response_mapping=response_mapping,
        response_format=response_format or endpoint.response_format,
        auth_type=endpoint.auth_type,
        auth_token=endpoint.auth_token,
        client_id=endpoint.client_id,
        client_secret=endpoint.client_secret,
        token_url=endpoint.token_url,
        scopes=endpoint.scopes,
        audience=endpoint.audience,
        extra_payload=endpoint.extra_payload,
        last_token=endpoint.last_token,
        last_token_expires_at=endpoint.last_token_expires_at,
        environment=endpoint.environment,
        config_source=endpoint.config_source,
        disable_tracing=True,
    )


async def test_endpoint_mapping(
    draft_endpoint: Endpoint,
    input_data: dict,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Dict[str, Any]:
    """Invoke a draft-mapping copy of a stored endpoint.

    Uses the stored endpoint's URL, method, headers and auth credentials, but
    the caller-supplied draft mappings instead of the saved ones. This lets the
    frontend test unsaved mapping changes without exposing the stored auth
    token to the browser.

    ``draft_endpoint`` comes from :func:`build_mapping_test_endpoint`, built by
    the caller in a worker thread so this coroutine never reads an attribute
    that could lazy-load.
    """
    try:
        enriched_input_data = input_data.copy()
        if organization_id:
            enriched_input_data["organization_id"] = organization_id
        if user_id:
            enriched_input_data["user_id"] = user_id

        if (
            ConversationTracker.detect_stateless_mode(draft_endpoint)
            and "messages" not in enriched_input_data
        ):
            messages: list = []
            system_prompt = ConversationTracker.extract_system_prompt(draft_endpoint)
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            user_input = enriched_input_data.get("input", "")
            if user_input:
                messages.append({"role": "user", "content": user_input})
            enriched_input_data["messages"] = messages
            enriched_input_data.pop("conversation_id", None)

        # No session, as in test_endpoint above: the draft copy is transient and
        # carries no project_id, so nothing the invoker does with one applies.
        context = InvocationContext(
            db=None, endpoint=draft_endpoint, input_data=enriched_input_data
        )
        result = await create_invoker(context).invoke()
        logger.debug("Endpoint mapping test completed")
        return result
    except HTTPException:
        # Same as test_endpoint above: an invoker reports the user's endpoint by
        # returning an ErrorResponse, and only raises for configuration problems
        # that already carry the right status.
        raise
    except ValueError as exc:
        logger.warning("Invalid endpoint mapping test: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise internal_error(exc, context="testing endpoint mapping") from exc
