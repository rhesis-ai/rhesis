"""Tests for template rendering functionality."""

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

    def test_omit_session_id_when_missing(self):
        """Test that session_id is omitted from template when not provided."""
        renderer = TemplateRenderer()
        template = '{"session_id": "{{ session_id }}", "query": "{{ input }}"}'
        input_data = {"input": "test"}

        result = renderer.render(template, input_data)

        assert isinstance(result, dict)
        assert "session_id" not in result  # Should be omitted, not auto-generated
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

        # Now nested structures are properly rendered
        assert result["user"] == {"name": "alice", "role": "admin"}
        assert result["query"] == "search"

    def test_render_nested_arrays(self):
        """Test rendering with nested arrays containing template variables."""
        renderer = TemplateRenderer()
        template = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "{{ input }}"},
            ],
            "model": "{{ model_name }}",
        }
        input_data = {"input": "Hello world", "model_name": "gpt-4"}

        result = renderer.render(template, input_data)

        assert result["messages"][0] == {
            "role": "system",
            "content": "You are a helpful assistant.",
        }
        assert result["messages"][1] == {"role": "user", "content": "Hello world"}
        assert result["model"] == "gpt-4"

    def test_render_deeply_nested_structure(self):
        """Test rendering with deeply nested structures."""
        renderer = TemplateRenderer()
        template = {
            "config": {
                "api": {
                    "endpoints": [
                        {"url": "{{ base_url }}/users", "method": "GET"},
                        {"url": "{{ base_url }}/posts", "method": "POST"},
                    ]
                },
                "auth": {"token": "{{ auth_token }}"},
            }
        }
        input_data = {"base_url": "https://api.example.com", "auth_token": "secret123"}

        result = renderer.render(template, input_data)

        assert result["config"]["api"]["endpoints"][0]["url"] == "https://api.example.com/users"
        assert result["config"]["api"]["endpoints"][1]["url"] == "https://api.example.com/posts"
        assert result["config"]["auth"]["token"] == "secret123"

    def test_render_mixed_types_in_nested_structure(self):
        """Test rendering with mixed data types in nested structures."""
        renderer = TemplateRenderer()
        template = {
            "settings": {
                "enabled": True,
                "count": 42,
                "name": "{{ setting_name }}",
                "values": [1, "{{ dynamic_value }}", 3],
            }
        }
        input_data = {"setting_name": "my_setting", "dynamic_value": "dynamic"}

        result = renderer.render(template, input_data)

        assert result["settings"]["enabled"] is True
        assert result["settings"]["count"] == 42
        assert result["settings"]["name"] == "my_setting"
        assert result["settings"]["values"] == [1, "dynamic", 3]

    def test_render_user_example_request_mapping(self):
        """Test rendering with the user's specific request mapping example."""
        renderer = TemplateRenderer()
        template = {
            "model": "cortecs/Llama-3.3-70B-Instruct-FP8-Dynamic",
            "messages": [
                {"role": "system", "content": "Du bist ein hilfreicher Assistent."},
                {"role": "user", "content": "{{ input }}"},
            ],
            "max_completion_tokens": 400,
            "temperature": 0.2,
        }
        input_data = {"input": "Wie geht es dir?"}

        result = renderer.render(template, input_data)

        assert result["model"] == "cortecs/Llama-3.3-70B-Instruct-FP8-Dynamic"
        assert result["messages"][0] == {
            "role": "system",
            "content": "Du bist ein hilfreicher Assistent.",
        }
        assert result["messages"][1] == {"role": "user", "content": "Wie geht es dir?"}
        assert result["max_completion_tokens"] == 400
        assert result["temperature"] == 0.2

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


