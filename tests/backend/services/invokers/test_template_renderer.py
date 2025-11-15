"""Tests for template rendering functionality."""

import uuid

from rhesis.backend.app.services.invokers.templating.renderer import TemplateRenderer


class TestTemplateRenderer:
    """Test TemplateRenderer class functionality."""

    def test_render_string_template_with_simple_variable(self):
        """Test rendering a simple string template."""
        renderer = TemplateRenderer()
        template = "Hello {{ name }}!"
        input_data = {"name": "World"}

        result = renderer.render(template, input_data)

        assert result == "Hello World!"

    def test_render_dict_template(self):
        """Test rendering a dictionary template."""
        renderer = TemplateRenderer()
        template = {"message": "{{ input }}", "user": "{{ username }}"}
        input_data = {"input": "test message", "username": "testuser"}

        result = renderer.render(template, input_data)

        assert result == {"message": "test message", "user": "testuser"}

    def test_render_json_string_template(self):
        """Test rendering a JSON string template."""
        renderer = TemplateRenderer()
        template = '{"query": "{{ input }}", "token": "{{ auth_token }}"}'
        input_data = {"input": "search query", "auth_token": "abc123"}

        result = renderer.render(template, input_data)

        assert isinstance(result, dict)
        assert result["query"] == "search query"
        assert result["token"] == "abc123"

    def test_render_with_tojson_filter(self):
        """Test rendering with tojson filter for proper JSON encoding."""
        renderer = TemplateRenderer()
        template = '{"value": {{ value | tojson }}}'
        input_data = {"value": None}

        result = renderer.render(template, input_data)

        assert result["value"] is None

    def test_auto_generate_session_id_when_missing(self):
        """Test automatic session_id generation when referenced but not provided."""
        renderer = TemplateRenderer()
        template = '{"session_id": "{{ session_id }}", "query": "{{ input }}"}'
        input_data = {"input": "test"}

        result = renderer.render(template, input_data)

        assert isinstance(result, dict)
        assert "session_id" in result
        # Verify it's a valid UUID
        uuid.UUID(result["session_id"])
        assert result["query"] == "test"

    def test_no_auto_generate_session_id_when_provided(self):
        """Test that session_id is not auto-generated when already provided."""
        renderer = TemplateRenderer()
        template = '{"session_id": "{{ session_id }}", "query": "{{ input }}"}'
        provided_session_id = "my-custom-session"
        input_data = {"input": "test", "session_id": provided_session_id}

        result = renderer.render(template, input_data)

        assert result["session_id"] == provided_session_id

    def test_render_with_complex_nested_structure(self):
        """Test rendering with nested dict structures."""
        renderer = TemplateRenderer()
        template = {
            "user": {"name": "{{ username }}", "role": "{{ role }}"},
            "query": "{{ input }}",
        }
        input_data = {"username": "alice", "role": "admin", "input": "search"}

        result = renderer.render(template, input_data)

        # Only top-level string values are rendered in dict templates
        assert result["user"] == {"name": "{{ username }}", "role": "{{ role }}"}
        assert result["query"] == "search"

    def test_render_non_json_string_returns_string(self):
        """Test that non-JSON strings are returned as-is."""
        renderer = TemplateRenderer()
        template = "Simple text with {{ variable }}"
        input_data = {"variable": "value"}

        result = renderer.render(template, input_data)

        assert result == "Simple text with value"

    def test_render_passthrough_for_non_template_types(self):
        """Test that non-template types are passed through unchanged."""
        renderer = TemplateRenderer()

        # Test with integer
        assert renderer.render(42, {}) == 42

        # Test with list
        assert renderer.render([1, 2, 3], {}) == [1, 2, 3]

        # Test with None
        assert renderer.render(None, {}) is None
