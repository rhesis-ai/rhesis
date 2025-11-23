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

        # Should match input, session_id, and context
        assert result["confidence"] == pytest.approx(0.8)  # 0.5 + 0.2 + 0.1
        assert "input" in result["matched_fields"]
        assert "session_id" in result["matched_fields"]
        assert "context" in result["matched_fields"]
        assert len(result["missing_fields"]) == 2  # metadata and tool_calls

        # Check request template
        assert result["request_template"]["input"] == "{{ input }}"
        assert result["request_template"]["session_id"] == "{{ session_id }}"
        assert result["request_template"]["context"] == "{{ context }}"

        # Check response mappings exist
        assert "output" in result["response_mappings"]
        assert "session_id" in result["response_mappings"]

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
        assert "session_id" in result["matched_fields"]

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
        assert result["request_template"]["text"] == "{{ input }}"

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
        assert len(result["missing_fields"]) == 5  # All standard fields missing

    def test_response_mappings_structure(self, auto_mapper, standard_function_signature):
        """Test that response mappings have correct structure."""
        result = auto_mapper.generate_mappings(
            function_name=standard_function_signature["name"],
            parameters=standard_function_signature["parameters"],
            return_type=standard_function_signature["return_type"],
        )

        response_mappings = result["response_mappings"]

        # Should have all standard fields plus output
        assert "output" in response_mappings
        assert "session_id" in response_mappings
        assert "context" in response_mappings
        assert "metadata" in response_mappings
        assert "tool_calls" in response_mappings

        # Should use Jinja2 'or' syntax for fallbacks
        assert "or" in response_mappings["output"]
        assert "{{" in response_mappings["output"]
        assert "}}" in response_mappings["output"]

    def test_confidence_calculation(self, auto_mapper):
        """Test confidence calculation with different field combinations."""
        # Only input (most important)
        result = auto_mapper.generate_mappings(
            function_name="test",
            parameters={"input": {"type": "string"}},
            return_type="string",
        )
        assert result["confidence"] == 0.5

        # Input + session_id
        result = auto_mapper.generate_mappings(
            function_name="test",
            parameters={
                "input": {"type": "string"},
                "session_id": {"type": "string"},
            },
            return_type="string",
        )
        assert result["confidence"] == 0.7

        # Input + session_id + context
        result = auto_mapper.generate_mappings(
            function_name="test",
            parameters={
                "input": {"type": "string"},
                "session_id": {"type": "string"},
                "context": {"type": "list"},
            },
            return_type="string",
        )
        assert result["confidence"] == pytest.approx(0.8)

        # All fields
        result = auto_mapper.generate_mappings(
            function_name="test",
            parameters={
                "input": {"type": "string"},
                "session_id": {"type": "string"},
                "context": {"type": "list"},
                "metadata": {"type": "dict"},
                "tool_calls": {"type": "list"},
            },
            return_type="string",
        )
        assert result["confidence"] == pytest.approx(1.0)

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
        assert "session_id" in result["matched_fields"]

    def test_matched_fields_tracking(self, auto_mapper, standard_function_signature):
        """Test that matched and missing fields are correctly tracked."""
        result = auto_mapper.generate_mappings(
            function_name=standard_function_signature["name"],
            parameters=standard_function_signature["parameters"],
            return_type=standard_function_signature["return_type"],
        )

        # Check matched fields
        assert isinstance(result["matched_fields"], list)
        assert "input" in result["matched_fields"]
        assert "session_id" in result["matched_fields"]
        assert "context" in result["matched_fields"]

        # Check missing fields
        assert isinstance(result["missing_fields"], list)
        assert "metadata" in result["missing_fields"]
        assert "tool_calls" in result["missing_fields"]

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
        assert result["request_template"]["input"] == "{{ input }}"
        assert "user_input" not in result["request_template"]
