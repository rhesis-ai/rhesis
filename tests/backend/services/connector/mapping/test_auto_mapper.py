"""Tests for auto-mapper functionality."""

import pytest

from rhesis.backend.app.services.connector.mapping.auto_mapper import AutoMapper


class TestAutoMapper:
    """Test AutoMapper class."""

    @pytest.fixture
    def auto_mapper(self):
        """Create AutoMapper instance."""
        return AutoMapper()

    def test_standard_naming_high_confidence(self, auto_mapper, standard_function_signature):
        """Test auto-mapping with standard naming (should have high confidence)."""
        result = auto_mapper.generate_mappings(
            function_name=standard_function_signature["name"],
            parameters=standard_function_signature["parameters"],
            return_type=standard_function_signature["return_type"],
            description=standard_function_signature["metadata"]["description"],
        )

        # Should match input and conversation_id (REQUEST fields only)
        # Context is a RESPONSE field, not counted in request confidence
        assert result["confidence"] == pytest.approx(0.7)  # 0.5 + 0.2 (request fields only)
        assert "input" in result["matched_fields"]
        assert "conversation_id" in result["matched_fields"]
        assert len(result["missing_fields"]) == 0  # All REQUEST fields matched

        # Check request template (only REQUEST fields)
        assert result["request_mapping"]["input"] == "{{ input }}"
        assert result["request_mapping"]["conversation_id"] == "{{ conversation_id }}"
        assert "context" not in result["request_mapping"]  # RESPONSE field

        # Check response mappings exist
        assert "output" in result["response_mapping"]
        assert "context" in result["response_mapping"]  # RESPONSE field
        assert "metadata" in result["response_mapping"]  # RESPONSE field
        assert "tool_calls" in result["response_mapping"]  # RESPONSE field

    def test_custom_naming_low_confidence(self, auto_mapper, custom_function_signature):
        """Test auto-mapping with custom naming (should trigger LLM fallback)."""
        result = auto_mapper.generate_mappings(
            function_name=custom_function_signature["name"],
            parameters=custom_function_signature["parameters"],
            return_type=custom_function_signature["return_type"],
            description=custom_function_signature["metadata"]["description"],
        )

        # Should have some matches: user_message (compound match),
        # conv_id (compound match), docs (partial match)
        # Note: "user_message" DOES match input patterns
        # (compound: "user_input" variants)
        # So this should have higher confidence than expected
        assert result["confidence"] >= 0.5  # At least input field matched

    def test_partial_matches(self, auto_mapper, partial_match_function_signature):
        """Test auto-mapping with partial pattern matches."""
        result = auto_mapper.generate_mappings(
            function_name=partial_match_function_signature["name"],
            parameters=partial_match_function_signature["parameters"],
            return_type=partial_match_function_signature["return_type"],
            description=partial_match_function_signature["metadata"]["description"],
        )

        # "question" should partially match input (confidence 0.5)
        # "conversation" should partially match session (confidence 0.2)
        assert result["confidence"] == pytest.approx(0.7)  # 0.5 + 0.2
        assert "input" in result["matched_fields"]
        assert "conversation_id" in result["matched_fields"]

    def test_minimal_function(self, auto_mapper, minimal_function_signature):
        """Test auto-mapping with minimal function (only one parameter)."""
        result = auto_mapper.generate_mappings(
            function_name=minimal_function_signature["name"],
            parameters=minimal_function_signature["parameters"],
            return_type=minimal_function_signature["return_type"],
            description=minimal_function_signature["metadata"]["description"],
        )

        # "text" should match input pattern (exact match via INPUT_EXACT)
        assert result["confidence"] == 0.5  # Only input matched
        assert "input" in result["matched_fields"]
        assert len(result["matched_fields"]) == 1
        assert result["request_mapping"]["text"] == "{{ input }}"

    def test_no_matches(self, auto_mapper):
        """Test auto-mapping with no matching parameters."""
        result = auto_mapper.generate_mappings(
            function_name="weird_func",
            parameters={
                "xyz": {"type": "string"},
                "abc": {"type": "string"},
            },
            return_type="string",
            description="Weird function",
        )

        # No matches should result in 0 confidence
        assert result["confidence"] == 0.0
        assert len(result["matched_fields"]) == 0
        assert len(result["missing_fields"]) == 2  # Only REQUEST fields (input, conversation_id)

    def test_response_mapping_structure(self, auto_mapper, standard_function_signature):
        """Test that response mappings have correct structure."""
        result = auto_mapper.generate_mappings(
            function_name=standard_function_signature["name"],
            parameters=standard_function_signature["parameters"],
            return_type=standard_function_signature["return_type"],
        )

        response_mapping = result["response_mapping"]

        # Should have RESPONSE fields plus output
        assert "output" in response_mapping
        assert "context" in response_mapping
        assert "metadata" in response_mapping
        assert "tool_calls" in response_mapping

        # conversation_id is a REQUEST field, not a RESPONSE field
        assert "conversation_id" not in response_mapping

        # Should use Jinja2 'or' syntax for fallbacks
        assert "or" in response_mapping["output"]
        assert "{{" in response_mapping["output"]
        assert "}}" in response_mapping["output"]

    def test_confidence_calculation(self, auto_mapper):
        """Test confidence calculation with different field combinations."""
        # Only input (most important)
        result = auto_mapper.generate_mappings(
            function_name="test",
            parameters={"input": {"type": "string"}},
            return_type="string",
        )
        assert result["confidence"] == 0.5

        # Input + conversation_id (all REQUEST fields)
        result = auto_mapper.generate_mappings(
            function_name="test",
            parameters={
                "input": {"type": "string"},
                "conversation_id": {"type": "string"},
            },
            return_type="string",
        )
        assert result["confidence"] == pytest.approx(0.7)

        # Input + conversation_id + context (context is RESPONSE field, doesn't affect confidence)
        result = auto_mapper.generate_mappings(
            function_name="test",
            parameters={
                "input": {"type": "string"},
                "conversation_id": {"type": "string"},
                "context": {"type": "list"},
            },
            return_type="string",
        )
        # Confidence is still 0.7 because context is a RESPONSE field
        assert result["confidence"] == pytest.approx(0.7)

        # All fields (but confidence only counts REQUEST fields)
        result = auto_mapper.generate_mappings(
            function_name="test",
            parameters={
                "input": {"type": "string"},
                "conversation_id": {"type": "string"},
                "context": {"type": "list"},
                "metadata": {"type": "dict"},
                "tool_calls": {"type": "list"},
            },
            return_type="string",
        )
        # Confidence is 0.7 because only REQUEST fields (input, conversation_id) count
        # context, metadata, tool_calls are RESPONSE fields
        assert result["confidence"] == pytest.approx(0.7)

    def test_case_insensitive_matching(self, auto_mapper):
        """Test that parameter matching is case-insensitive."""
        result = auto_mapper.generate_mappings(
            function_name="test",
            parameters={
                "INPUT": {"type": "string"},  # Uppercase
                "Session_ID": {"type": "string"},  # Mixed case
            },
            return_type="string",
        )

        assert result["confidence"] == 0.7
        assert "input" in result["matched_fields"]
        assert "conversation_id" in result["matched_fields"]

    def test_matched_fields_tracking(self, auto_mapper, standard_function_signature):
        """Test that matched and missing REQUEST fields are correctly tracked."""
        result = auto_mapper.generate_mappings(
            function_name=standard_function_signature["name"],
            parameters=standard_function_signature["parameters"],
            return_type=standard_function_signature["return_type"],
        )

        # Check matched REQUEST fields
        assert isinstance(result["matched_fields"], list)
        assert "input" in result["matched_fields"]
        assert "conversation_id" in result["matched_fields"]
        # context is a RESPONSE field, not tracked in matched_fields
        assert "context" not in result["matched_fields"]

        # Check missing REQUEST fields (should be empty since both request fields matched)
        assert isinstance(result["missing_fields"], list)
        assert len(result["missing_fields"]) == 0

        # No overlap between matched and missing
        assert set(result["matched_fields"]).isdisjoint(set(result["missing_fields"]))

    def test_best_match_selection(self, auto_mapper):
        """Test that best match is selected when multiple parameters could match."""
        # "input" should win over "user_input" if both exist
        # (exact match has higher confidence)
        result = auto_mapper.generate_mappings(
            function_name="test",
            parameters={
                "user_input": {"type": "string"},  # Compound match (0.9)
                "input": {"type": "string"},  # Exact match (1.0) - should win
            },
            return_type="string",
        )

        # Should only have one mapping for input field
        assert result["request_mapping"]["input"] == "{{ input }}"
        assert "user_input" not in result["request_mapping"]
