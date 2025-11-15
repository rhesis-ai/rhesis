"""Conversation tracking for multi-turn conversations."""

from typing import Any, Dict, Optional

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.logging import logger

# Conversation tracking field names (priority-ordered)
# Used for convention-based detection of conversation tracking fields in response_mappings
# Tier 1: Most common (90% of APIs)
CONVERSATION_FIELD_NAMES = [
    "conversation_id",
    "session_id",
    "thread_id",
    "chat_id",
    # Tier 2: Common variants (8% of APIs)
    "dialog_id",
    "dialogue_id",
    "context_id",
    "interaction_id",
]


class ConversationTracker:
    """Handles conversation tracking for multi-turn conversations."""

    @staticmethod
    def detect_conversation_field(endpoint: Endpoint) -> Optional[str]:
        """
        Detect which conversation tracking field is configured in response_mappings.
        Uses convention-based detection by checking common field names.

        This enables automatic conversation tracking when a field like 'conversation_id',
        'session_id', 'thread_id', etc. is mapped in response_mappings.

        Args:
            endpoint: The endpoint configuration

        Returns:
            The field name to use for conversation tracking, or None if not configured.
        """
        response_mappings = endpoint.response_mappings or {}

        # Check common field names (auto-detection)
        for field_name in CONVERSATION_FIELD_NAMES:
            if field_name in response_mappings:
                logger.info(f"Auto-detected conversation tracking field: {field_name}")
                return field_name

        logger.debug("No conversation tracking field detected in response_mappings")
        return None

    @staticmethod
    def prepare_conversation_context(
        endpoint: Endpoint, input_data: Dict[str, Any], **extra_context
    ) -> tuple:
        """
        Prepare template context with conversation tracking field.

        Ensures the conversation field is present in the template context (even if None)
        to avoid Jinja2 Undefined errors when rendering templates.

        Args:
            endpoint: The endpoint configuration
            input_data: Input data from the user
            **extra_context: Additional context to merge (e.g., auth_token)

        Returns:
            Tuple of (template_context, conversation_field)
        """
        conversation_field = ConversationTracker.detect_conversation_field(endpoint)
        template_context = {**input_data, **extra_context}

        if conversation_field and conversation_field not in template_context:
            template_context[conversation_field] = None
            logger.debug(f"Added {conversation_field}=None to template context for first turn")

        return template_context, conversation_field

    @staticmethod
    def extract_conversation_id(
        rendered_body: Dict[str, Any],
        input_data: Dict[str, Any],
        conversation_field: Optional[str],
    ) -> Optional[str]:
        """
        Extract conversation ID from rendered body or input data.

        Checks three sources in order:
        1. Rendered request body (from template)
        2. Input data (explicitly provided)
        3. None (will be extracted from response)

        Args:
            rendered_body: The rendered request body
            input_data: Original input data
            conversation_field: Name of the conversation tracking field

        Returns:
            The conversation ID or None
        """
        if not conversation_field:
            return None

        if conversation_field in rendered_body:
            conv_id = rendered_body[conversation_field]
            logger.info(f"Using {conversation_field} from rendered template: {conv_id}")
            return conv_id
        elif conversation_field in input_data:
            conv_id = input_data[conversation_field]
            rendered_body[conversation_field] = conv_id
            logger.info(f"Using {conversation_field} from input_data: {conv_id}")
            return conv_id
        else:
            logger.debug(
                f"No {conversation_field} provided in input - "
                f"will be extracted from response if available"
            )
            return None
