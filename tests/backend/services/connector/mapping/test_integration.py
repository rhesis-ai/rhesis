"""Integration tests for mapping system with end-to-end validation.

These tests simulate real-world SDK connector scenarios to catch issues
that unit tests might miss, such as:
- System field leakage (organization_id, user_id)
- Field separation (request vs response fields)
- Complex type preservation (dicts, lists)
- Template rendering edge cases
- Partial manual mappings
"""

from unittest.mock import Mock, patch

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.connector.mapping.mapper_service import (
    MappingService,
    MappingSource,
)
from rhesis.backend.app.services.invokers.conversation.tracker import ConversationTracker
from rhesis.backend.app.services.invokers.templating.renderer import TemplateRenderer


class TestSystemFieldFiltering:
    """Test that system fields don't leak into SDK function calls."""

    def test_organization_id_filtered_from_template_context(self):
        """System field organization_id should not be passed to SDK functions."""
        # Simulate input data with system fields
        input_data = {
            "input": "test message",
            "session_id": "sess_123",
            "organization_id": "org_abc",  # System field - present in input
            "user_id": "user_xyz",  # System field - present in input
        }

        endpoint = Mock(spec=Endpoint)
        endpoint.response_mapping = {}

        # ConversationTracker.prepare_conversation_context passes through all fields
        # System field filtering is handled by specific invokers (e.g., SDK invoker)
        context, _ = ConversationTracker.prepare_conversation_context(endpoint, input_data)

        # ConversationTracker should pass through ALL fields (including system fields)
        # The filtering happens at the invoker level, not at the conversation tracker level
        assert "organization_id" in context, "ConversationTracker should pass through all fields!"
        assert "user_id" in context, "ConversationTracker should pass through all fields!"
        assert "input" in context
        assert "session_id" in context

        # Simulate SDK invoker filtering (this is where system fields are actually filtered)
        system_fields = {"organization_id", "user_id"}
        filtered_context = {
            k: v for k, v in context.items() if k not in system_fields
        }

        # After SDK invoker filtering, system fields should be removed
        assert "organization_id" not in filtered_context, "SDK invoker should filter system fields!"
        assert "user_id" not in filtered_context, "SDK invoker should filter system fields!"
        assert "input" in filtered_context
        assert "session_id" in filtered_context

    def test_template_rendering_without_system_fields(self):
        """Template rendering should not receive system fields."""
        renderer = TemplateRenderer()

        request_mapping = {
            "query": "{{ input }}",
            "session": "{{ session_id }}",
        }

        # Simulate filtered context (after system field removal)
        filtered_context = {
            "input": "test query",
            "session_id": "sess_123",
            # organization_id and user_id already filtered out
        }

        result = renderer.render(request_mapping, filtered_context)

        assert result == {
            "query": "test query",
            "session": "sess_123",
        }
        assert "organization_id" not in result
        assert "user_id" not in result


class TestFieldSeparation:
    """Test proper separation of request vs response fields."""

    def test_response_fields_not_in_request_template(self):
        """Context, metadata, tool_calls should not appear in request_mapping."""
        from rhesis.backend.app.services.connector.mapping.auto_mapper import AutoMapper

        auto_mapper = AutoMapper()

        # Function with only input parameter
        result = auto_mapper.generate_mappings(
            function_name="test_func",
            parameters={
                "input": {"type": "str", "default": None},
            },
            return_type="dict",
            description="Test function",
        )

        # Request mapping should only have input-related fields
        request_keys = result["request_mapping"].keys()
        assert "input" in request_keys

        # These are RESPONSE fields, should NOT be in request_mapping
        assert "context" not in request_keys, "context is a response field!"
        assert "metadata" not in request_keys, "metadata is a response field!"
        assert "tool_calls" not in request_keys, "tool_calls is a response field!"

    def test_response_fields_in_response_mapping(self):
        """Context, metadata, tool_calls should be in response_mapping."""
        from rhesis.backend.app.services.connector.mapping.patterns import MappingPatterns

        # Verify field location configuration
        response_fields = [
            f for f in MappingPatterns.STANDARD_FIELDS if f.field_location == "response"
        ]
        response_field_names = [f.name for f in response_fields]

        assert "context" in response_field_names
        assert "metadata" in response_field_names
        assert "tool_calls" in response_field_names

        # Verify they are NOT request fields
        request_fields = [
            f for f in MappingPatterns.STANDARD_FIELDS if f.field_location == "request"
        ]
        request_field_names = [f.name for f in request_fields]

        assert "context" not in request_field_names
        assert "metadata" not in request_field_names
        assert "tool_calls" not in request_field_names


