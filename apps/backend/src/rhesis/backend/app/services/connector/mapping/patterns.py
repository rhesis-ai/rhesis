"""Sophisticated pattern matching for SDK function parameter detection."""

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class FieldConfig:
    """Configuration for a standard field."""

    name: str  # Field name (e.g., "input", "session_id")
    pattern_type: str  # Pattern lookup key (e.g., "input", "session")
    template_var: str  # Jinja2 variable name (e.g., "{{ input }}")
    confidence_weight: float  # Weight for confidence calculation
    field_location: str  # "request" or "response"
    is_required: bool = False  # Whether this field is required for high confidence


class MappingPatterns:
    """
    Comprehensive pattern definitions for mapping standard Rhesis fields.

    Each pattern category includes:
    - Exact matches (highest priority)
    - Compound patterns (word + suffix like _id, _identifier)
    - Partial matches (word contained within parameter name)
    - Common abbreviations and variations
    """

    # ==================== STANDARD FIELDS CONFIGURATION ====================
    # Add new fields here to automatically include them in auto-mapping
    # REQUEST fields: input parameters to the function
    # RESPONSE fields: output fields from the function
    STANDARD_FIELDS = [
        # REQUEST FIELDS (function inputs)
        FieldConfig(
            name="input",
            pattern_type="input",
            template_var="{{ input }}",
            confidence_weight=0.5,
            field_location="request",
            is_required=True,
        ),
        FieldConfig(
            name="conversation_id",
            pattern_type="session",
            template_var="{{ conversation_id }}",
            confidence_weight=0.2,
            field_location="request",
            is_required=False,
        ),
        # RESPONSE FIELDS (function outputs)
        FieldConfig(
            name="context",
            pattern_type="context",
            template_var="{{ context }}",
            confidence_weight=0.1,
            field_location="response",
            is_required=False,
        ),
        FieldConfig(
            name="metadata",
            pattern_type="metadata",
            template_var="{{ metadata }}",
            confidence_weight=0.1,
            field_location="response",
            is_required=False,
        ),
        FieldConfig(
            name="tool_calls",
            pattern_type="tool_calls",
            template_var="{{ tool_calls }}",
            confidence_weight=0.1,
            field_location="response",
            is_required=False,
        ),
    ]

    # ==================== INPUT PATTERNS ====================
    # Main user query/message/prompt
    INPUT_EXACT = ["input", "query", "prompt", "message", "text"]
    INPUT_COMPOUND = [
        "user_input",
        "user_query",
        "user_message",
        "user_prompt",
        "user_text",
        "input_text",
        "input_message",
        "query_text",
        "prompt_text",
        "chat_input",
        "chat_message",
        "chat_query",
    ]
    INPUT_PARTIAL = ["question", "ask", "request", "instruction"]

    # ==================== SESSION PATTERNS ====================
    # Conversation/session identifiers (often with _id suffix)
    SESSION_EXACT = [
        "session_id",
        "session",
        "conversation_id",
        "conversation",
        "thread_id",
        "thread",
        "chat_id",
        "chat",
    ]
    SESSION_COMPOUND = [
        "conv_id",
        "convo_id",
        "session_key",
        "session_identifier",
        "conversation_key",
        "conversation_identifier",
        "thread_key",
        "thread_identifier",
        "chat_session",
        "chat_session_id",
        "user_session",
        "user_session_id",
        "session_token",
    ]
    SESSION_PARTIAL = ["conv", "convo", "sess"]

    # ==================== CONTEXT PATTERNS ====================
    # Additional context like documents, RAG results
    CONTEXT_EXACT = ["context", "documents", "sources", "knowledge"]
    CONTEXT_COMPOUND = [
        "rag_context",
        "rag_documents",
        "rag_sources",
        "rag_chunks",
        "doc_context",
        "document_context",
        "context_docs",
        "context_documents",
        "retrieved_documents",
        "retrieved_context",
        "search_results",
        "search_context",
        "context_data",
        "additional_context",
    ]
    CONTEXT_PARTIAL = ["docs", "chunks", "passages", "retrieval", "rag"]

    # ==================== METADATA PATTERNS ====================
    # Extra metadata, user info, preferences
    METADATA_EXACT = ["metadata", "meta", "info", "data"]
    METADATA_COMPOUND = [
        "user_metadata",
        "user_info",
        "user_data",
        "user_preferences",
        "extra_data",
        "extra_info",
        "additional_data",
        "additional_info",
        "context_metadata",
        "request_metadata",
        "meta_data",
    ]
    METADATA_PARTIAL = ["extras", "props", "properties", "attributes", "params"]

    # ==================== TOOL CALLS PATTERNS ====================
    # Tool/function call information
    TOOL_CALLS_EXACT = ["tool_calls", "tools", "function_calls", "functions"]
    TOOL_CALLS_COMPOUND = [
        "tool_results",
        "tool_outputs",
        "function_results",
        "available_tools",
        "enabled_tools",
        "active_tools",
        "tools_list",
        "functions_list",
    ]
    TOOL_CALLS_PARTIAL = ["tool", "func", "action", "capability"]

    # ==================== OUTPUT PATTERNS ====================
    # Response/result fields (often nested)
    OUTPUT_EXACT = ["output", "response", "result", "answer", "reply", "message"]
    OUTPUT_COMPOUND = [
        "text_output",
        "text_response",
        "response_text",
        "result_text",
        "answer_text",
        "reply_text",
        "message_text",
        "response_message",
        "output_message",
        "generated_text",
        "completion",
        "model_output",
        "llm_response",
        "ai_response",
        "bot_response",
    ]
    OUTPUT_PARTIAL = ["content", "generated", "completion", "text"]

    @classmethod
    def get_field_config(cls, field_name: str) -> FieldConfig | None:
        """
        Get field configuration by name.

        Args:
            field_name: Name of the field (e.g., "input", "session_id")

        Returns:
            FieldConfig or None if not found
        """
        for config in cls.STANDARD_FIELDS:
            if config.name == field_name:
                return config
        return None

    @classmethod
    def get_all_patterns(cls, field_type: str) -> Tuple[List[str], List[str], List[str]]:
        """
        Get all patterns for a field type.

        Args:
            field_type: One of "input", "session", "context", "metadata", "tool_calls", "output"

        Returns:
            Tuple of (exact_patterns, compound_patterns, partial_patterns)
        """
        field_map = {
            "input": (cls.INPUT_EXACT, cls.INPUT_COMPOUND, cls.INPUT_PARTIAL),
            "session": (cls.SESSION_EXACT, cls.SESSION_COMPOUND, cls.SESSION_PARTIAL),
            "context": (cls.CONTEXT_EXACT, cls.CONTEXT_COMPOUND, cls.CONTEXT_PARTIAL),
            "metadata": (cls.METADATA_EXACT, cls.METADATA_COMPOUND, cls.METADATA_PARTIAL),
            "tool_calls": (cls.TOOL_CALLS_EXACT, cls.TOOL_CALLS_COMPOUND, cls.TOOL_CALLS_PARTIAL),
            "output": (cls.OUTPUT_EXACT, cls.OUTPUT_COMPOUND, cls.OUTPUT_PARTIAL),
        }
        return field_map.get(field_type, ([], [], []))

    @classmethod
    def match_parameter(cls, param_name: str, field_type: str) -> Tuple[bool, float]:
        """
        Check if parameter name matches a field type with confidence scoring.

        Args:
            param_name: Parameter name to check
            field_type: Field type to match against

        Returns:
            Tuple of (matches: bool, confidence: float 0.0-1.0)
        """
        param_lower = param_name.lower()
        exact, compound, partial = cls.get_all_patterns(field_type)

        # Exact match (highest confidence)
        if param_lower in exact:
            return True, 1.0

        # Compound match (high confidence)
        if param_lower in compound:
            return True, 0.9

        # Partial match (medium confidence)
        for pattern in partial:
            if pattern in param_lower:
                return True, 0.7

        return False, 0.0

    @classmethod
    def detect_nested_output_field(cls, return_structure: dict, path: str = "$") -> Dict[str, str]:
        """
        Detect nested output fields in return structure recursively.

        Args:
            return_structure: Dict representing function return structure
                Example: {"response": {"text": str, "id": str}, "metadata": dict}
            path: Current JSONPath being explored (for recursion)

        Returns:
            Dict mapping standard fields to JSONPath expressions
            Example: {"output": "$.response.text", "conversation_id": "$.response.id"}
        """
        mappings = {}

        if not isinstance(return_structure, dict):
            return mappings

        for key, value in return_structure.items():
            current_path = f"{path}.{key}"

            # Check if this key matches output patterns
            if cls.match_parameter(key, "output")[0]:
                if "output" not in mappings:  # Use first match
                    mappings["output"] = current_path

            # Check if this key matches session/conversation patterns
            if cls.match_parameter(key, "session")[0]:
                if "conversation_id" not in mappings:  # Use first match
                    mappings["conversation_id"] = current_path

            # Check if this key matches context patterns
            if cls.match_parameter(key, "context")[0]:
                if "context" not in mappings:  # Use first match
                    mappings["context"] = current_path

            # Check if this key matches metadata patterns
            if cls.match_parameter(key, "metadata")[0]:
                if "metadata" not in mappings:  # Use first match
                    mappings["metadata"] = current_path

            # Check if this key matches tool_calls patterns
            if cls.match_parameter(key, "tool_calls")[0]:
                if "tool_calls" not in mappings:  # Use first match
                    mappings["tool_calls"] = current_path

            # Recurse into nested dicts
            if isinstance(value, dict):
                nested_mappings = cls.detect_nested_output_field(value, current_path)
                # Merge nested mappings (don't override already found fields)
                for field, field_path in nested_mappings.items():
                    if field not in mappings:
                        mappings[field] = field_path

        return mappings
