from abc import ABC, abstractmethod
from typing import Any, Dict

from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint

# Import modular components
from .auth import AuthenticationManager
from .common import ErrorResponseBuilder, HeaderManager
from .conversation import ConversationTracker
from .templating import ResponseMapper, TemplateRenderer


class BaseEndpointInvoker(ABC):
    """Base class for endpoint invokers with shared functionality."""

    def __init__(self):
        self.template_renderer = TemplateRenderer()
        self.response_mapper = ResponseMapper()
        self.auth_manager = AuthenticationManager()
        self.error_builder = ErrorResponseBuilder()
        self.header_manager = HeaderManager()
        self.conversation_tracker = ConversationTracker()

    @abstractmethod
    async def invoke(
        self, db: Session, endpoint: Endpoint, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Invoke the endpoint with the given input data.

        Args:
            db: Database session
            endpoint: The endpoint to invoke
            input_data: Input data to be mapped to the endpoint's request template

        Returns:
            Dict containing the mapped response from the endpoint
        """
        pass

    # Conversation tracking methods (delegated to ConversationTracker)
    def _detect_conversation_field(self, endpoint: Endpoint):
        """Detect conversation tracking field from response mappings."""
        return self.conversation_tracker.detect_conversation_field(endpoint)

    def _prepare_conversation_context(
        self, endpoint: Endpoint, input_data: Dict[str, Any], **extra_context
    ):
        """Prepare template context with conversation tracking."""
        return self.conversation_tracker.prepare_conversation_context(
            endpoint, input_data, **extra_context
        )

    def _extract_conversation_id(
        self, rendered_body: Dict[str, Any], input_data: Dict[str, Any], conversation_field
    ):
        """Extract conversation ID from rendered body or input data."""
        return self.conversation_tracker.extract_conversation_id(
            rendered_body, input_data, conversation_field
        )

    # Authentication methods (delegated to AuthenticationManager)
    def _get_valid_token(self, db: Session, endpoint: Endpoint):
        """Get a valid authentication token."""
        return self.auth_manager.get_valid_token(db, endpoint)

    def _get_client_credentials_token(self, db: Session, endpoint: Endpoint):
        """Get a new token using OAuth 2.0 client credentials flow."""
        return self.auth_manager.get_client_credentials_token(db, endpoint)

    # Header management methods (delegated to HeaderManager)
    def _inject_context_headers(self, headers: Dict[str, str], input_data: Dict[str, Any] = None):
        """Inject context headers into headers dict."""
        return self.header_manager.inject_context_headers(headers, input_data)

    def _sanitize_headers(self, headers: Dict[str, Any]):
        """Sanitize headers by redacting sensitive information."""
        return self.header_manager.sanitize_headers(headers)

    # Error handling methods (delegated to ErrorResponseBuilder)
    def _create_error_response(
        self,
        error_type: str,
        output_message: str,
        message: str,
        request_details: Dict = None,
        **kwargs,
    ):
        """Create standardized error response."""
        return self.error_builder.create_error_response(
            error_type, output_message, message, request_details, **kwargs
        )

    def _safe_request_details(self, local_vars: Dict, connection_type: str = "unknown"):
        """Safely create request details from local variables."""
        return self.error_builder.safe_request_details(local_vars, connection_type)
