"""Tests for response mapping functionality."""

from rhesis.backend.app.services.invokers.templating.response_mapper import ResponseMapper


class TestResponseMapper:
    """Test ResponseMapper class functionality."""

    def test_map_response_with_pure_jsonpath(self):
        """Test mapping with pure JSONPath expressions."""
        mapper = ResponseMapper()
        response_data = {
            "message": "Hello World",
            "usage": {"tokens": 42},
            "metadata": {"id": "123"},
        }
        mappings = {
            "output": "$.message",
            "tokens": "$.usage.tokens",
            "id": "$.metadata.id",
        }

        result = mapper.map_response(response_data, mappings)

        assert result["output"] == "Hello World"
        assert result["tokens"] == 42
        assert result["id"] == "123"

    def test_map_response_with_jinja2_conditional(self):
        """Test mapping with Jinja2 template and conditional logic."""
        mapper = ResponseMapper()
        response_data = {
            "text_response": "",
            "sql_query_result": "SELECT * FROM users",
            "table_data": "[...]",
        }
        mappings = {
            "output": "{{ text_response or sql_query_result }}",
        }

        result = mapper.map_response(response_data, mappings)

        assert result["output"] == "SELECT * FROM users"

    def test_map_response_with_jsonpath_function_in_jinja(self):
        """Test using jsonpath() function within Jinja2 templates."""
        mapper = ResponseMapper()
        response_data = {
            "response": {"text": "Paris"},
            "alt_response": {"content": "France"},
        }
        mappings = {
            "output": "{{ jsonpath('$.response.text') or jsonpath('$.alt_response.content') }}",
        }

        result = mapper.map_response(response_data, mappings)

        assert result["output"] == "Paris"

    def test_map_response_jsonpath_fallback_in_jinja(self):
        """Test JSONPath fallback when first path doesn't exist."""
        mapper = ResponseMapper()
        response_data = {
            "alt_response": {"content": "Fallback value"},
        }
        mappings = {
            "output": "{{ jsonpath('$.response.text') or jsonpath('$.alt_response.content') }}",
        }

        result = mapper.map_response(response_data, mappings)

        assert result["output"] == "Fallback value"

    def test_map_response_with_missing_field(self):
        """Test mapping with JSONPath that doesn't match any data."""
        mapper = ResponseMapper()
        response_data = {"message": "Hello"}
        mappings = {"output": "$.nonexistent.field"}

        result = mapper.map_response(response_data, mappings)

        assert result["output"] is None

    def test_map_response_with_direct_field_access(self):
        """Test Jinja2 template with direct field access."""
        mapper = ResponseMapper()
        response_data = {"message": "Test", "status": "success"}
        mappings = {"output": "{{ message }}", "result": "{{ status }}"}

        result = mapper.map_response(response_data, mappings)

        assert result["output"] == "Test"
        assert result["result"] == "success"

    def test_map_response_with_empty_mappings(self):
        """Test that empty mappings returns original data."""
        mapper = ResponseMapper()
        response_data = {"message": "Hello", "value": 42}
        mappings = {}

        result = mapper.map_response(response_data, mappings)

        assert result == response_data

    def test_map_response_with_none_mappings(self):
        """Test that None mappings returns original data."""
        mapper = ResponseMapper()
        response_data = {"message": "Hello"}

        result = mapper.map_response(response_data, None)

        assert result == response_data

    def test_map_response_handles_template_errors_gracefully(self):
        """Test that mapping errors are handled gracefully."""
        mapper = ResponseMapper()
        response_data = {"message": "Hello"}
        mappings = {"output": "{{ undefined_function() }}"}

        result = mapper.map_response(response_data, mappings)

        # Should return None for fields that error
        assert result["output"] is None

    def test_map_response_with_complex_conditional(self):
        """Test complex conditional logic in Jinja2 template."""
        mapper = ResponseMapper()
        response_data = {
            "primary": "",
            "secondary": None,
            "tertiary": "Success!",
        }
        mappings = {
            "output": "{{ primary or secondary or tertiary or 'default' }}",
        }

        result = mapper.map_response(response_data, mappings)

        assert result["output"] == "Success!"

    def test_map_response_with_nested_jsonpath(self):
        """Test JSONPath with deeply nested structures."""
        mapper = ResponseMapper()
        response_data = {"data": {"response": {"messages": [{"text": "Hello"}, {"text": "World"}]}}}
        mappings = {"first_message": "$.data.response.messages[0].text"}

        result = mapper.map_response(response_data, mappings)

        assert result["first_message"] == "Hello"

    def test_map_response_empty_string_vs_none(self):
        """Test that empty string is handled correctly (truthy/falsy)."""
        mapper = ResponseMapper()
        response_data = {"empty": "", "none_val": None, "filled": "text"}
        mappings = {
            "test1": "{{ empty or 'fallback' }}",
            "test2": "{{ none_val or 'fallback' }}",
            "test3": "{{ filled or 'fallback' }}",
        }

        result = mapper.map_response(response_data, mappings)

        # Empty string is falsy in Jinja2
        assert result["test1"] == "fallback"
        assert result["test2"] == "fallback"
        assert result["test3"] == "text"

    def test_jsonpath_extract_with_invalid_path(self):
        """Test _jsonpath_extract with invalid JSONPath."""
        mapper = ResponseMapper()
        response_data = {"key": "value"}

        result = mapper._jsonpath_extract(response_data, "$.invalid[syntax")

        assert result is None
