"""
Endpoint target implementation.

EndpointTarget is a thin wrapper around the Rhesis SDK's Endpoint entity.
The interface (what can be sent/received) is defined by the Rhesis platform.

All authentication, request mapping, and response parsing is handled by the
Rhesis backend - Penelope simply uses the SDK to invoke endpoints.
"""

from typing import Any, Optional, cast

from rhesis.penelope.targets.base import Target, TargetResponse
from rhesis.sdk.entities import Endpoint


class EndpointTarget(Target):
    """
    Target implementation for Rhesis endpoints.

    This is a thin wrapper around rhesis.sdk.entities.Endpoint that adapts
    it to Penelope's Target interface. The Rhesis platform defines what can
    be sent (input + optional session_id) and received (structured response).

    All endpoint configuration, authentication, request/response mapping,
    and protocol handling is managed by the Rhesis backend via the SDK.

    Usage:
        >>> # Using an endpoint ID (loads from Rhesis platform)
        >>> target = EndpointTarget(endpoint_id="chatbot-prod")
        >>> response = target.send_message("Hello!")

        >>> # Using an existing Endpoint instance
        >>> endpoint = Endpoint(id="chatbot-prod")
        >>> endpoint.fetch()
        >>> target = EndpointTarget(endpoint=endpoint)
        >>> response = target.send_message("Hello!")
    """

    endpoint: Endpoint  # Type annotation for the instance variable
    endpoint_id: str

    def __init__(
        self,
        endpoint_id: Optional[str] = None,
        endpoint: Optional[Endpoint] = None,
    ):
        """
        Initialize the endpoint target.

        Args:
            endpoint_id: Unique identifier for the endpoint (loaded from Rhesis)
            endpoint: Pre-loaded Endpoint instance (alternative to endpoint_id)

        Note:
            Provide either endpoint_id OR endpoint, not both.
        """
        if endpoint_id is None and endpoint is None:
            raise ValueError("Must provide either endpoint_id or endpoint")

        if endpoint_id is not None and endpoint is not None:
            raise ValueError("Provide only endpoint_id OR endpoint, not both")

        if endpoint is not None:
            self.endpoint = endpoint
            self.endpoint_id = endpoint.id or "unknown"
        else:
            # Load endpoint from SDK
            assert endpoint_id is not None  # Already validated above
            self.endpoint_id = endpoint_id
            loaded_endpoint = Endpoint.from_id(self.endpoint_id)
            if loaded_endpoint is None:
                raise ValueError(f"Endpoint not found: {endpoint_id}")
            # Cast from BaseEntity to Endpoint (from_id returns BaseEntity)
            self.endpoint = cast(Endpoint, loaded_endpoint)

        # Validate on initialization
        is_valid, error = self.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid endpoint configuration: {error}")

    @property
    def target_type(self) -> str:
        return "endpoint"

    @property
    def target_id(self) -> str:
        return self.endpoint_id

    @property
    def description(self) -> str:
        url = self.endpoint.fields.get("url", "")
        name = self.endpoint.fields.get("name", self.endpoint_id)
        return f"Rhesis Endpoint: {name} ({url})"

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """Validate endpoint configuration."""
        if not self.endpoint:
            return False, "Endpoint instance is None"

        if not self.endpoint.id:
            return False, "Endpoint ID is missing"

        return True, None

    def send_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """
        Send a message to the endpoint via the Rhesis SDK.

        Args:
            message: The message to send
            session_id: Optional session ID for multi-turn conversations
            **kwargs: Additional parameters (ignored for endpoints)

        Returns:
            TargetResponse with the endpoint's response
        """
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
            # Use SDK to invoke the endpoint
            response_data = self.endpoint.invoke(
                input=message,
                session_id=session_id,
            )

            if response_data is None:
                return TargetResponse(
                    success=False,
                    content="",
                    error="Endpoint invocation returned None",
                )

            # Extract response content from Rhesis standard response structure
            # Standard fields: output, session_id, metadata, context
            response_text = response_data.get("output", "")

            # Extract session_id
            response_session_id = response_data.get("session_id", session_id)

            # Build metadata including context if available
            response_metadata = {
                "raw_response": response_data,
                "message_sent": message,
            }

            # Include Rhesis metadata fields if present
            if "metadata" in response_data and response_data["metadata"] is not None:
                response_metadata["endpoint_metadata"] = response_data["metadata"]

            if "context" in response_data and response_data["context"]:
                response_metadata["context"] = response_data["context"]

            return TargetResponse(
                success=True,
                content=str(response_text),
                session_id=response_session_id,
                metadata=response_metadata,
            )

        except ValueError as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"Invalid request: {str(e)}",
            )
        except Exception as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"Unexpected error: {str(e)}",
            )

    def get_tool_documentation(self) -> str:
        """Get endpoint-specific documentation."""
        name = self.endpoint.fields.get("name", self.endpoint_id)
        url = self.endpoint.fields.get("url", "N/A")
        description = self.endpoint.fields.get("description", "")
        protocol = self.endpoint.fields.get("protocol", "REST")

        doc = f"""
Target Type: Rhesis Endpoint
Name: {name}
Endpoint ID: {self.endpoint_id}
Protocol: {protocol}
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
  - context: Optional list of context items

The Rhesis backend handles all authentication, request mapping, and
response parsing according to the endpoint's configuration.

How to interact:
- Use send_message_to_target(message, session_id) to send messages
- Messages should be natural, conversational text
- Maintain session_id across turns for conversation continuity
- Session typically expires after 1 hour of inactivity

Best practices:
- Write messages as a real user would
- Check responses before deciding next actions
- Use consistent session_id for related questions
"""
        return doc
