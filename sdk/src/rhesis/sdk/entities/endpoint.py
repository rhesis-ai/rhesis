from enum import Enum
from typing import Any, ClassVar, Dict, Optional

from rhesis.sdk.client import Client, Endpoints, Methods
from rhesis.sdk.entities.base_entity import BaseEntity, handle_http_errors

ENDPOINT = Endpoints.ENDPOINTS


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
    """

    endpoint: ClassVar[Endpoints] = ENDPOINT
    name: Optional[str] = None
    description: Optional[str] = None
    # Required field - must be one of: "REST", "WebSocket", "GRPC", "SDK"
    connection_type: Optional[ConnectionType] = None
    url: Optional[str] = None
    project_id: Optional[str] = None
    id: Optional[str] = None

    @handle_http_errors
    def invoke(self, input: str, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Invoke the endpoint with the given input.

        This method sends a request to the Rhesis backend, which handles
        authentication, request mapping, and response parsing according to
        the endpoint's configuration.

        Args:
            input: The message or query to send to the endpoint
            session_id: Optional session ID for multi-turn conversations

        Returns:
            Dict containing the response from the endpoint, or None if error occurred.

            Response structure (standard Rhesis format):
            {
                "output": "Response text from the endpoint",
                "session_id": "Session identifier for tracking",
                "metadata": {...},  # Optional endpoint metadata
                "context": [...]    # Optional context items
            }

        Raises:
            ValueError: If endpoint ID is not set
            requests.exceptions.HTTPError: If the API request fails

        Example:
            >>> endpoint = Endpoint(id='endpoint-123')
            >>> endpoint.fetch()
            >>> response = endpoint.invoke(
            ...     input="What is the weather?",
            ...     session_id="session-abc"
            ... )
            >>> print(response)
            {
                "output": "The weather is sunny today!",
                "session_id": "session-abc",
                "metadata": None,
                "context": []
            }
        """
        if not self.id:
            raise ValueError("Endpoint ID must be set before invoking")

        input_data: Dict[str, Any] = {"input": input}
        if session_id is not None:
            input_data["session_id"] = session_id

        client = Client()
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
