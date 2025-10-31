"""
Endpoint target implementation.

EndpointTarget represents Rhesis endpoints accessible via the SDK.
"""

from typing import Any, Dict, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from rhesis.penelope.targets.base import Target, TargetResponse


class EndpointTarget(Target):
    """
    Target implementation for Rhesis endpoints.
    
    This target type enables Penelope to test HTTP/REST/WebSocket endpoints
    configured in the Rhesis platform.
    
    Configuration should include:
    - url: The endpoint URL
    - method: HTTP method (default: POST)
    - headers: Request headers (including auth)
    - request_template: Template for request body
    - response_path: JSON path to extract response text
    
    Usage:
        >>> target = EndpointTarget(
        ...     endpoint_id="chatbot-prod",
        ...     config={
        ...         "url": "https://api.example.com/chat",
        ...         "method": "POST",
        ...         "headers": {"Authorization": "Bearer token"},
        ...         "request_template": {"message": ""},
        ...         "response_path": "response",
        ...     }
        ... )
        >>> response = target.send_message("Hello!")
    """
    
    def __init__(self, endpoint_id: str, config: Dict[str, Any]):
        """
        Initialize the endpoint target.
        
        Args:
            endpoint_id: Unique identifier for the endpoint
            config: Endpoint configuration dictionary
        """
        self.endpoint_id = endpoint_id
        self.config = config
        
        # Extract configuration
        self.url: str = config.get("url", "")
        self.method: str = config.get("method", "POST")
        self.headers: Dict[str, str] = config.get("headers", {})
        self.request_template: Dict[str, Any] = config.get("request_template", {})
        self.response_path: str = config.get("response_path", "response")
        
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
        return f"Rhesis Endpoint: {self.endpoint_id} ({self.url})"
    
    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """Validate endpoint configuration."""
        if not self.url:
            return False, "Missing required 'url' in configuration"
        
        if not self.method:
            return False, "Missing required 'method' in configuration"
        
        if self.method.upper() not in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            return False, f"Invalid HTTP method: {self.method}"
        
        return True, None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _make_http_request(
        self,
        message: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to the endpoint with retry logic.
        
        Args:
            message: The message to send
            session_id: Optional session ID
            
        Returns:
            Response JSON
        """
        # Build request body from template
        request_body = self.request_template.copy()
        
        # Replace message placeholder
        if "message" in request_body:
            request_body["message"] = message
        elif "input" in request_body:
            request_body["input"] = message
        elif "prompt" in request_body:
            request_body["prompt"] = message
        elif "query" in request_body:
            request_body["query"] = message
        else:
            # Default to message field
            request_body["message"] = message
        
        # Add session_id if provided
        if session_id:
            request_body["session_id"] = session_id
        
        # Make request
        response = requests.request(
            method=self.method,
            url=self.url,
            headers=self.headers,
            json=request_body,
            timeout=30,
        )
        
        response.raise_for_status()
        return response.json()
    
    def send_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        **kwargs
    ) -> TargetResponse:
        """
        Send a message to the endpoint.
        
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
            # Make request (with automatic retry)
            response_data = self._make_http_request(message, session_id)
            
            # Extract response content
            response_text = response_data.get(self.response_path, "")
            if not response_text and "message" in response_data:
                response_text = response_data["message"]
            if not response_text and "response" in response_data:
                response_text = response_data["response"]
            
            # Extract session_id
            response_session_id = response_data.get("session_id", session_id)
            
            return TargetResponse(
                success=True,
                content=str(response_text),
                session_id=response_session_id,
                metadata={
                    "raw_response": response_data,
                    "message_sent": message,
                },
            )
            
        except requests.exceptions.HTTPError as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"HTTP error: {e.response.status_code} - {e.response.text}",
            )
        except requests.exceptions.RequestException as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"Request failed: {str(e)}",
            )
        except Exception as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"Unexpected error: {str(e)}",
            )
    
    def get_tool_documentation(self) -> str:
        """Get endpoint-specific documentation."""
        return f"""
Target Type: Rhesis Endpoint
Endpoint ID: {self.endpoint_id}
URL: {self.url}
Method: {self.method}

This is a Rhesis endpoint accessible via HTTP {self.method} requests.

How to interact:
- Use send_message_to_target(message, session_id) to send messages
- The endpoint expects conversational messages
- Maintain session_id across turns for conversation continuity
- Session typically expires after 1 hour of inactivity

Best practices:
- Write messages as a real user would
- Check responses before deciding next actions
- Use consistent session_id for related questions
"""

