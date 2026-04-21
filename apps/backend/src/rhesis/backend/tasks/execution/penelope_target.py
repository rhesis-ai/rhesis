"""
Backend-specific endpoint target for Penelope.

This module provides a custom Target implementation that allows Penelope to interact
with Rhesis endpoints directly through the backend's endpoint service, without requiring
SDK initialization. This is used for multi-turn test execution where Penelope runs
within the backend worker context.
"""

import asyncio
import logging
from typing import Any, Coroutine, Dict, List, Optional, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.dependencies import get_endpoint_service
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.penelope.targets.base import Target, TargetResponse

logger = logging.getLogger(__name__)

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run async coroutine in sync context, handling existing event loops.

    If an event loop is running (e.g., Celery), uses a thread pool.
    Otherwise, runs directly with asyncio.run().

    Args:
        coro: Coroutine to execute

    Returns:
        Result of the coroutine
    """
    try:
        asyncio.get_running_loop()
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


class BackendEndpointTarget(Target):
    """
    Backend-specific target implementation for Rhesis endpoints.

    Unlike the SDK's EndpointTarget (used in external scripts), this target works
    directly with the backend's database and endpoint service. This enables Penelope
    to test endpoints from within the backend worker context without SDK initialization.

    Supports two modes:
    - **Sync mode** (original): uses db session and run_async for send_message
    - **Async mode** (batch): uses pre-fetched endpoint, deferred tracing, and
      in-memory trace_id tracking for a_send_message (DB-free during execution)
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        endpoint_id: str = "",
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        test_execution_context: Optional[dict[str, str]] = None,
        endpoint: Optional[Endpoint] = None,
        invoke_max_attempts: int = 4,
        invoke_retry_min_wait: float = 1.0,
        invoke_retry_max_wait: float = 30.0,
    ):
        """
        Initialize the backend endpoint target.

        Args:
            db: Database session (required for sync mode, optional for async batch mode)
            endpoint_id: UUID string of the endpoint to target
            organization_id: Optional organization ID for security filtering
            user_id: Optional user ID for context injection
            test_execution_context: Optional dict with test_run_id, test_result_id, test_id
            endpoint: Optional pre-fetched Endpoint model for DB-free async mode
            invoke_max_attempts: Max invocation attempts (including initial).
            invoke_retry_min_wait: Minimum backoff wait in seconds.
            invoke_retry_max_wait: Maximum backoff wait in seconds.

        Raises:
            ValueError: If endpoint is not found or configuration is invalid
        """
        self.db = db
        self.endpoint_id = endpoint_id or (str(endpoint.id) if endpoint else "")
        self.organization_id = organization_id
        self.user_id = user_id
        self.test_execution_context = test_execution_context
        self.endpoint_service = get_endpoint_service()
        self._invoke_max_attempts = invoke_max_attempts
        self._invoke_retry_min_wait = invoke_retry_min_wait
        self._invoke_retry_max_wait = invoke_retry_max_wait

        self._endpoint = endpoint
        self._deferred_traces: list = []
        self._current_trace_id: Optional[str] = None

        self._endpoint_name = None
        self._endpoint_url = None
        self._endpoint_description = None
        self._endpoint_connection_type = None

        if endpoint:
            self._endpoint_name = endpoint.name
            self._endpoint_url = endpoint.url
            self._endpoint_description = endpoint.description
            self._endpoint_connection_type = endpoint.connection_type
        else:
            is_valid, error = self.validate_configuration()
            if not is_valid:
                raise ValueError(f"Invalid endpoint configuration: {error}")
            self._load_endpoint_metadata()

    def _load_endpoint_metadata(self) -> None:
        """Load endpoint metadata for descriptions and documentation."""
        try:
            endpoint = crud.get_endpoint(
                self.db,
                UUID(self.endpoint_id),
                organization_id=self.organization_id,
                user_id=self.user_id,
            )
            if endpoint:
                self._endpoint_name = endpoint.name
                self._endpoint_url = endpoint.url
                self._endpoint_description = endpoint.description
                self._endpoint_connection_type = endpoint.connection_type
        except Exception as e:
            logger.warning(f"Failed to load endpoint metadata for {self.endpoint_id}: {e}")

    @property
    def target_type(self) -> str:
        """Type identifier for this target."""
        return "backend_endpoint"

    @property
    def target_id(self) -> str:
        """Unique identifier for this target instance."""
        return self.endpoint_id

    @property
    def description(self) -> str:
        """Human-readable description of the target."""
        name = self._endpoint_name or self.endpoint_id
        url = self._endpoint_url or "N/A"
        return f"Backend Endpoint: {name} ({url})"

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """
        Validate the endpoint configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.endpoint_id:
            return False, "Endpoint ID is missing"

        if self._endpoint:
            return True, None

        if not self.db:
            return False, "Database session is None and no pre-fetched endpoint provided"

        try:
            endpoint = crud.get_endpoint(
                self.db,
                UUID(self.endpoint_id),
                organization_id=self.organization_id,
                user_id=self.user_id,
            )
            if not endpoint:
                return False, f"Endpoint {self.endpoint_id} not found or not accessible"
        except Exception as e:
            return False, f"Failed to validate endpoint: {str(e)}"

        return True, None

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_message(message: str) -> Optional["TargetResponse"]:
        """Return an error TargetResponse if the message is invalid, else None."""
        if not message or not message.strip():
            return TargetResponse(success=False, content="", error="Message cannot be empty")
        if len(message) > 10000:
            return TargetResponse(
                success=False,
                content="",
                error="Message too long (max 10000 characters)",
            )
        return None

    @staticmethod
    def _extract_response_metadata(response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract optional fields (metadata, context, tool_calls) from a response dict."""
        metadata: Dict[str, Any] = {}
        if response_data.get("metadata") is not None:
            metadata["endpoint_metadata"] = response_data["metadata"]
        if response_data.get("context"):
            metadata["context"] = response_data["context"]
        if response_data.get("tool_calls"):
            metadata["tool_calls"] = response_data["tool_calls"]
        return metadata

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """
        Send a message to the endpoint via the backend endpoint service.

        The interface is identical for stateless and stateful endpoints.
        Conversation history for stateless endpoints is managed by
        ``EndpointService`` transparently -- callers just pass back the
        ``conversation_id`` from the previous response, exactly as they would
        for a stateful endpoint.

        Args:
            message: The message to send
            conversation_id: Optional conversation/session ID for multi-turn
            files: Optional list of file attachments
            **kwargs: Additional parameters

        Returns:
            TargetResponse with the endpoint's response and conversation_id
        """
        err = self._validate_message(message)
        if err:
            return err

        try:
            # Prepare input data -- same shape for stateless and stateful
            input_data = {"input": message}
            if conversation_id:
                input_data["conversation_id"] = conversation_id
            if files:
                input_data["files"] = files

            logger.debug(
                "BackendEndpointTarget invoking %s, message_len=%d",
                self.endpoint_id,
                len(message),
            )

            response_data = run_async(
                self.endpoint_service.invoke_endpoint(
                    db=self.db,
                    endpoint_id=self.endpoint_id,
                    input_data=input_data,
                    organization_id=self.organization_id,
                    user_id=self.user_id,
                    test_execution_context=self.test_execution_context,
                )
            )

            if response_data is None:
                return TargetResponse(
                    success=False,
                    content="",
                    error="Endpoint invocation returned None",
                )

            # Handle ErrorResponse objects (Pydantic models) from invokers
            from rhesis.backend.app.services.invokers.common.schemas import (
                ErrorResponse,
            )

            if isinstance(response_data, ErrorResponse):
                response_dict = response_data.to_dict()
                return TargetResponse(
                    success=False,
                    content="",
                    error=response_dict.get("output", "Endpoint invocation failed"),
                    metadata={"error_details": response_dict},
                )

            # Extract response content
            response_text = response_data.get("output", "")

            # Extract conversation_id using smart field detection.
            # For stateful endpoints this comes from the external API;
            # for stateless endpoints EndpointService injects conversation_id.
            from rhesis.penelope.conversation import extract_conversation_id

            response_conversation_id = extract_conversation_id(response_data)
            if not response_conversation_id:
                response_conversation_id = conversation_id

            # Build metadata
            response_metadata = {
                "raw_response": response_data,
                "message_sent": message,
                "input_conversation_id": conversation_id,
                "extracted_conversation_id": response_conversation_id,
                **self._extract_response_metadata(response_data),
            }

            logger.debug(
                "BackendEndpointTarget received response from %s, response_len=%d",
                self.endpoint_id,
                len(str(response_text)),
            )

            return TargetResponse(
                success=True,
                content=str(response_text),
                conversation_id=response_conversation_id,
                metadata=response_metadata,
            )

        except ValueError as e:
            logger.warning(f"BackendEndpointTarget validation error for {self.endpoint_id}: {e}")
            return TargetResponse(
                success=False,
                content="",
                error=f"Invalid request: {str(e)}",
            )
        except Exception as e:
            logger.error(
                f"BackendEndpointTarget unexpected error for {self.endpoint_id}: {e}",
                exc_info=True,
            )
            return TargetResponse(
                success=False,
                content="",
                error=f"Unexpected error: {str(e)}",
            )

    async def a_send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """
        Async send_message that directly awaits invoke_endpoint in DB-free mode.

        Uses pre-fetched endpoint and deferred tracing. Trace_ids are tracked
        as instance state across turns for multi-turn conversations.
        """
        err = self._validate_message(message)
        if err:
            return err

        try:
            input_data: Dict[str, Any] = {"input": message}
            if conversation_id:
                input_data["conversation_id"] = conversation_id
            if files:
                input_data["files"] = files

            logger.debug(
                "BackendEndpointTarget (async) invoking %s, message_len=%d",
                self.endpoint_id,
                len(message),
            )

            from rhesis.backend.tasks.execution.batch.retry import invoke_with_retry

            test_id = (self.test_execution_context or {}).get("test_id", "?")

            async def _invoke():
                return await self.endpoint_service.invoke_endpoint(
                    db=None,
                    endpoint_id=self.endpoint_id,
                    input_data=input_data,
                    organization_id=self.organization_id,
                    user_id=self.user_id,
                    test_execution_context=self.test_execution_context,
                    endpoint=self._endpoint,
                    deferred_trace=True,
                    trace_id=self._current_trace_id,
                )

            response_data = await invoke_with_retry(
                _invoke,
                max_attempts=self._invoke_max_attempts,
                min_wait=self._invoke_retry_min_wait,
                max_wait=self._invoke_retry_max_wait,
                label=f"multi_turn[{test_id[:8]}]",
            )

            if response_data is None:
                return TargetResponse(
                    success=False,
                    content="",
                    error="Endpoint invocation returned None",
                )

            deferred_trace = response_data.pop("_deferred_trace", None)
            if deferred_trace:
                self._deferred_traces.append(deferred_trace)
                if not self._current_trace_id:
                    self._current_trace_id = deferred_trace.trace_id

            response_text = response_data.get("output", "")

            from rhesis.penelope.conversation import extract_conversation_id

            response_conversation_id = extract_conversation_id(response_data)
            if not response_conversation_id:
                response_conversation_id = conversation_id

            response_metadata = self._extract_response_metadata(response_data)

            return TargetResponse(
                success=True,
                content=str(response_text),
                conversation_id=response_conversation_id,
                metadata=response_metadata,
            )

        except ValueError as e:
            logger.warning(f"BackendEndpointTarget async validation error: {e}")
            return TargetResponse(
                success=False,
                content="",
                error=f"Invalid request: {str(e)}",
            )
        except Exception as e:
            logger.error(
                f"BackendEndpointTarget async unexpected error: {e}",
                exc_info=True,
            )
            return TargetResponse(
                success=False,
                content="",
                error=f"Unexpected error: {str(e)}",
            )

    def get_tool_documentation(self) -> str:
        """
        Get endpoint-specific documentation for Penelope.

        Returns:
            Documentation string describing how to interact with this endpoint
        """
        name = self._endpoint_name or self.endpoint_id
        url = self._endpoint_url or "N/A"
        description = self._endpoint_description or ""
        connection_type = self._endpoint_connection_type or "REST"

        doc = f"""
Target Type: Backend Endpoint (Rhesis)
Name: {name}
Endpoint ID: {self.endpoint_id}
Connection Type: {connection_type}
URL: {url}
"""

        if description:
            doc += f"\nDescription: {description}\n"

        doc += """
Interface (defined by Rhesis platform):

Input:
  - input: Text message (string)
  - conversation_id: Optional, for multi-turn conversations

Output:
  - output: The response text from the endpoint
  - conversation_id: Identifier for conversation tracking
  - metadata: Optional endpoint-specific metadata
  - context: Optional list of context items (RAG results, etc.)

How to interact:
- Use send_message_to_target(message, conversation_id) to send messages
- Messages should be natural, conversational text
- Maintain conversation_id across turns for conversation continuity
- The platform handles conversation state automatically (both stateless
  and stateful endpoints use the same interface)

The Rhesis backend handles all authentication, request mapping, and
response parsing according to the endpoint's configuration.

Best practices:
- Write messages as a real user would
- Check responses before deciding next actions
- The endpoint may use RAG or other context mechanisms internally
"""
        return doc
