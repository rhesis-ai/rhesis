from enum import Enum
from typing import Any, ClassVar, Dict, Optional

from rhesis.sdk.clients import APIClient, Methods
from rhesis.sdk.clients import Endpoints as ApiEndpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity, handle_http_errors

ENDPOINT = ApiEndpoints.ENDPOINTS


class ConnectionType(str, Enum):
    """Connection type enum matching backend EndpointConnectionType."""

    REST = "REST"
    WEBSOCKET = "WebSocket"
    GRPC = "GRPC"
    SDK = "SDK"


class Endpoint(BaseEntity):
    """
    Endpoint entity for interacting with the Rhesis API.

    Endpoints represent AI services or APIs that tests execute against.
    They define how Rhesis connects to your application, sends test inputs,
    and receives responses for evaluation.

    Examples:
        Load an endpoint:
        >>> endpoint = Endpoint(id='endpoint-123')
        >>> endpoint.fetch()
        >>> print(endpoint.fields.get('name'))

        Invoke an endpoint:
        >>> response = endpoint.invoke(input="What is the weather?")
        >>> print(response)

        List all endpoints:
        >>> for endpoint in Endpoint().all():
        ...     print(endpoint.fields.get('name'))

        Create an endpoint programmatically:
        >>> endpoint = Endpoint(
        ...     name="My API",
        ...     connection_type=ConnectionType.REST,
        ...     project_id="your-project-uuid",
        ...     url="https://api.example.com",
        ...     auth_token="your-api-key",  # Token for the target API
        ...     request_mapping={"message": "{{ input }}"},
        ...     request_headers={"Content-Type": "application/json"},
        ...     response_mapping={"output": "response.text"},
        ... )
        >>> endpoint.push()
    """

    endpoint: ClassVar[ApiEndpoints] = ENDPOINT
    _push_required_fields: ClassVar[tuple[str, ...]] = ("name", "connection_type", "project_id")
    _write_only_fields: ClassVar[tuple[str, ...]] = ("auth_token",)

    name: Optional[str] = None
    description: Optional[str] = None
    # Required field - must be one of: "REST", "WebSocket", "GRPC", "SDK"
    connection_type: Optional[ConnectionType] = None
    url: Optional[str] = None
    project_id: Optional[str] = None
    id: Optional[str] = None

    # Request Structure - for programmatic endpoint configuration
    method: Optional[str] = None
    endpoint_path: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Any]] = None
    request_mapping: Optional[Dict[str, Any]] = None

    # Response Handling
    response_mapping: Optional[Dict[str, str]] = None

    # Authentication - for the target API (not Rhesis API)
    auth_token: Optional[str] = None

    @handle_http_errors
    def invoke(
        self,
        input: str,
        conversation_id: Optional[str] = None,
        # Deprecated alias kept for backward compatibility
        session_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Invoke the endpoint with the given input.

        This method sends a request to the Rhesis backend, which handles
        authentication, request mapping, and response parsing according to
        the endpoint's configuration.

        Args:
            input: The message or query to send to the endpoint
            conversation_id: Optional conversation ID for multi-turn
                conversations.  Pass the ``conversation_id`` from the
                previous response to continue the same conversation.
            session_id: Deprecated alias for *conversation_id*.

        Returns:
            Dict containing the response from the endpoint, or ``None``
            if an error occurred.

            Response structure (standard Rhesis format)::

                {
                    "output": "Response text from the endpoint",
                    "conversation_id": "Identifier for tracking",
                    "metadata": {...},
                    "context": [...]
                }

        Raises:
            ValueError: If endpoint ID is not set
            requests.exceptions.HTTPError: If the API request fails

        Example:
            >>> endpoint = Endpoint(id='endpoint-123')
            >>> endpoint.fetch()
            >>> response = endpoint.invoke(
            ...     input="What is the weather?",
            ...     conversation_id="conv-abc"
            ... )
            >>> print(response)
            {
                "output": "The weather is sunny today!",
                "conversation_id": "conv-abc",
                "metadata": None,
                "context": []
            }
        """
        if not self.id:
            raise ValueError("Endpoint ID must be set before invoking")

        # Resolve conversation_id: explicit param wins over deprecated alias
        resolved_cid = conversation_id or session_id

        input_data: Dict[str, Any] = {"input": input}
        if resolved_cid is not None:
            input_data["conversation_id"] = resolved_cid

        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            data=input_data,
            url_params=f"{self.id}/invoke",
        )

    def test(self) -> None:
        result = self.invoke(input="This is a test, answer shortly")
        if result is None:
            raise ValueError("Endpoint is not answering")
        print("Endpoint is working correctly")

    @property
    def auto_configure_result(self) -> Optional[Dict[str, Any]]:
        """Access the raw auto-configure result (confidence, reasoning, warnings).

        Returns:
            Dict with auto-configure metadata, or None if not created via auto_configure().
        """
        return getattr(self, "_auto_configure_result", None)

    @classmethod
    @handle_http_errors
    def auto_configure(
        cls,
        input_text: str,
        url: str,
        auth_token: Optional[str] = None,
        method: str = "POST",
        probe: bool = True,
        name: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Optional["Endpoint"]:
        """
        Auto-configure an endpoint using AI-powered mapping generation.

        Paste any reference material about your endpoint -- a curl command,
        Python code, API docs, or a plain-text description -- and Rhesis
        will use AI to generate the request and response mappings.

        Args:
            input_text: Any reference material about the endpoint (curl,
                code, docs, description).
            url: The endpoint URL.
            auth_token: Authentication token for the target API.
            method: HTTP method (default: "POST").
            probe: If True, Rhesis sends a test request to verify
                the configuration (default: True).
            name: Optional endpoint name.
            project_id: Optional project ID to assign the endpoint to.

        Returns:
            An Endpoint instance pre-filled with the generated mappings
            and configuration. Call ``push()`` to save it. Returns None
            if the request fails.

        Raises:
            requests.exceptions.HTTPError: If the API request fails.

        Example:
            >>> endpoint = Endpoint.auto_configure(
            ...     input_text='''
            ...     curl -X POST https://api.example.com/chat \\
            ...       -H "Authorization: Bearer token123" \\
            ...       -d '{"query": "hello", "model": "gpt-4"}'
            ...     ''',
            ...     url="https://api.example.com/chat",
            ...     auth_token="token123",
            ... )
            >>> print(endpoint.request_mapping)
            >>> endpoint.name = "My Chat API"
            >>> endpoint.project_id = "project-uuid"
            >>> endpoint.push()
        """
        client = APIClient()
        result = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.POST,
            data={
                "input_text": input_text,
                "url": url,
                "auth_token": auth_token,
                "method": method,
                "probe": probe,
            },
            url_params="auto-configure",
        )

        if result is None or result.get("status") == "failed":
            return None

        # Build a pre-filled Endpoint instance
        endpoint = cls(
            name=name,
            url=result.get("url", url),
            method=result.get("method", method),
            connection_type=ConnectionType.REST,
            auth_token=auth_token,
            project_id=project_id,
            request_mapping=result.get("request_mapping"),
            response_mapping=result.get("response_mapping"),
            request_headers=result.get("request_headers"),
        )

        # Store the full result as metadata for transparency
        endpoint._auto_configure_result = result

        return endpoint


class Endpoints(BaseCollection):
    endpoint = ENDPOINT
    entity_class = Endpoint
