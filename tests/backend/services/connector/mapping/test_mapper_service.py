"""Tests for mapper service orchestration."""

from unittest.mock import Mock, patch

import pytest

from rhesis.backend.app.services.connector.mapping.mapper_service import (
    MappingResult,
    MappingService,
)

# Import patch for the LLM fallback test


class TestMappingResult:
    """Test MappingResult Pydantic model."""

    def test_create_mapping_result(self):
        """Test creating a valid MappingResult."""
        result = MappingResult(
            request_mapping={"input": "{{ input }}"},
            response_mapping={"output": "{{ response }}"},
            source="auto_mapped",
            confidence=0.8,
            should_update=True,
            reasoning="Auto-detected from function signature",
        )

        assert result.request_mapping == {"input": "{{ input }}"}
        assert result.response_mapping == {"output": "{{ response }}"}
        assert result.source == "auto_mapped"
        assert result.confidence == 0.8
        assert result.should_update is True
        assert result.reasoning == "Auto-detected from function signature"

    def test_confidence_validation(self):
        """Test that confidence is validated (0.0-1.0)."""
        # Valid confidence
        result = MappingResult(
            request_mapping={},
            response_mapping={},
            source="auto_mapped",
            confidence=0.5,
            should_update=True,
        )
        assert result.confidence == 0.5

        # Invalid confidence (too high)
        with pytest.raises(Exception):  # Pydantic ValidationError
            MappingResult(
                request_mapping={},
                response_mapping={},
                source="auto_mapped",
                confidence=1.5,
                should_update=True,
            )

        # Invalid confidence (negative)
        with pytest.raises(Exception):
            MappingResult(
                request_mapping={},
                response_mapping={},
                source="auto_mapped",
                confidence=-0.1,
                should_update=True,
            )

    def test_source_literal_validation(self):
        """Test that source is validated against allowed values."""
        # Valid sources (updated enum values)
        valid_sources = [
            "sdk_manual",
            "sdk_hybrid",
            "previously_saved",
            "auto_mapped",
            "llm_generated",
        ]
        for source in valid_sources:
            result = MappingResult(
                request_mapping={},
                response_mapping={},
                source=source,
                confidence=0.8,
                should_update=True,
            )
            assert result.source == source

    def test_default_reasoning(self):
        """Test that reasoning has a default value."""
        result = MappingResult(
            request_mapping={},
            response_mapping={},
            source="auto_mapped",
            confidence=0.8,
            should_update=True,
        )
        assert result.reasoning == ""


