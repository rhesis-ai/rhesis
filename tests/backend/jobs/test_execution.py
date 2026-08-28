"""
Tests for BackendEndpointTarget in rhesis.backend.jobs.execution.penelope_target

Covers the target's use of the unified EndpointService path: the input_data shape
it sends, and how it carries conversation_id across turns.
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from sqlalchemy.orm import Session

from rhesis.backend.jobs.execution.penelope_target import BackendEndpointTarget


class TestBackendEndpointTargetStateless:
    """Test that BackendEndpointTarget uses the unified EndpointService path.

    Since history management now lives in EndpointService, these tests
    verify that the target:
    1. Sends the right input_data shape (no messages array -- that's
       EndpointService's job now)
    2. Passes conversation_id from the response back on subsequent turns
    3. Works identically for stateless and stateful endpoints
    """

    def _create_target(
        self,
        mock_db,
        endpoint_id,
        mock_endpoint_service,
        mock_endpoint,
        organization_id=None,
    ):
        """Helper to create a BackendEndpointTarget with common mocking."""
        with (
            patch(
                "rhesis.backend.jobs.execution.penelope_target.get_endpoint_service",
                return_value=mock_endpoint_service,
            ),
            patch(
                "rhesis.backend.jobs.execution.penelope_target.endpoint_crud.get_endpoint",
                return_value=mock_endpoint,
            ),
        ):
            return BackendEndpointTarget(
                db=mock_db,
                endpoint_id=endpoint_id,
                organization_id=organization_id,
            )

    def _make_mock_endpoint(self):
        """Create a generic mock endpoint."""
        mock_endpoint = Mock()
        mock_endpoint.name = "test-endpoint"
        mock_endpoint.url = "https://api.example.com/v1/chat"
        mock_endpoint.description = "Test endpoint"
        mock_endpoint.connection_type = "REST"
        mock_endpoint.request_mapping = {"message": "{{ input }}"}
        mock_endpoint.response_mapping = {"output": "$.text"}
        return mock_endpoint

    def test_first_turn_sends_input_without_conversation_id(self):
        """First call sends input without conversation_id."""
        mock_db = Mock(spec=Session)
        endpoint_id = str(uuid4())

        mock_endpoint_service = Mock()
        mock_endpoint_service.invoke_endpoint = AsyncMock(
            return_value={
                "output": "Hello!",
                "conversation_id": "srv-session-1",
            }
        )
        mock_endpoint = self._make_mock_endpoint()

        target = self._create_target(
            mock_db,
            endpoint_id,
            mock_endpoint_service,
            mock_endpoint,
        )
        response = target.send_message("Hi")

        assert response.success is True
        assert response.content == "Hello!"

        call_kwargs = mock_endpoint_service.invoke_endpoint.call_args.kwargs
        input_data = call_kwargs["input_data"]
        assert input_data["input"] == "Hi"
        assert "conversation_id" not in input_data

    def test_second_turn_passes_conversation_id_from_response(self):
        """conversation_id from first response is sent in second call."""
        mock_db = Mock(spec=Session)
        endpoint_id = str(uuid4())

        mock_endpoint_service = Mock()
        mock_endpoint_service.invoke_endpoint = AsyncMock(
            side_effect=[
                {"output": "Hi!", "conversation_id": "srv-session-1"},
                {"output": "I'm fine.", "conversation_id": "srv-session-1"},
            ]
        )
        mock_endpoint = self._make_mock_endpoint()

        target = self._create_target(
            mock_db,
            endpoint_id,
            mock_endpoint_service,
            mock_endpoint,
        )

        resp1 = target.send_message("Hello")
        # Penelope passes conversation_id from previous response
        resp2 = target.send_message(
            "How are you?",
            conversation_id=resp1.conversation_id,
        )

        # Second call should include conversation_id
        second_call = mock_endpoint_service.invoke_endpoint.call_args_list[1]
        input_data = second_call.kwargs["input_data"]
        assert input_data["conversation_id"] == "srv-session-1"

        assert resp2.success is True
        assert resp2.conversation_id == "srv-session-1"

    def test_conversation_id_stable_across_turns(self):
        """conversation_id in responses stays consistent across turns."""
        mock_db = Mock(spec=Session)
        endpoint_id = str(uuid4())

        session = "stable-session-42"
        mock_endpoint_service = Mock()
        mock_endpoint_service.invoke_endpoint = AsyncMock(
            side_effect=[
                {"output": "A", "conversation_id": session},
                {"output": "B", "conversation_id": session},
                {"output": "C", "conversation_id": session},
            ]
        )
        mock_endpoint = self._make_mock_endpoint()

        target = self._create_target(
            mock_db,
            endpoint_id,
            mock_endpoint_service,
            mock_endpoint,
        )

        r1 = target.send_message("1")
        r2 = target.send_message("2", conversation_id=r1.conversation_id)
        r3 = target.send_message("3", conversation_id=r2.conversation_id)

        assert r1.conversation_id == session
        assert r2.conversation_id == session
        assert r3.conversation_id == session

    def test_none_response_returns_failure(self):
        """When invoke_endpoint returns None, response is a failure."""
        mock_db = Mock(spec=Session)
        endpoint_id = str(uuid4())

        mock_endpoint_service = Mock()
        mock_endpoint_service.invoke_endpoint = AsyncMock(return_value=None)
        mock_endpoint = self._make_mock_endpoint()

        target = self._create_target(
            mock_db,
            endpoint_id,
            mock_endpoint_service,
            mock_endpoint,
        )
        response = target.send_message("Hello")

        assert response.success is False
        assert "None" in response.error

    def test_error_response_returns_failure(self):
        """When invoker returns ErrorResponse, target returns failure."""
        from rhesis.backend.app.services.invokers.common.schemas import (
            ErrorResponse,
        )

        mock_db = Mock(spec=Session)
        endpoint_id = str(uuid4())

        error_resp = ErrorResponse(
            output="Something went wrong",
            error_type="http_error",
            message="HTTP error occurred",
        )
        mock_endpoint_service = Mock()
        mock_endpoint_service.invoke_endpoint = AsyncMock(
            return_value=error_resp,
        )
        mock_endpoint = self._make_mock_endpoint()

        target = self._create_target(
            mock_db,
            endpoint_id,
            mock_endpoint_service,
            mock_endpoint,
        )
        response = target.send_message("Hello")

        assert response.success is False

    def test_empty_message_rejected(self):
        """Empty or whitespace-only messages are rejected."""
        mock_db = Mock(spec=Session)
        endpoint_id = str(uuid4())
        mock_endpoint_service = Mock()
        mock_endpoint = self._make_mock_endpoint()

        target = self._create_target(
            mock_db,
            endpoint_id,
            mock_endpoint_service,
            mock_endpoint,
        )

        assert target.send_message("").success is False
        assert target.send_message("   ").success is False

    def test_long_message_rejected(self):
        """Messages exceeding 10 000 chars are rejected."""
        mock_db = Mock(spec=Session)
        endpoint_id = str(uuid4())
        mock_endpoint_service = Mock()
        mock_endpoint = self._make_mock_endpoint()

        target = self._create_target(
            mock_db,
            endpoint_id,
            mock_endpoint_service,
            mock_endpoint,
        )

        response = target.send_message("x" * 10001)
        assert response.success is False
        assert "too long" in response.error.lower()


class TestBackendEndpointTargetConversationContext:
    """Test conversation context maintenance in BackendEndpointTarget"""

    def test_conversation_id_extraction_from_response(self):
        """Test that BackendEndpointTarget correctly extracts conversation_id from endpoint responses"""
        from unittest.mock import Mock
        from uuid import uuid4

        from rhesis.backend.jobs.execution.penelope_target import BackendEndpointTarget

        # Mock database session
        mock_db = Mock(spec=Session)

        # Mock endpoint service response with conversation_id
        mock_endpoint_service = Mock()
        mock_endpoint_service.invoke_endpoint = AsyncMock(
            return_value={
                "output": "Test response",
                "conversation_id": "test-session-123",
                "metadata": {"test": "data"},
            }
        )

        # Create valid UUIDs for testing
        endpoint_id = str(uuid4())
        organization_id = str(uuid4())

        # Create BackendEndpointTarget instance
        with (
            patch(
                "rhesis.backend.jobs.execution.penelope_target.get_endpoint_service",
                return_value=mock_endpoint_service,
            ),
            patch(
                "rhesis.backend.jobs.execution.penelope_target.endpoint_crud.get_endpoint"
            ) as mock_get_endpoint,
        ):
            # Mock endpoint exists
            mock_endpoint = Mock()
            mock_endpoint.name = "test-endpoint"
            mock_endpoint.url = "https://test.com"
            mock_endpoint.description = "Test endpoint"
            mock_endpoint.connection_type = "REST"
            mock_get_endpoint.return_value = mock_endpoint

            target = BackendEndpointTarget(
                db=mock_db, endpoint_id=endpoint_id, organization_id=organization_id
            )

            # Send message without conversation_id
            response = target.send_message("Hello")

            # Verify response contains extracted conversation_id
            assert response.success is True
            assert response.content == "Test response"
            assert response.conversation_id == "test-session-123"

    def test_conversation_id_passthrough_to_endpoint(self):
        """Test that BackendEndpointTarget passes conversation_id to endpoint service"""
        from unittest.mock import Mock
        from uuid import uuid4

        from rhesis.backend.jobs.execution.penelope_target import BackendEndpointTarget

        # Mock database session
        mock_db = Mock(spec=Session)

        # Mock endpoint service
        mock_endpoint_service = Mock()
        mock_endpoint_service.invoke_endpoint = AsyncMock(
            return_value={
                "output": "Follow-up response",
                "conversation_id": "test-session-123",
            }
        )

        # Create valid UUIDs for testing
        endpoint_id = str(uuid4())
        organization_id = str(uuid4())

        # Create BackendEndpointTarget instance
        with (
            patch(
                "rhesis.backend.jobs.execution.penelope_target.get_endpoint_service",
                return_value=mock_endpoint_service,
            ),
            patch(
                "rhesis.backend.jobs.execution.penelope_target.endpoint_crud.get_endpoint"
            ) as mock_get_endpoint,
        ):
            # Mock endpoint exists
            mock_endpoint = Mock()
            mock_endpoint.name = "test-endpoint"
            mock_get_endpoint.return_value = mock_endpoint

            target = BackendEndpointTarget(
                db=mock_db, endpoint_id=endpoint_id, organization_id=organization_id
            )

            # Send message with conversation_id
            response = target.send_message("Follow up", conversation_id="test-session-123")

            # Verify endpoint service was called with conversation_id
            mock_endpoint_service.invoke_endpoint.assert_called_once()
            call_args = mock_endpoint_service.invoke_endpoint.call_args
            input_data = call_args.kwargs["input_data"]
            assert input_data["conversation_id"] == "test-session-123"

            # Verify response maintains conversation_id
            assert response.conversation_id == "test-session-123"

    def test_flexible_conversation_field_extraction(self):
        """Test that BackendEndpointTarget handles multiple conversation field names"""
        from unittest.mock import Mock
        from uuid import uuid4

        from rhesis.backend.jobs.execution.penelope_target import BackendEndpointTarget

        # Mock database session
        mock_db = Mock(spec=Session)

        # Mock endpoint service response with thread_id instead of conversation_id
        mock_endpoint_service = Mock()
        mock_endpoint_service.invoke_endpoint = AsyncMock(
            return_value={
                "output": "Response with thread_id",
                "thread_id": "thread-456",
                "metadata": {},
            }
        )

        # Create valid UUID for testing
        endpoint_id = str(uuid4())

        # Create BackendEndpointTarget instance
        with (
            patch(
                "rhesis.backend.jobs.execution.penelope_target.get_endpoint_service",
                return_value=mock_endpoint_service,
            ),
            patch(
                "rhesis.backend.jobs.execution.penelope_target.endpoint_crud.get_endpoint"
            ) as mock_get_endpoint,
        ):
            # Mock endpoint exists
            mock_endpoint = Mock()
            mock_get_endpoint.return_value = mock_endpoint

            target = BackendEndpointTarget(db=mock_db, endpoint_id=endpoint_id)

            # Send message with thread_id in kwargs
            response = target.send_message("Hello", thread_id="thread-456")

            # Verify thread_id was extracted and used
            assert response.conversation_id == "thread-456"