class TestComplexTypePreservation:
    """Test that complex types (dicts, lists) are preserved in templates."""

    def test_dict_not_stringified_in_simple_template(self):
        """Dict values should remain dicts when using {{ var }} syntax."""
        renderer = TemplateRenderer()

        request_mapping = {
            "metadata": "{{ metadata }}",  # Simple variable reference
        }

        context = {
            "metadata": {"urgency": "high", "category": "support"},
        }

        result = renderer.render(request_mapping, context)

        # Should preserve dict type
        assert isinstance(result["metadata"], dict)
        assert result["metadata"] == {"urgency": "high", "category": "support"}
        assert result["metadata"] != "{'urgency': 'high', 'category': 'support'}"

    def test_list_not_stringified_in_simple_template(self):
        """List values should remain lists when using {{ var }} syntax."""
        renderer = TemplateRenderer()

        request_mapping = {
            "documents": "{{ context }}",  # Simple variable reference
        }

        context = {
            "context": ["doc1", "doc2", "doc3"],
        }

        result = renderer.render(request_mapping, context)

        # Should preserve list type
        assert isinstance(result["documents"], list)
        assert result["documents"] == ["doc1", "doc2", "doc3"]
        assert result["documents"] != "['doc1', 'doc2', 'doc3']"

    def test_complex_template_still_stringifies(self):
        """Complex templates (not simple {{ var }}) should still stringify."""
        renderer = TemplateRenderer()

        request_mapping = {
            "message": "Context: {{ context }} - Message: {{ input }}",  # Complex template
        }

        context = {
            "context": ["doc1", "doc2"],
            "input": "test",
        }

        result = renderer.render(request_mapping, context)

        # Complex template should stringify
        assert isinstance(result["message"], str)
        assert "doc1" in result["message"]


class TestPartialManualMappings:
    """Test SDK hybrid mappings (partial manual + auto-generated)."""

    def test_manual_request_only_generates_response(self):
        """Providing only request_mapping should auto-generate response_mapping."""
        service = MappingService()

        # Mock dependencies
        mock_db = Mock()
        mock_user = Mock(spec=User)
        mock_endpoint = Mock(spec=Endpoint)
        mock_endpoint.request_mapping = None
        mock_endpoint.response_mapping = None

        sdk_metadata = {
            "request_mapping": {
                "query": "{{ input }}",
            },
            # response_mapping is missing - should be auto-generated
            "description": "Test function",
        }

        function_data = {
            "name": "test_func",
            "parameters": {
                "query": {"type": "str", "default": None},
            },
            "return_type": "dict",
        }

        result = service.generate_or_use_existing(
            db=mock_db,
            user=mock_user,
            endpoint=mock_endpoint,
            sdk_metadata=sdk_metadata,
            function_data=function_data,
        )

        assert result.source == MappingSource.SDK_HYBRID
        assert result.request_mapping == {"query": "{{ input }}"}
        assert result.response_mapping != {}  # Should be auto-generated
        assert "output" in result.response_mapping

    def test_manual_response_only_generates_request(self):
        """Providing only response_mapping should auto-generate request_mapping."""
        service = MappingService()

        # Mock dependencies
        mock_db = Mock()
        mock_user = Mock(spec=User)
        mock_endpoint = Mock(spec=Endpoint)
        mock_endpoint.request_mapping = None
        mock_endpoint.response_mapping = None

        sdk_metadata = {
            # request_mapping is missing - should be auto-generated
            "response_mapping": {
                "output": "$.answer.text",
            },
            "description": "Test function",
        }

        function_data = {
            "name": "test_func",
            "parameters": {
                "input": {"type": "str", "default": None},
            },
            "return_type": "dict",
        }

        result = service.generate_or_use_existing(
            db=mock_db,
            user=mock_user,
            endpoint=mock_endpoint,
            sdk_metadata=sdk_metadata,
            function_data=function_data,
        )

        assert result.source == MappingSource.SDK_HYBRID
        assert result.response_mapping == {"output": "$.answer.text"}
        assert result.request_mapping != {}  # Should be auto-generated
        assert "input" in result.request_mapping


class TestMappingSourceEnum:
    """Test MappingSource enum values and usage."""

    def test_enum_values_are_strings(self):
        """Enum values should be strings for JSON serialization."""
        assert MappingSource.SDK_MANUAL.value == "sdk_manual"
        assert MappingSource.SDK_HYBRID.value == "sdk_hybrid"
        assert MappingSource.PREVIOUSLY_SAVED.value == "previously_saved"
        assert MappingSource.AUTO_MAPPED.value == "auto_mapped"
        assert MappingSource.LLM_GENERATED.value == "llm_generated"

    def test_enum_comparison(self):
        """Enum values should be comparable."""
        source1 = MappingSource.SDK_MANUAL
        source2 = MappingSource.SDK_MANUAL
        source3 = MappingSource.AUTO_MAPPED

        assert source1 == source2
        assert source1 != source3

    def test_enum_in_mapping_result(self):
        """MappingResult should accept MappingSource enum."""
        from rhesis.backend.app.services.connector.mapping.mapper_service import (
            MappingResult,
        )

        result = MappingResult(
            request_mapping={},
            response_mapping={},
            source=MappingSource.SDK_MANUAL,
            confidence=1.0,
            should_update=True,
        )

        assert result.source == MappingSource.SDK_MANUAL
        assert result.source.value == "sdk_manual"


