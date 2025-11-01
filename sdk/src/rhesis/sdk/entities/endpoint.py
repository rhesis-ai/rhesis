from typing import Any, Dict, Optional

from rhesis.sdk.entities import BaseEntity


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
        >>> print(endpoint.name)
        
        List all endpoints:
        >>> for endpoint in Endpoint().all():
        ...     print(endpoint.name, endpoint.url)
    """
    
    endpoint = "endpoints"
    
    def __init__(self, **fields: Any) -> None:
        """
        Initialize an Endpoint instance.
        
        Args:
            **fields: Arbitrary keyword arguments representing endpoint fields.
        """
        super().__init__(**fields)
        
        # Core fields
        self.name: Optional[str] = fields.get("name")
        self.description: Optional[str] = fields.get("description")
        self.protocol: Optional[str] = fields.get("protocol")
        self.url: Optional[str] = fields.get("url")
        self.auth: Optional[Dict[str, Any]] = fields.get("auth")
        self.environment: Optional[str] = fields.get("environment")
        
        # Configuration source
        self.config_source: Optional[str] = fields.get("config_source")
        self.openapi_spec_url: Optional[str] = fields.get("openapi_spec_url")
        self.openapi_spec: Optional[Dict[str, Any]] = fields.get("openapi_spec")
        self.llm_suggestions: Optional[Dict[str, Any]] = fields.get("llm_suggestions")
        
        # Request structure
        self.method: Optional[str] = fields.get("method")
        self.endpoint_path: Optional[str] = fields.get("endpoint_path")
        self.request_headers: Optional[Dict[str, str]] = fields.get("request_headers")
        self.query_params: Optional[Dict[str, Any]] = fields.get("query_params")
        self.request_body_template: Optional[Dict[str, Any]] = fields.get(
            "request_body_template"
        )
        self.input_mappings: Optional[Dict[str, Any]] = fields.get("input_mappings")
        
        # Response handling
        self.response_format: Optional[str] = fields.get("response_format")
        self.response_mappings: Optional[Dict[str, str]] = fields.get("response_mappings")
        self.validation_rules: Optional[Dict[str, Any]] = fields.get("validation_rules")
        
        # Relationships
        self.status_id: Optional[str] = fields.get("status_id")
        self.user_id: Optional[str] = fields.get("user_id")
        self.organization_id: Optional[str] = fields.get("organization_id")
        self.project_id: Optional[str] = fields.get("project_id")
        
        # Authentication (write-only fields are not returned)
        self.auth_type: Optional[str] = fields.get("auth_type")
        self.client_id: Optional[str] = fields.get("client_id")
        self.token_url: Optional[str] = fields.get("token_url")
        self.scopes: Optional[list[str]] = fields.get("scopes")
        self.audience: Optional[str] = fields.get("audience")
        self.extra_payload: Optional[Dict[str, Any]] = fields.get("extra_payload")
    
    def to_penelope_config(self) -> Dict[str, Any]:
        """
        Convert endpoint to Penelope EndpointTarget configuration.
        
        Returns:
            Dictionary suitable for EndpointTarget initialization
            
        Example:
            >>> endpoint = Endpoint(id='endpoint-123')
            >>> endpoint.fetch()
            >>> config = endpoint.to_penelope_config()
            >>> from rhesis.penelope import EndpointTarget
            >>> target = EndpointTarget(endpoint_id=endpoint.id, config=config)
        """
        config = {
            "url": self.url,
            "method": self.method or "POST",
            "headers": self.request_headers or {},
            "request_template": self.request_body_template or {},
        }
        
        # Add response path if available in response_mappings
        if self.response_mappings and "response" in self.response_mappings:
            config["response_path"] = self.response_mappings["response"]
        else:
            config["response_path"] = "response"
        
        return config

