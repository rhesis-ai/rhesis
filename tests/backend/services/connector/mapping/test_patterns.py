"""Tests for pattern matching logic."""

from rhesis.backend.app.services.connector.mapping.patterns import (
    FieldConfig,
    MappingPatterns,
)


class TestFieldConfig:
    """Test FieldConfig dataclass."""

    def test_field_config_creation(self):
        """Test creating a FieldConfig."""
        config = FieldConfig(
            name="input",
            pattern_type="input",
            template_var="{{ input }}",
            confidence_weight=0.5,
            field_location="request",
            is_required=True,
        )
        assert config.name == "input"
        assert config.pattern_type == "input"
        assert config.template_var == "{{ input }}"
        assert config.confidence_weight == 0.5
        assert config.field_location == "request"
        assert config.is_required is True


class TestMappingPatterns:
    """Test pattern matching functionality."""

    def test_standard_fields_configuration(self):
        """Test that STANDARD_FIELDS is properly configured."""
        assert len(MappingPatterns.STANDARD_FIELDS) == 5
        field_names = [f.name for f in MappingPatterns.STANDARD_FIELDS]
        assert "input" in field_names
        assert "conversation_id" in field_names
        assert "context" in field_names
        assert "metadata" in field_names
        assert "tool_calls" in field_names

    def test_get_field_config(self):
        """Test retrieving field configuration."""
        config = MappingPatterns.get_field_config("input")
        assert config is not None
        assert config.name == "input"
        assert config.confidence_weight == 0.5

        config = MappingPatterns.get_field_config("nonexistent")
        assert config is None

    def test_input_exact_match(self):
        """Test exact input pattern matching."""
        matches, confidence = MappingPatterns.match_parameter("input", "input")
        assert matches is True
        assert confidence == 1.0

        matches, confidence = MappingPatterns.match_parameter("query", "input")
        assert matches is True
        assert confidence == 1.0

    def test_input_compound_match(self):
        """Test compound input pattern matching."""
        matches, confidence = MappingPatterns.match_parameter("user_input", "input")
        assert matches is True
        assert confidence == 0.9

        matches, confidence = MappingPatterns.match_parameter("chat_message", "input")
        assert matches is True
        assert confidence == 0.9

    def test_input_partial_match(self):
        """Test partial input pattern matching."""
        matches, confidence = MappingPatterns.match_parameter("user_question", "input")
        assert matches is True
        assert confidence == 0.7  # Contains "question"

    def test_session_exact_match(self):
        """Test exact session pattern matching."""
        matches, confidence = MappingPatterns.match_parameter("session_id", "session")
        assert matches is True
        assert confidence == 1.0

        matches, confidence = MappingPatterns.match_parameter("conversation_id", "session")
        assert matches is True
        assert confidence == 1.0

    def test_session_compound_match(self):
        """Test compound session pattern matching."""
        matches, confidence = MappingPatterns.match_parameter("conv_id", "session")
        assert matches is True
        assert confidence == 0.9

        matches, confidence = MappingPatterns.match_parameter("chat_session_id", "session")
        assert matches is True
        assert confidence == 0.9

    def test_session_partial_match(self):
        """Test partial session pattern matching."""
        matches, confidence = MappingPatterns.match_parameter("my_session", "session")
        assert matches is True
        assert confidence == 0.7  # Contains "sess"

    def test_context_patterns(self):
        """Test context pattern matching."""
        matches, confidence = MappingPatterns.match_parameter("context", "context")
        assert matches is True
        assert confidence == 1.0

        matches, confidence = MappingPatterns.match_parameter("rag_documents", "context")
        assert matches is True
        assert confidence == 0.9

        matches, confidence = MappingPatterns.match_parameter("search_docs", "context")
        assert matches is True
        assert confidence == 0.7

    def test_metadata_patterns(self):
        """Test metadata pattern matching."""
        matches, confidence = MappingPatterns.match_parameter("metadata", "metadata")
        assert matches is True
        assert confidence == 1.0

        matches, confidence = MappingPatterns.match_parameter("user_info", "metadata")
        assert matches is True
        assert confidence == 0.9

    def test_tool_calls_patterns(self):
        """Test tool_calls pattern matching."""
        matches, confidence = MappingPatterns.match_parameter("tool_calls", "tool_calls")
        assert matches is True
        assert confidence == 1.0

        matches, confidence = MappingPatterns.match_parameter("available_tools", "tool_calls")
        assert matches is True
        assert confidence == 0.9

    def test_no_match(self):
        """Test parameters that don't match any pattern."""
        matches, confidence = MappingPatterns.match_parameter("random_param", "input")
        assert matches is False
        assert confidence == 0.0

        matches, confidence = MappingPatterns.match_parameter("xyz", "session")
        assert matches is False
        assert confidence == 0.0

    def test_case_insensitivity(self):
        """Test that pattern matching is case-insensitive."""
        matches, confidence = MappingPatterns.match_parameter("INPUT", "input")
        assert matches is True

        matches, confidence = MappingPatterns.match_parameter("Session_ID", "session")
        assert matches is True

    def test_detect_nested_output_field(self):
        """Test detecting nested output fields in return structure."""
        return_structure = {
            "response": {"text": str, "id": str},
            "metadata": dict,
        }

        mappings = MappingPatterns.detect_nested_output_field(return_structure)
        assert "output" in mappings
        # Should find "response" first (matches output patterns)
        assert "$.response" in mappings["output"]
        assert "metadata" in mappings
        assert mappings["metadata"] == "$.metadata"

    def test_detect_nested_session_field(self):
        """Test detecting nested session fields."""
        return_structure = {
            "result": {"content": str},
            "conversation_id": str,
        }

        mappings = MappingPatterns.detect_nested_output_field(return_structure)
        assert "conversation_id" in mappings
        assert mappings["conversation_id"] == "$.conversation_id"

    def test_detect_deeply_nested_fields(self):
        """Test detecting deeply nested fields."""
        return_structure = {
            "data": {
                "result": {
                    "output": str,
                },
                "session_info": {
                    "session_id": str,
                },
            },
        }

        mappings = MappingPatterns.detect_nested_output_field(return_structure)
        assert "output" in mappings
        # Should find "result" or "output" - both match output patterns
        assert "$.data.result" in mappings["output"] or "$.data.result.output" in mappings["output"]
        assert "conversation_id" in mappings

    def test_get_all_patterns(self):
        """Test get_all_patterns method."""
        exact, compound, partial = MappingPatterns.get_all_patterns("input")
        assert "input" in exact
        assert "user_input" in compound
        assert "question" in partial

        exact, compound, partial = MappingPatterns.get_all_patterns("session")
        assert "session_id" in exact
        assert "conv_id" in compound
        assert "sess" in partial

        exact, compound, partial = MappingPatterns.get_all_patterns("nonexistent")
        assert exact == []
        assert compound == []
        assert partial == []
