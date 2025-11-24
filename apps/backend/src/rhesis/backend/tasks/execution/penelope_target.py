"""
Backend-specific endpoint target for Penelope.

This module provides a custom Target implementation that allows Penelope to interact
with Rhesis endpoints directly through the backend's endpoint service, without requiring
SDK initialization. This is used for multi-turn test execution where Penelope runs
within the backend worker context.
"""

import asyncio
from typing import Any, Coroutine, Optional, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.dependencies import get_endpoint_service
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.penelope.targets.base import Target, TargetResponse

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
        # Event loop exists - use thread pool
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        # No event loop - run directly
        return asyncio.run(coro)


class BackendEndpointTarget(Target):
    """
    Backend-specific target implementation for Rhesis endpoints.

    Unlike the SDK's EndpointTarget (used in external scripts), this target works
    directly with the backend's database and endpoint service. This enables Penelope
    to test endpoints from within the backend worker context without SDK initialization.

    The interface and behavior match EndpointTarget, but the implementation uses
    backend services instead of SDK HTTP calls.

    Usage:
        >>> # In a Celery task or backend context
        >>> with get_db() as db:
        >>>     target = BackendEndpointTarget(
        >>>         db=db,
        >>>         endpoint_id="uuid-here",
        >>>         organization_id="org-uuid"
        >>>     )
        >>>     response = target.send_message("Hello!")
    """

    def __init__(
        self,
        db: Session,
        endpoint_id: str,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """
        Initialize the backend endpoint target.

        Args:
            db: Database session for accessing endpoint data
            endpoint_id: UUID string of the endpoint to target
            organization_id: Optional organization ID for security filtering
            user_id: Optional user ID for context injection

        Raises:
            ValueError: If endpoint is not found or configuration is invalid
        """
        self.db = db
        self.endpoint_id = endpoint_id
        self.organization_id = organization_id
        self.user_id = user_id
        self.endpoint_service = get_endpoint_service()

        # Load and cache endpoint metadata
        self._endpoint_name = None
        self._endpoint_url = None
        self._endpoint_description = None
        self._endpoint_connection_type = None

        # Validate configuration on initialization
        is_valid, error = self.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid endpoint configuration: {error}")

        # Load endpoint metadata for descriptions
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
        if not self.db:
            return False, "Database session is None"

        if not self.endpoint_id:
            return False, "Endpoint ID is missing"

        # Try to retrieve the endpoint to ensure it exists and is accessible
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

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """
        Send a message to the endpoint via the backend endpoint service.

        Uses Penelope's intelligent conversation ID extraction to support multiple
        conversation tracking field names (conversation_id, session_id, thread_id, etc.).

        Args:
            message: The message to send
            conversation_id: Optional conversation ID for multi-turn conversations
            **kwargs: Additional parameters, including other conversation tracking fields
                     (session_id, thread_id, chat_id, etc.)

        Returns:
            TargetResponse with the endpoint's response and extracted conversation_id
        """
        # Validate input
        if not message or not message.strip():
            return TargetResponse(
                success=False,
                content="",
                error="Message cannot be empty",
            )

        if len(message) > 10000:
            return TargetResponse(
                success=False,
                content="",
                error="Message too long (max 10000 characters)",
            )

        try:
            # TargetInteractionTool extracts conversation_id and passes it as second parameter
            # kwargs should not contain conversation fields (filtered by TargetInteractionTool)
            # So we can use conversation_id directly
            final_conversation_id = conversation_id

            # Prepare input data in the format expected by the endpoint service
            input_data = {"input": message}
            if final_conversation_id:
                input_data["session_id"] = final_conversation_id

            logger.debug(
                f"BackendEndpointTarget input conversation tracking - "
                f"conversation_id: {conversation_id}, "
                f"kwargs: {list(kwargs.keys())}, "
                f"final_conversation_id: {final_conversation_id}"
            )

            # Invoke endpoint through the backend service
            logger.info(
                f"BackendEndpointTarget invoking endpoint {self.endpoint_id} "
                f"with message: '{message[:100]}...', conversation_id: {final_conversation_id}"
            )

            response_data = run_async(
                self.endpoint_service.invoke_endpoint(
                    db=self.db,
                    endpoint_id=self.endpoint_id,
                    input_data=input_data,
                    organization_id=self.organization_id,
                    user_id=self.user_id,
                )
            )

            if response_data is None:
                return TargetResponse(
                    success=False,
                    content="",
                    error="Endpoint invocation returned None",
                )

            # Handle ErrorResponse objects (Pydantic models) from invokers
            from rhesis.backend.app.services.invokers.common.schemas import ErrorResponse

            if isinstance(response_data, ErrorResponse):
                # Convert Pydantic ErrorResponse to dict
                response_dict = response_data.to_dict()
                return TargetResponse(
                    success=False,
                    content="",
                    error=response_dict.get("output", "Endpoint invocation failed"),
                    metadata={"error_details": response_dict},
                )

            # Extract response content from Rhesis standard response structure
            # Standard fields: output, session_id, metadata, context
            response_text = response_data.get("output", "")

            # Extract conversation_id using smart field detection (match Penelope EndpointTarget)
            from rhesis.penelope.conversation import extract_conversation_id

            # Extract session_id from endpoint response (endpoint manages session lifecycle)
            response_conversation_id = extract_conversation_id(response_data)
            if not response_conversation_id:
                # Fallback to input conversation_id for subsequent turns
                response_conversation_id = final_conversation_id

            # Debug logging for conversation ID tracking (match Penelope EndpointTarget format)
            logger.debug(
                f"BackendEndpoint conversation tracking - Input: {final_conversation_id}, "
                f"Response extracted: {extract_conversation_id(response_data)}, "
                f"Final: {response_conversation_id}"
            )

            # Build metadata including context if available (match Penelope EndpointTarget format)
            response_metadata = {
                "raw_response": response_data,
                "message_sent": message,
                "input_conversation_id": final_conversation_id,
                "extracted_conversation_id": response_conversation_id,
            }

            # Include Rhesis metadata fields if present
            if "metadata" in response_data and response_data["metadata"] is not None:
                response_metadata["endpoint_metadata"] = response_data["metadata"]

            if "context" in response_data and response_data["context"]:
                response_metadata["context"] = response_data["context"]

            logger.info(
                f"BackendEndpointTarget received response from {self.endpoint_id}: "
                f"'{str(response_text)[:100]}...', conversation_id: {response_conversation_id}"
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
  - session_id: Optional, for multi-turn conversations

Output:
  - output: The response text from the endpoint
  - session_id: Session identifier for conversation tracking
  - metadata: Optional endpoint-specific metadata
  - context: Optional list of context items (RAG results, etc.)

The Rhesis backend handles all authentication, request mapping, and
response parsing according to the endpoint's configuration.

How to interact:
- Use send_message_to_target(message, conversation_id) to send messages
- Messages should be natural, conversational text
- Maintain conversation_id across turns for conversation continuity
- Supports flexible conversation tracking (conversation_id, session_id, thread_id, etc.)
- Conversation typically expires after 1 hour of inactivity

Best practices:
- Write messages as a real user would
- Check responses before deciding next actions
- Use consistent conversation_id for related questions
- The endpoint may use RAG or other context mechanisms internally
- BackendEndpointTarget intelligently extracts conversation IDs from any supported field
"""
        return doc