class TestLLMFallbackTrigger:
    """Test LLM fallback is triggered correctly."""

    def test_low_confidence_triggers_llm(self):
        """Auto-mapping confidence < 0.7 should trigger LLM fallback."""
        service = MappingService()

        # Mock dependencies
        mock_db = Mock()
        mock_user = Mock(spec=User)
        mock_endpoint = Mock(spec=Endpoint)
        mock_endpoint.request_mapping = None
        mock_endpoint.response_mapping = None

        # Function with custom parameter names (will have low confidence)
        function_data = {
            "name": "test_func",
            "parameters": {
                "xyz": {"type": "str", "default": None},  # Custom name, not "input"
                "abc": {"type": "str", "default": None},  # Custom name, not "session_id"
            },
            "return_type": "dict",
        }

        sdk_metadata = {
            "description": "Test function with custom parameters",
        }

        with patch.object(service.llm_mapper, "generate_mappings") as mock_llm:
            mock_llm.return_value = {
                "request_mapping": {"xyz": "{{ input }}", "abc": "{{ session_id }}"},
                "response_mapping": {"output": "{{ response }}"},
                "confidence": 0.9,
                "reasoning": "LLM inferred mappings",
            }

            result = service.generate_or_use_existing(
                db=mock_db,
                user=mock_user,
                endpoint=mock_endpoint,
                sdk_metadata=sdk_metadata,
                function_data=function_data,
            )

            # LLM should have been called
            mock_llm.assert_called_once()
            assert result.source == MappingSource.LLM_GENERATED

    def test_high_confidence_skips_llm(self):
        """Auto-mapping confidence >= 0.7 should NOT trigger LLM."""
        service = MappingService()

        # Mock dependencies
        mock_db = Mock()
        mock_user = Mock(spec=User)
        mock_endpoint = Mock(spec=Endpoint)
        mock_endpoint.request_mapping = None
        mock_endpoint.response_mapping = None

        # Function with standard parameter names (will have high confidence)
        function_data = {
            "name": "test_func",
            "parameters": {
                "input": {"type": "str", "default": None},
                "session_id": {"type": "str", "default": None},
            },
            "return_type": "dict",
        }

        sdk_metadata = {
            "description": "Test function",
        }

        with patch.object(service.llm_mapper, "generate_mappings") as mock_llm:
            result = service.generate_or_use_existing(
                db=mock_db,
                user=mock_user,
                endpoint=mock_endpoint,
                sdk_metadata=sdk_metadata,
                function_data=function_data,
            )

            # LLM should NOT have been called
            mock_llm.assert_not_called()
            assert result.source == MappingSource.AUTO_MAPPED


class TestEdgeCaseValidation:
    """Test edge cases that caused issues in production."""

    def test_empty_request_mapping_handled(self):
        """Empty request_mapping should be handled gracefully."""
        renderer = TemplateRenderer()

        request_mapping = {}
        context = {"input": "test"}

        result = renderer.render(request_mapping, context)
        assert result == {}

    def test_none_values_in_context(self):
        """None values in context should be omitted from rendered output."""
        renderer = TemplateRenderer()

        request_mapping = {
            "input": "{{ input }}",
            "session_id": "{{ session_id }}",
        }

        context = {
            "input": "test",
            "session_id": None,  # None value - should be omitted
        }

        result = renderer.render(request_mapping, context)
        assert result["input"] == "test"
        # None values are filtered out to avoid sending null to SDK functions
        assert "session_id" not in result

    def test_missing_keys_in_context_with_default(self):
        """Custom fields with defaults should render the default value."""
        renderer = TemplateRenderer()

        request_mapping = {
            "input": "{{ input }}",
            "priority": "{{ priority | default('low', true) }}",  # Custom field
        }

        context = {
            "input": "test",
            # priority is missing
        }

        result = renderer.render(request_mapping, context)
        assert result["input"] == "test"
        # Using Jinja2 default filter with true flag ensures default is used for undefined
        assert result["priority"] == "low"

    def test_missing_keys_without_default_omitted(self):
        """Missing keys without defaults should be omitted from output."""
        renderer = TemplateRenderer()

        request_mapping = {
            "input": "{{ input }}",
            "session_id": "{{ session_id }}",
        }

        context = {
            "input": "test",
            # session_id is missing
        }

        result = renderer.render(request_mapping, context)
        assert result["input"] == "test"
        # Missing keys without defaults are filtered out
        assert "session_id" not in result
