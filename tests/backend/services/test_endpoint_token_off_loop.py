"""The OAuth token refresh must not happen on the event loop.

``AuthenticationManager.get_client_credentials_token`` is a blocking
``requests.post``. The invokers reach for it from inside ``invoke()``, which the
endpoint routes await, so a CLIENT_CREDENTIALS endpoint with an expired cached
token would stall the whole worker for the length of the OAuth round trip -- and
forever if the token URL never answers.

The routes resolve the token during the prefetch they already run in a worker
thread, leaving the awaited invocation a cache hit. These tests are the check
that it really happens there: ``tests/backend/test_no_sync_db_on_loop.py`` only
sees Sessions crossing a handler signature, not blocking calls below it.
"""

import threading
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointAuthType, EndpointConnectionType
from rhesis.backend.app.schemas.endpoint import EndpointMappingTestRequest
from rhesis.backend.app.services.endpoint.off_loop import invoke_endpoint_off_loop
from tests.backend._helpers import records_thread as _recorder

TOKEN_POST = "rhesis.backend.app.services.invokers.auth.manager._token_session.post"


def _oauth_endpoint(expired: bool) -> Endpoint:
    """A stored client-credentials endpoint, with a live or a stale cached token."""
    endpoint = Endpoint(
        id=uuid.uuid4(),
        name="OAuth endpoint",
        connection_type=EndpointConnectionType.REST.value,
        url="https://api.example.com/chat",
        method="POST",
        auth_type=EndpointAuthType.CLIENT_CREDENTIALS.value,
        token_url="https://auth.example.com/oauth/token",
        client_id="client",
        client_secret="secret",
        request_mapping={"input": "{{ input }}"},
        response_mapping={"output": "$.output"},
    )
    endpoint.last_token = "stored-token"
    offset = timedelta(hours=-1) if expired else timedelta(hours=1)
    endpoint.last_token_expires_at = datetime.now(timezone.utc) + offset
    return endpoint


def _token_response(access_token: str) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {"access_token": access_token, "expires_in": 3600}
    return response


def _service(endpoint: Endpoint) -> MagicMock:
    service = MagicMock()
    service._get_endpoint.return_value = endpoint
    service.invoke_endpoint = AsyncMock(return_value={"output": "hello"})
    return service


@pytest.mark.unit
@pytest.mark.asyncio
class TestInvokeRoute:
    async def test_expired_token_is_fetched_in_a_worker_thread(self):
        threads: list = []
        endpoint = _oauth_endpoint(expired=True)
        service = _service(endpoint)

        with patch(TOKEN_POST, _recorder(threads, _token_response("fresh-token"))):
            result = await invoke_endpoint_off_loop(service, MagicMock(), "ep-1", {"input": "hi"})

        assert threads and threading.get_ident() not in threads
        assert result == {"output": "hello"}
        # The awaited invocation now finds a valid cached token and fetches nothing.
        assert endpoint.last_token == "fresh-token"
        assert endpoint.last_token_expires_at > datetime.now(timezone.utc)
        service.invoke_endpoint.assert_awaited_once()

    async def test_a_valid_cached_token_is_not_refetched(self):
        endpoint = _oauth_endpoint(expired=False)
        service = _service(endpoint)

        with patch(TOKEN_POST) as post:
            await invoke_endpoint_off_loop(service, MagicMock(), "ep-1", {"input": "hi"})

        post.assert_not_called()
        assert endpoint.last_token == "stored-token"


@pytest.mark.unit
class TestMappingTestRoute:
    def test_the_draft_copy_carries_a_freshly_fetched_token(self):
        """``/endpoints/{id}/test`` prefetches in the same thread hop as the load."""
        from rhesis.backend.app.routers import endpoint as endpoint_router

        stored = _oauth_endpoint(expired=True)
        request = EndpointMappingTestRequest(
            request_mapping={"input": "{{ input }}"},
            response_mapping={"output": "$.output"},
            input_data={"input": "hi"},
        )

        with (
            patch.object(endpoint_router, "endpoint_crud") as crud,
            patch(TOKEN_POST, return_value=_token_response("draft-token")) as post,
        ):
            crud.get_endpoint.return_value = stored
            draft = endpoint_router._load_draft_endpoint(
                MagicMock(), stored.id, str(uuid.uuid4()), str(uuid.uuid4()), request
            )

        post.assert_called_once()
        assert draft.last_token == "draft-token"
        assert draft.request_mapping == {"input": "{{ input }}"}
        # The refresh lands on the transient copy, exactly where the invoker put it.
        assert stored.last_token == "stored-token"