class TestMappingService:
    """Test MappingService orchestration."""

    @pytest.fixture
    def mapping_service(self):
        """Create MappingService instance."""
        return MappingService()

    def test_priority_1_sdk_manual_mappings(
        self,
        mapping_service,
        mock_db_session,
        mock_user,
        mock_endpoint,
        standard_function_signature,
        sdk_metadata_with_manual_mappings,
    ):
        """Test Priority 1: SDK manual mappings take precedence."""
        result = mapping_service.generate_or_use_existing(
            db=mock_db_session,
            user=mock_user,
            endpoint=mock_endpoint,
            sdk_metadata=sdk_metadata_with_manual_mappings,
            function_data=standard_function_signature,
        )

        assert isinstance(result, MappingResult)
        assert result.source == "sdk_manual"
        assert result.confidence == 1.0
        assert result.should_update is True
        assert result.request_mapping == sdk_metadata_with_manual_mappings["request_mapping"]
        assert result.response_mapping == sdk_metadata_with_manual_mappings["response_mapping"]
        assert "Explicit mappings" in result.reasoning

    def test_priority_2_existing_db_mappings(
        self,
        mapping_service,
        mock_db_session,
        mock_user,
        mock_endpoint_with_existing_mappings,
        standard_function_signature,
    ):
        """Test Priority 2: Existing DB mappings are preserved."""
        result = mapping_service.generate_or_use_existing(
            db=mock_db_session,
            user=mock_user,
            endpoint=mock_endpoint_with_existing_mappings,
            sdk_metadata={},
            function_data=standard_function_signature,
        )

        assert isinstance(result, MappingResult)
        assert result.source == "previously_saved"
        assert result.confidence == 1.0
        assert result.should_update is False  # Don't overwrite existing mappings
        assert result.request_mapping == mock_endpoint_with_existing_mappings.request_mapping
        assert result.response_mapping == mock_endpoint_with_existing_mappings.response_mapping
        assert "preserved" in result.reasoning.lower()

    def test_priority_3_auto_mapping_high_confidence(
        self,
        mapping_service,
        mock_db_session,
        mock_user,
        mock_endpoint,
        standard_function_signature,
    ):
        """Test Priority 3: Auto-mapping with high confidence (>= 0.7)."""
        result = mapping_service.generate_or_use_existing(
            db=mock_db_session,
            user=mock_user,
            endpoint=mock_endpoint,
            sdk_metadata={},  # No manual mappings
            function_data=standard_function_signature,
        )

        assert isinstance(result, MappingResult)
        assert result.source == "auto_mapped"
        assert result.confidence >= 0.7
        assert result.should_update is True
        assert "input" in result.request_mapping
        assert "session_id" in result.request_mapping
        assert "Auto-detected" in result.reasoning

    def test_priority_4_llm_fallback(
        self,
        mapping_service,
        mock_db_session,
        mock_user,
        mock_endpoint,
    ):
        """Test Priority 4: LLM fallback when auto-mapping confidence is low."""
        # Create a function signature with NO matching patterns
        no_match_signature = {
            "name": "weird_func",
            "parameters": {
                "xyz": {"type": "string"},  # No pattern match
                "abc": {"type": "number"},  # No pattern match
            },
            "return_type": "dict",
        }

        # Mock the LLM mapper
        with patch.object(mapping_service.llm_mapper, "generate_mappings") as mock_llm:
            mock_llm.return_value = {
                "request_mapping": {"xyz": "{{ input }}"},
                "response_mapping": {"output": "{{ response }}"},
                "confidence": 0.85,
                "reasoning": "Generated by LLM",
            }

            result = mapping_service.generate_or_use_existing(
                db=mock_db_session,
                user=mock_user,
                endpoint=mock_endpoint,
                sdk_metadata={},
                function_data=no_match_signature,
            )

            # Should fall back to LLM since auto-mapping confidence will be 0.0 (< 0.7)
            assert isinstance(result, MappingResult)
            assert result.source == "llm_generated"
            assert result.should_update is True
            mock_llm.assert_called_once()

    def test_priority_cascade(
        self,
        mapping_service,
        mock_db_session,
        mock_user,
        standard_function_signature,
        sdk_metadata_with_manual_mappings,
    ):
        """Test that priorities cascade correctly."""
        # Priority 1 wins over Priority 2
        mock_endpoint_with_existing = Mock()
        mock_endpoint_with_existing.request_mapping = {"old": "{{ input }}"}
        mock_endpoint_with_existing.response_mapping = {"output": "{{ old }}"}

        result = mapping_service.generate_or_use_existing(
            db=mock_db_session,
            user=mock_user,
            endpoint=mock_endpoint_with_existing,
            sdk_metadata=sdk_metadata_with_manual_mappings,  # Has manual mappings
            function_data=standard_function_signature,
        )

        # Should use SDK manual mappings, not existing DB mappings
        assert result.source == "sdk_manual"
        assert result.request_mapping != mock_endpoint_with_existing.request_mapping

    def test_partial_sdk_metadata(
        self,
        mapping_service,
        mock_db_session,
        mock_user,
        mock_endpoint,
        standard_function_signature,
    ):
        """Test hybrid mapping when only one mapping is provided."""
        # Only request_mapping (no response_mapping)
        sdk_metadata = {"request_mapping": {"input": "{{ input }}"}}

        result = mapping_service.generate_or_use_existing(
            db=mock_db_session,
            user=mock_user,
            endpoint=mock_endpoint,
            sdk_metadata=sdk_metadata,
            function_data=standard_function_signature,
        )

        # Should use hybrid approach: manual request + auto-generated response
        assert result.source == "sdk_hybrid"
        assert result.request_mapping == {"input": "{{ input }}"}
        assert result.response_mapping != {}  # Auto-generated

    def test_empty_endpoint_triggers_auto_mapping(
        self,
        mapping_service,
        mock_db_session,
        mock_user,
        mock_endpoint,
        standard_function_signature,
    ):
        """Test that empty endpoint without mappings triggers auto-mapping."""
        # Endpoint with no mappings
        mock_endpoint.request_mapping = None
        mock_endpoint.response_mapping = None

        result = mapping_service.generate_or_use_existing(
            db=mock_db_session,
            user=mock_user,
            endpoint=mock_endpoint,
            sdk_metadata={},
            function_data=standard_function_signature,
        )

        # Should use auto-mapping
        assert result.source == "auto_mapped"
        assert result.confidence >= 0.7

    def test_result_attributes(self, mapping_service):
        """Test that MappingResult has all expected attributes."""
        result = MappingResult(
            request_mapping={"input": "{{ input }}"},
            response_mapping={"output": "{{ response }}"},
            source="auto_mapped",
            confidence=0.8,
            should_update=True,
            reasoning="Test reasoning",
        )

        # Verify all attributes are accessible
        assert result.request_mapping == {"input": "{{ input }}"}
        assert result.response_mapping == {"output": "{{ response }}"}
        assert result.source == "auto_mapped"
        assert result.confidence == 0.8
        assert result.should_update is True
        assert result.reasoning == "Test reasoning"

    def test_all_standard_fields_matched(
        self, mapping_service, mock_db_session, mock_user, mock_endpoint
    ):
        """Test function with all standard fields matched."""
        all_fields_signature = {
            "name": "comprehensive_chat",
            "parameters": {
                "input": {"type": "string"},
                "session_id": {"type": "string"},
                "context": {"type": "list"},
                "metadata": {"type": "dict"},
                "tool_calls": {"type": "list"},
            },
            "return_type": "dict",
        }

        result = mapping_service.generate_or_use_existing(
            db=mock_db_session,
            user=mock_user,
            endpoint=mock_endpoint,
            sdk_metadata={},
            function_data=all_fields_signature,
        )

        # Only request fields (input, session_id) should be in request_mapping
        # context, metadata, tool_calls are RESPONSE fields
        assert result.confidence == pytest.approx(0.7)  # Only 2/5 matched (request fields)
        assert result.source == "auto_mapped"
        assert len(result.request_mapping) == 2  # Only request fields (input, session_id)
        assert "input" in result.request_mapping
        assert "session_id" in result.request_mapping
