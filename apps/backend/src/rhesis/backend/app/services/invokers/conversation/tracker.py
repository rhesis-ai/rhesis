"""Conversation tracking for multi-turn conversations."""

import json
import re
from typing import Any, Dict, Optional

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.logging import logger

# Conversation tracking field names (priority-ordered)
# Used for convention-based detection of conversation tracking fields in response_mapping
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

# Pattern to detect {{ messages }} (with or without spaces) in request_mapping
_MESSAGES_TEMPLATE_PATTERN = re.compile(r"\{\{\s*messages\s*\}\}")


class ConversationTracker:
    """Handles conversation tracking for multi-turn conversations."""

    @staticmethod
    def detect_stateless_mode(endpoint: Endpoint) -> bool:
        """
        Detect whether an endpoint operates in stateless mode.

        Stateless endpoints expect the full conversation history as a
        ``messages`` array in every request, rather than maintaining
        server-side session state. Detection is convention-based: if the
        ``request_mapping`` references ``{{ messages }}``, the endpoint
        is treated as stateless.

        Args:
            endpoint: The endpoint configuration.

        Returns:
            True if the endpoint is stateless, False otherwise.
        """
        request_mapping = endpoint.request_mapping
        if not request_mapping:
            return False

        # Serialize to string for pattern matching
        if isinstance(request_mapping, dict):
            mapping_str = json.dumps(request_mapping)
        else:
            mapping_str = str(request_mapping)

        is_stateless = bool(_MESSAGES_TEMPLATE_PATTERN.search(mapping_str))
        if is_stateless:
            logger.info(
                "Detected stateless endpoint mode ({{ messages }} found in request_mapping)"
            )
        return is_stateless

    @staticmethod
    def extract_system_prompt(endpoint: Endpoint) -> Optional[str]:
        """
        Extract the system prompt from an endpoint's request_mapping.

        The ``system_prompt`` key is a reserved meta key in
        ``request_mapping``. When present, its value is used to prepend a
        system message to the conversation's ``messages`` array. The key
        itself is stripped from the wire body by
        ``BaseEndpointInvoker._strip_meta_keys()``.

        Args:
            endpoint: The endpoint configuration.

        Returns:
            The system prompt string, or None if not configured or empty.
        """
        request_mapping = endpoint.request_mapping
        if not request_mapping or not isinstance(request_mapping, dict):
            return None

        system_prompt = request_mapping.get("system_prompt")
        if not system_prompt or not isinstance(system_prompt, str):
            return None

        # Treat empty/whitespace-only as absent
        stripped = system_prompt.strip()
        if not stripped:
            return None

        logger.debug("Extracted system_prompt from request_mapping")
        return stripped

    @staticmethod
    def detect_conversation_field(endpoint: Endpoint) -> Optional[str]:
        """
        Detect which conversation tracking field is configured in response_mapping.
        Uses convention-based detection by checking common field names.

        This enables automatic conversation tracking when a field like 'conversation_id',
        'session_id', 'thread_id', etc. is mapped in response_mapping.

        For stateless endpoints (detected via ``{{ messages }}`` in
        request_mapping), returns None because conversation state is
        managed internally rather than by the endpoint.

        Args:
            endpoint: The endpoint configuration

        Returns:
            The field name to use for conversation tracking, or None if not configured.
        """
        # Stateless endpoints don't use wire-level conversation tracking
        if ConversationTracker.detect_stateless_mode(endpoint):
            logger.debug("Stateless endpoint detected - skipping conversation field detection")
            return None

        response_mapping = endpoint.response_mapping or {}

        # Check common field names (auto-detection)
        for field_name in CONVERSATION_FIELD_NAMES:
            if field_name in response_mapping:
                logger.info(f"Auto-detected conversation tracking field: {field_name}")
                return field_name

        logger.debug("No conversation tracking field detected in response_mapping")
        return None

    @staticmethod
    def prepare_conversation_context(
        endpoint: Endpoint, input_data: Dict[str, Any], **extra_context
    ) -> tuple:
        """
        Prepare template context with conversation tracking field.

        Only includes conversation fields that have actual values to prevent
        None -> "None" conversion in templates. Missing conversation fields
        should be omitted from the first request and extracted from the response.

        Args:
            endpoint: The endpoint configuration
            input_data: Input data from the user
            **extra_context: Additional context to merge (e.g., auth_token)

        Returns:
            Tuple of (template_context, conversation_field)
        """
        conversation_field = ConversationTracker.detect_conversation_field(endpoint)

        # Use input_data as-is - system field filtering is now handled by specific invokers
        # that need it (e.g., SDK invoker filters out organization_id/user_id for function calls)
        template_context = {**input_data, **extra_context}

        if conversation_field:
            if conversation_field in input_data and input_data[conversation_field] is not None:
                # Use the provided non-None value
                logger.debug(
                    f"Using {conversation_field}={input_data[conversation_field]} from input"
                )
            else:
                # Don't add None values - let the template handle missing fields gracefully
                # The conversation ID will be extracted from the endpoint response
                logger.debug(
                    f"No {conversation_field} provided - will be extracted from endpoint response"
                )

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
