"""Tests for the stateless conversation management in EndpointService.

These tests exercise the two-phase commit logic, conversation_id
injection, and error-handling paths that live in
``EndpointService.invoke_endpoint()`` (the orchestration layer that
is NOT covered by the invoker unit tests).
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointConnectionType
from rhesis.backend.app.services.endpoint.service import EndpointService
from rhesis.backend.app.services.invokers.conversation.store import (
    _reset_conversation_store,
    get_conversation_store,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stateless_endpoint(**overrides) -> Endpoint:
    """Create a stateless endpoint stub."""
    ep = MagicMock(spec=Endpoint)
    ep.name = overrides.get("name", "stateless-ep")
    ep.id = overrides.get("id", "ep-1")
    ep.connection_type = EndpointConnectionType.REST.value
    ep.method = "POST"
    ep.url = "https://api.example.com/v1/chat/completions"
    ep.endpoint_path = None
    ep.request_mapping = overrides.get(
        "request_mapping",
        {
            "system_prompt": "You are helpful.",
            "messages": "{{ messages }}",
            "model": "gpt-4",
        },
    )
    ep.response_mapping = overrides.get(
        "response_mapping", {"output": "$.choices[0].message.content"}
    )
    ep.request_headers = {"Content-Type": "application/json"}
    ep.auth_type = "bearer_token"
    ep.auth_token = "test-token"
    ep.project_id = "proj-1"
    ep.environment = "development"
    ep.config_source = "manual"
    ep.response_format = "json"
    return ep


def _make_stateful_endpoint(**overrides) -> Endpoint:
    """Create a stateful endpoint stub (no {{ messages }})."""
    ep = _make_stateless_endpoint(**overrides)
    ep.request_mapping = overrides.get("request_mapping", {"message": "{{ input }}"})
    ep.response_mapping = overrides.get(
        "response_mapping", {"output": "$.text", "conversation_id": "$.cid"}
    )
    return ep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_store():
    """Reset the global conversation store before each test."""
    _reset_conversation_store()
    yield
    _reset_conversation_store()


@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def service():
    return EndpointService()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStatelessConversationManagement:
    """Core stateless endpoint orchestration tests."""

    @pytest.mark.asyncio
    async def test_first_turn_creates_conversation_and_injects_id(self, mock_db, service):
        """First invocation creates a conversation and returns conversation_id."""
        endpoint = _make_stateless_endpoint()

        with (
            patch.object(service, "_get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.endpoint.service.create_invoker") as mock_create,
        ):
            mock_invoker = AsyncMock()
            mock_invoker.automatic_tracing = True
            mock_invoker.invoke.return_value = {
                "output": "Hello!",
            }
            mock_create.return_value = mock_invoker

            result = await service.invoke_endpoint(
                db=mock_db,
                endpoint_id="ep-1",
                input_data={"input": "Hi"},
            )

        assert "conversation_id" in result
        assert result["output"] == "Hello!"

        # The store should have the user + assistant committed
        store = get_conversation_store()
        msgs = store.get_messages(result["conversation_id"])
        assert msgs is not None
        assert len(msgs) == 3  # system + user + assistant
        assert msgs[0]["role"] == "system"
        assert msgs[1] == {"role": "user", "content": "Hi"}
        assert msgs[2] == {"role": "assistant", "content": "Hello!"}

    @pytest.mark.asyncio
    async def test_second_turn_continues_conversation(self, mock_db, service):
        """Passing conversation_id back continues the same conversation."""
        endpoint = _make_stateless_endpoint()

        with (
            patch.object(service, "_get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.endpoint.service.create_invoker") as mock_create,
        ):
            mock_invoker = AsyncMock()
            mock_invoker.automatic_tracing = True
            mock_invoker.invoke.side_effect = [
                {"output": "Hello!"},
                {"output": "I'm great, thanks!"},
            ]
            mock_create.return_value = mock_invoker

            # Turn 1
            r1 = await service.invoke_endpoint(
                db=mock_db,
                endpoint_id="ep-1",
                input_data={"input": "Hi"},
            )
            cid = r1["conversation_id"]

            # Turn 2
            r2 = await service.invoke_endpoint(
                db=mock_db,
                endpoint_id="ep-1",
                input_data={
                    "input": "How are you?",
                    "conversation_id": cid,
                },
            )

        assert r2["conversation_id"] == cid
        assert r2["output"] == "I'm great, thanks!"

        # Verify messages were built correctly for the second call
        call2_input = mock_invoker.invoke.call_args_list[1].args[2]
        messages = call2_input["messages"]
        assert len(messages) == 4  # system + user + assistant + user
        assert messages[3] == {"role": "user", "content": "How are you?"}

        # CRITICAL: conversation_id must NOT leak into the data that
        # goes to the template renderer / external API.  It is an
        # internal tracking field managed by the store.
        assert "conversation_id" not in call2_input, (
            "conversation_id leaked into enriched_input_data — "
            "the template renderer would propagate it to aliases "
            "like session_id and the external API would reject it"
        )

        # Verify final store state
        store = get_conversation_store()
        stored = store.get_messages(cid)
        assert len(stored) == 5  # system + u + a + u + a

    @pytest.mark.asyncio
    async def test_messages_array_passthrough_skips_history(self, mock_db, service):
        """When caller provides messages directly, store is bypassed."""
        endpoint = _make_stateless_endpoint()
        custom_messages = [
            {"role": "user", "content": "Custom"},
        ]

        with (
            patch.object(service, "_get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.endpoint.service.create_invoker") as mock_create,
        ):
            mock_invoker = AsyncMock()
            mock_invoker.automatic_tracing = True
            mock_invoker.invoke.return_value = {"output": "OK"}
            mock_create.return_value = mock_invoker

            result = await service.invoke_endpoint(
                db=mock_db,
                endpoint_id="ep-1",
                input_data={
                    "input": "ignored",
                    "messages": custom_messages,
                },
            )

        # conversation_id should NOT be injected (not managed by us)
        assert "conversation_id" not in result

    @pytest.mark.asyncio
    async def test_error_response_does_not_commit_messages(self, mock_db, service):
        """On error, the user message must NOT be committed to the store."""
        from rhesis.backend.app.services.invokers.common.schemas import (
            ErrorResponse,
        )

        endpoint = _make_stateless_endpoint()

        with (
            patch.object(service, "_get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.endpoint.service.create_invoker") as mock_create,
        ):
            mock_invoker = AsyncMock()
            mock_invoker.automatic_tracing = True
            mock_invoker.invoke.return_value = ErrorResponse(
                output="Endpoint failed",
                error_type="http_error",
                message="HTTP 500",
            )
            mock_create.return_value = mock_invoker

            result = await service.invoke_endpoint(
                db=mock_db,
                endpoint_id="ep-1",
                input_data={"input": "Hi"},
            )

        # ErrorResponse is returned as-is (not a dict)
        assert not isinstance(result, dict)

        # The store should have the conversation but with ONLY the
        # system prompt -- the user message must not have been committed.
        store = get_conversation_store()
        # We can't easily get the conversation_id since it wasn't
        # injected, so check that no history has user messages.
        for cid, hist in store._histories.items():
            msgs = hist.get_messages()
            user_msgs = [m for m in msgs if m["role"] == "user"]
            assert len(user_msgs) == 0, (
                f"Conversation {cid} should have no user messages "
                f"after a failed invocation, but has: {user_msgs}"
            )

    @pytest.mark.asyncio
    async def test_empty_output_still_injects_conversation_id(self, mock_db, service):
        """Even with empty output, conversation_id is returned."""
        endpoint = _make_stateless_endpoint()

        with (
            patch.object(service, "_get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.endpoint.service.create_invoker") as mock_create,
        ):
            mock_invoker = AsyncMock()
            mock_invoker.automatic_tracing = True
            mock_invoker.invoke.return_value = {"output": ""}
            mock_create.return_value = mock_invoker

            result = await service.invoke_endpoint(
                db=mock_db,
                endpoint_id="ep-1",
                input_data={"input": "Hi"},
            )

        assert "conversation_id" in result

    @pytest.mark.asyncio
    async def test_empty_input_not_committed(self, mock_db, service):
        """Empty input should not produce a user message in the store."""
        endpoint = _make_stateless_endpoint()

        with (
            patch.object(service, "_get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.endpoint.service.create_invoker") as mock_create,
        ):
            mock_invoker = AsyncMock()
            mock_invoker.automatic_tracing = True
            mock_invoker.invoke.return_value = {"output": "Hello!"}
            mock_create.return_value = mock_invoker

            result = await service.invoke_endpoint(
                db=mock_db,
                endpoint_id="ep-1",
                input_data={"input": ""},
            )

        cid = result["conversation_id"]
        store = get_conversation_store()
        msgs = store.get_messages(cid)
        # Only system prompt + assistant (no empty user message)
        user_msgs = [m for m in msgs if m["role"] == "user"]
        assert len(user_msgs) == 0

    @pytest.mark.asyncio
    async def test_expired_conversation_starts_fresh(self, mock_db, service):
        """If the conversation_id is expired/unknown, a new one is created."""
        endpoint = _make_stateless_endpoint()

        with (
            patch.object(service, "_get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.endpoint.service.create_invoker") as mock_create,
        ):
            mock_invoker = AsyncMock()
            mock_invoker.automatic_tracing = True
            mock_invoker.invoke.return_value = {"output": "Fresh start"}
            mock_create.return_value = mock_invoker

            result = await service.invoke_endpoint(
                db=mock_db,
                endpoint_id="ep-1",
                input_data={
                    "input": "Hello",
                    "conversation_id": "expired-or-unknown-id",
                },
            )

        # Should get a NEW conversation_id, not the expired one
        assert result["conversation_id"] != "expired-or-unknown-id"

    @pytest.mark.asyncio
    async def test_stateful_endpoint_not_affected(self, mock_db, service):
        """Stateful endpoints skip the stateless conversation management."""
        endpoint = _make_stateful_endpoint()

        with (
            patch.object(service, "_get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.endpoint.service.create_invoker") as mock_create,
        ):
            mock_invoker = AsyncMock()
            mock_invoker.automatic_tracing = True
            mock_invoker.invoke.return_value = {
                "output": "Response",
                "conversation_id": "external-cid",
            }
            mock_create.return_value = mock_invoker

            result = await service.invoke_endpoint(
                db=mock_db,
                endpoint_id="ep-1",
                input_data={"input": "Hi"},
            )

        # conversation_id should come from the endpoint, not injected
        assert result.get("conversation_id") == "external-cid"

        # Store should be empty (no stateless management)
        store = get_conversation_store()
        assert len(store._histories) == 0

    @pytest.mark.asyncio
    async def test_no_system_prompt_endpoint(self, mock_db, service):
        """Stateless endpoint without system_prompt still works."""
        endpoint = _make_stateless_endpoint(
            request_mapping={
                "messages": "{{ messages }}",
                "model": "gpt-4",
            }
        )

        with (
            patch.object(service, "_get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.endpoint.service.create_invoker") as mock_create,
        ):
            mock_invoker = AsyncMock()
            mock_invoker.automatic_tracing = True
            mock_invoker.invoke.return_value = {"output": "Hello!"}
            mock_create.return_value = mock_invoker

            result = await service.invoke_endpoint(
                db=mock_db,
                endpoint_id="ep-1",
                input_data={"input": "Hi"},
            )

        cid = result["conversation_id"]
        store = get_conversation_store()
        msgs = store.get_messages(cid)
        # No system prompt -> user + assistant only
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
