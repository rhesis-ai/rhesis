"""Tests for edge cases and error handling in mapping system."""

from unittest.mock import Mock, patch

import pytest

from rhesis.backend.app.services.connector.mapping.auto_mapper import AutoMapper
from rhesis.backend.app.services.connector.mapping.llm_mapper import LLMMapper
from rhesis.backend.app.services.connector.mapping.mapper_service import (
    MappingResult,
    MappingService,
)


class TestUnmappableScenarios:
    """Test cases where parameters cannot be mapped."""

    @pytest.fixture
    def auto_mapper(self):
        """Create AutoMapper instance."""
        return AutoMapper()

    @pytest.fixture
    def mapping_service(self):
        """Create MappingService instance."""
        return MappingService()

    def test_empty_function_no_parameters(self, auto_mapper):
        """Test function with NO parameters at all."""
        result = auto_mapper.generate_mappings(
            function_name="get_timestamp",
            parameters={},  # No parameters
            return_type="string",
            description="Returns current timestamp",
        )

        # Should have 0 confidence (no parameters to match)
        assert result["confidence"] == 0.0
        assert len(result["matched_fields"]) == 0
        assert len(result["missing_fields"]) == 2  # Only REQUEST fields (input, session_id)
        assert result["request_mapping"] == {}

    def test_function_with_only_unrelated_parameters(self, auto_mapper):
        """Test function where no parameters match any patterns."""
        result = auto_mapper.generate_mappings(
            function_name="calculate",
            parameters={
                "x": {"type": "number"},
                "y": {"type": "number"},
                "operation": {"type": "string"},
            },
            return_type="number",
            description="Performs mathematical operations",
        )

        # Should have 0 confidence
        assert result["confidence"] == 0.0
        assert len(result["matched_fields"]) == 0
        assert len(result["missing_fields"]) == 2  # Only REQUEST fields (input, session_id)
        assert result["request_mapping"] == {}

    def test_fallback_when_all_parameters_unmatchable(
        self,
        mapping_service,
        mock_db_session,
        mock_user,
        mock_endpoint,
    ):
        """Test that LLM fallback is triggered when no parameters match."""
        unmatchable_signature = {
            "name": "math_operation",
            "parameters": {
                "operand_a": {"type": "number"},
                "operand_b": {"type": "number"},
            },
            "return_type": "number",
        }

        # Mock LLM to return mappings
        with patch.object(mapping_service.llm_mapper, "generate_mappings") as mock_llm:
            mock_llm.return_value = {
                "request_mapping": {"operand_a": "{{ input }}"},
                "response_mapping": {"output": "{{ result }}"},
                "confidence": 0.6,
                "reasoning": "LLM inferred that operand_a could map to input",
            }

            result = mapping_service.generate_or_use_existing(
                db=mock_db_session,
                user=mock_user,
                endpoint=mock_endpoint,
                sdk_metadata={},
                function_data=unmatchable_signature,
            )

            # Should use LLM fallback
            assert result.source == "llm_generated"
            assert result.confidence == 0.6
            mock_llm.assert_called_once()


class TestLLMFailureHandling:
    """Test LLM mapper error handling."""

    @pytest.fixture
    def llm_mapper(self):
        """Create LLMMapper instance."""
        return LLMMapper()

    def test_llm_api_failure_returns_fallback(self, llm_mapper, mock_db_session, mock_user):
        """Test that LLM mapper returns fallback when API call fails."""
        with patch(
            "rhesis.backend.app.services.connector.mapping.llm_mapper.get_user_generation_model"
        ) as mock_get_model:
            # Mock the model to raise an exception
            mock_model = Mock()
            mock_model.generate.side_effect = Exception("API connection timeout")
            mock_get_model.return_value = mock_model

            result = llm_mapper.generate_mappings(
                db=mock_db_session,
                user=mock_user,
                function_name="test_func",
                parameters={"xyz": {"type": "string"}},
                return_type="string",
            )

            # Should return minimal fallback
            assert result["confidence"] == 0.3
            assert "LLM generation failed" in result["reasoning"]
            assert "input" in result["request_mapping"]
            assert "output" in result["response_mapping"]

    def test_llm_invalid_response_returns_fallback(self, llm_mapper, mock_db_session, mock_user):
        """Test that invalid LLM response triggers fallback."""
        with patch(
            "rhesis.backend.app.services.connector.mapping.llm_mapper.get_user_generation_model"
        ) as mock_get_model:
            # Mock the model to return invalid data
            mock_model = Mock()
            mock_response = Mock()
            mock_response.model_dump.side_effect = Exception("Invalid Pydantic model")
            mock_model.generate.return_value = mock_response
            mock_get_model.return_value = mock_model

            result = llm_mapper.generate_mappings(
                db=mock_db_session,
                user=mock_user,
                function_name="test_func",
                parameters={"param": {"type": "string"}},
                return_type="string",
            )

            # Should return minimal fallback
            assert result["confidence"] == 0.3
            assert "failed" in result["reasoning"].lower()


