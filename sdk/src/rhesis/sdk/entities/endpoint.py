from typing import Any, Dict, Optional

import requests

from rhesis.sdk.entities.base_entity import BaseEntity, handle_http_errors


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
    
    endpoint = "endpoints"
    
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
        
        # Construct input_data dictionary
        input_data: Dict[str, Any] = {"input": input}
        if session_id is not None:
            input_data["session_id"] = session_id
        
        url = f"{self.client.get_url(self.endpoint)}/{self.id}/invoke"
        response = requests.post(
            url,
            json=input_data,
            headers=self.headers,
        )
        response.raise_for_status()
        return dict(response.json())