class TestMessagesListPassthrough:
    """Test {{ messages }} rendering for stateless multi-turn endpoints.

    Stateless endpoints use a request_mapping like:
        {"messages": "{{ messages }}", "model": "gpt-4"}
    where `messages` is an OpenAI-style list of dicts passed through as-is.
    """

    def test_messages_list_preserved_as_list(self):
        """{{ messages }} with a list value preserves the list type."""
        renderer = TemplateRenderer()
        template = {"messages": "{{ messages }}", "model": "gpt-4"}
        messages = [
            {"role": "user", "content": "Hello"},
        ]
        input_data = {"messages": messages}

        result = renderer.render(template, input_data)

        assert isinstance(result["messages"], list)
        assert result["messages"] == messages

    def test_messages_multi_turn_passthrough(self):
        """Full multi-turn messages array is preserved through rendering."""
        renderer = TemplateRenderer()
        template = {"messages": "{{ messages }}", "model": "gpt-4"}
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help?"},
            {"role": "user", "content": "What is 2+2?"},
        ]
        input_data = {"messages": messages}

        result = renderer.render(template, input_data)

        assert result["messages"] == messages
        assert len(result["messages"]) == 4
        assert result["messages"][0]["role"] == "system"
        assert result["messages"][3]["content"] == "What is 2+2?"

    def test_messages_passthrough_with_other_fields(self):
        """Messages passthrough works alongside other template variables."""
        renderer = TemplateRenderer()
        template = {
            "messages": "{{ messages }}",
            "model": "{{ model_name }}",
            "temperature": 0.7,
        }
        messages = [
            {"role": "user", "content": "Hello"},
        ]
        input_data = {"messages": messages, "model_name": "gpt-4o"}

        result = renderer.render(template, input_data)

        assert result["messages"] == messages
        assert result["model"] == "gpt-4o"
        assert result["temperature"] == 0.7

    def test_messages_passthrough_with_system_prompt_field(self):
        """Stateless request mapping with system_prompt renders correctly."""
        renderer = TemplateRenderer()
        template = {
            "messages": "{{ messages }}",
            "model": "gpt-4",
            "system_prompt": "You are a helpful assistant.",
        }
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        input_data = {"messages": messages}

        result = renderer.render(template, input_data)

        assert result["messages"] == messages
        assert result["system_prompt"] == "You are a helpful assistant."

    def test_messages_empty_list_passthrough(self):
        """An empty messages list is preserved as an empty list."""
        renderer = TemplateRenderer()
        template = {"messages": "{{ messages }}"}
        input_data = {"messages": []}

        result = renderer.render(template, input_data)

        assert result["messages"] == []

    def test_messages_single_system_prompt_only(self):
        """A messages array with only a system prompt is preserved."""
        renderer = TemplateRenderer()
        template = {"messages": "{{ messages }}"}
        messages = [{"role": "system", "content": "Be concise."}]
        input_data = {"messages": messages}

        result = renderer.render(template, input_data)

        assert result["messages"] == messages

    def test_stateless_request_mapping_end_to_end(self):
        """Full stateless endpoint request mapping renders correctly.

        Simulates what EndpointService produces for a single-turn stateless call.
        """
        renderer = TemplateRenderer()
        template = {
            "messages": "{{ messages }}",
            "model": "cortecs/Llama-3.3-70B-Instruct-FP8-Dynamic",
            "max_completion_tokens": 400,
            "temperature": 0.2,
            "system_prompt": "Du bist ein hilfreicher Assistent.",
        }
        messages = [
            {
                "role": "system",
                "content": "Du bist ein hilfreicher Assistent.",
            },
            {"role": "user", "content": "Wie geht es dir?"},
        ]
        input_data = {"messages": messages}

        result = renderer.render(template, input_data)

        assert result["messages"] == messages
        assert result["model"] == "cortecs/Llama-3.3-70B-Instruct-FP8-Dynamic"
        assert result["max_completion_tokens"] == 400
        assert result["temperature"] == 0.2
        # system_prompt is still present after rendering;
        # BaseEndpointInvoker._strip_meta_keys removes it before sending
        assert result["system_prompt"] == "Du bist ein hilfreicher Assistent."

    def test_messages_dict_contents_preserve_structure(self):
        """Each message dict within the list preserves its exact structure."""
        renderer = TemplateRenderer()
        template = {"messages": "{{ messages }}"}
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        input_data = {"messages": messages}

        result = renderer.render(template, input_data)

        for i, msg in enumerate(result["messages"]):
            assert set(msg.keys()) == {"role", "content"}
            assert msg["role"] == messages[i]["role"]
            assert msg["content"] == messages[i]["content"]