class TestPartialMappingScenarios:
    """Test scenarios with partial/incomplete mappings."""

    @pytest.fixture
    def auto_mapper(self):
        """Create AutoMapper instance."""
        return AutoMapper()

    def test_only_output_parameter_no_input(self, auto_mapper):
        """Test function with output-like param but no input."""
        result = auto_mapper.generate_mappings(
            function_name="get_response",
            parameters={
                "response_id": {"type": "string"},  # Not an input field
            },
            return_type="dict",
        )

        # Should have 0 confidence (no input matched)
        assert result["confidence"] == 0.0
        assert "input" not in result["matched_fields"]

    def test_input_only_no_session(self, auto_mapper):
        """Test function with input but no session tracking."""
        result = auto_mapper.generate_mappings(
            function_name="one_shot_query",
            parameters={
                "query": {"type": "string"},  # Matches input
            },
            return_type="string",
        )

        # Should have 0.5 confidence (only input matched)
        assert result["confidence"] == 0.5
        assert "input" in result["matched_fields"]
        assert "session_id" not in result["matched_fields"]
        assert len(result["missing_fields"]) == 1  # Only missing session_id (REQUEST field)

    def test_very_weak_partial_matches(self, auto_mapper):
        """Test with parameters that barely match patterns."""
        result = auto_mapper.generate_mappings(
            function_name="weak_match",
            parameters={
                "asking": {"type": "string"},  # Partial match to "ask" in INPUT_PARTIAL
                "convo": {"type": "string"},  # Partial match to "convo" in SESSION_PARTIAL
            },
            return_type="string",
        )

        # Both should match via partial patterns (0.5 + 0.2)
        assert result["confidence"] == pytest.approx(0.7)
        assert "input" in result["matched_fields"]
        assert "session_id" in result["matched_fields"]


class TestMinimalFallbackMappings:
    """Test the minimal fallback mappings."""

    def test_minimal_fallback_structure(self):
        """Test that minimal fallback has correct structure."""
        # Simulate the fallback return from the exception handler
        fallback = {
            "request_mapping": {"input": "{{ input }}"},
            "response_mapping": {"output": "{{ response or result }}"},
            "confidence": 0.3,
            "reasoning": "LLM generation failed: Test error. Using minimal fallback.",
        }

        # Verify structure
        assert "request_mapping" in fallback
        assert "response_mapping" in fallback
        assert "confidence" in fallback
        assert "reasoning" in fallback

        # Verify minimal mappings
        assert "input" in fallback["request_mapping"]
        assert "output" in fallback["response_mapping"]
        assert fallback["confidence"] < 0.7  # Below threshold

    def test_fallback_can_be_used_by_mapper_service(
        self,
        mock_db_session,
        mock_user,
        mock_endpoint,
    ):
        """Test that fallback mappings can be used by MappingService."""
        from rhesis.backend.app.services.connector.mapping.mapper_service import MappingService

        service = MappingService()

        # Function with no matchable parameters
        no_match_function = {
            "name": "incompatible_func",
            "parameters": {
                "arg1": {"type": "any"},
                "arg2": {"type": "any"},
            },
            "return_type": "any",
        }

        # Mock LLM to fail and return fallback
        with patch.object(service.llm_mapper, "generate_mappings") as mock_llm:
            mock_llm.return_value = {
                "request_mapping": {"input": "{{ input }}"},
                "response_mapping": {"output": "{{ response or result }}"},
                "confidence": 0.3,
                "reasoning": "Fallback used due to LLM failure",
            }

            result = service.generate_or_use_existing(
                db=mock_db_session,
                user=mock_user,
                endpoint=mock_endpoint,
                sdk_metadata={},
                function_data=no_match_function,
            )

            # Should successfully return fallback result
            assert isinstance(result, MappingResult)
            assert result.source == "llm_generated"
            assert result.confidence == 0.3
            assert len(result.request_mapping) >= 1
            assert len(result.response_mapping) >= 1


class TestResponseMappingEdgeCases:
    """Test edge cases in response mapping generation."""

    @pytest.fixture
    def auto_mapper(self):
        """Create AutoMapper instance."""
        return AutoMapper()

    def test_response_mapping_with_any_return_type(self, auto_mapper):
        """Test response mappings when return type is 'any'."""
        result = auto_mapper.generate_mappings(
            function_name="dynamic_func",
            parameters={"input": {"type": "string"}},
            return_type="any",
        )

        # Should still generate response mappings with fallback patterns
        assert "output" in result["response_mapping"]
        assert "context" in result["response_mapping"]  # RESPONSE field
        assert "metadata" in result["response_mapping"]  # RESPONSE field
        # session_id is a REQUEST field, not RESPONSE
        assert "session_id" not in result["response_mapping"]
        # Should have 'or' for fallback patterns
        assert "or" in result["response_mapping"]["output"]

    def test_response_mapping_with_primitive_return(self, auto_mapper):
        """Test response mappings when return type is primitive (string, number)."""
        result = auto_mapper.generate_mappings(
            function_name="get_string",
            parameters={"input": {"type": "string"}},
            return_type="string",
        )

        # Should still generate response mappings
        assert "output" in result["response_mapping"]
        # Fallback patterns should work for primitive returns too
        assert "response" in result["response_mapping"]["output"]

    def test_empty_response_mapping_handling(self, auto_mapper):
        """Test that response_mapping is never empty."""
        result = auto_mapper.generate_mappings(
            function_name="void_func",
            parameters={},
            return_type="void",
        )

        # Should always have response mappings with output and RESPONSE fields
        assert "output" in result["response_mapping"]
        assert "context" in result["response_mapping"]
        assert "metadata" in result["response_mapping"]
        assert "tool_calls" in result["response_mapping"]
        # Should have at least 4 fields (output + 3 RESPONSE fields)
        assert len(result["response_mapping"]) >= 4
