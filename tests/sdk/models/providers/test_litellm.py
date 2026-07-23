from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import BaseModel

from rhesis.sdk.config import DEFAULT_LLM_TIMEOUT
from rhesis.sdk.models import LiteLLM
from rhesis.sdk.models.providers.litellm import LiteLLMEmbedder


class TestLiteLLM:
    def test_init_without_api_key(self):
        model_name = "provider/model"
        llm = LiteLLM(model_name)
        assert llm.model_name == model_name
        assert llm.api_key is None

    def test_init_with_api_key(self):
        api_key = "test_api_key"
        model_name = "provider/model"
        llm = LiteLLM(model_name, api_key=api_key)
        assert llm.model_name == model_name
        assert llm.api_key == api_key

    def test_init_without_name(self):
        with pytest.raises(ValueError):
            LiteLLM(None)

    def test_init_with_empty_string(self):
        with pytest.raises(ValueError):
            LiteLLM("")

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_generate_without_schema_without_api_key(self, mock_completion):
        """Test generate method without schema returns string response"""
        # Mock the completion response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello, this is a test response"
        mock_completion.return_value = mock_response

        model_name = "provider/model"
        llm = LiteLLM(model_name)
        prompt = "Hello, how are you?"

        result = llm.generate(prompt)

        assert result == "Hello, this is a test response"
        mock_completion.assert_called_once_with(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=None,
            api_key=None,
            api_base=None,
            api_version=None,
            extra_headers={"Connection": "close"},
            timeout=300,
        )

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_generate_without_schema_with_api_key(self, mock_completion):
        """Test generate method without schema returns string response"""
        # Mock the completion response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello, this is a test response"
        mock_completion.return_value = mock_response

        model_name = "provider/model"
        api_key = "test_api_key"
        llm = LiteLLM(model_name, api_key=api_key)
        prompt = "Hello, how are you?"

        result = llm.generate(prompt)

        assert result == "Hello, this is a test response"
        mock_completion.assert_called_once_with(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=None,
            api_key=api_key,
            api_base=None,
            api_version=None,
            extra_headers={"Connection": "close"},
            timeout=300,
        )

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_generate_with_schema_without_api_key(self, mock_completion):
        """Test generate method with schema returns validated dict response"""

        # Define a test schema
        class TestSchema(BaseModel):
            name: str
            age: int
            city: str

        # Mock the completion response with JSON string
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"name": "John", "age": 30, "city": "New York"}'
        mock_completion.return_value = mock_response

        model_name = "provider/model"
        llm = LiteLLM(model_name=model_name)
        prompt = "Generate a person's information"

        result = llm.generate(prompt, schema=TestSchema)

        assert isinstance(result, dict)
        assert result["name"] == "John"
        assert result["age"] == 30
        assert result["city"] == "New York"

        mock_completion.assert_called_once_with(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=TestSchema,
            api_key=None,
            api_base=None,
            api_version=None,
            extra_headers={"Connection": "close"},
            timeout=300,
        )

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_generate_with_schema_with_api_key(self, mock_completion):
        """Test generate method with schema returns validated dict response"""

        # Define a test schema
        class TestSchema(BaseModel):
            name: str
            age: int
            city: str

        # Mock the completion response with JSON string
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"name": "John", "age": 30, "city": "New York"}'
        mock_completion.return_value = mock_response

        model_name = "provider/model"
        api_key = "test_api_key"
        llm = LiteLLM(model_name=model_name, api_key=api_key)
        prompt = "Generate a person's information"

        result = llm.generate(prompt, schema=TestSchema)

        assert isinstance(result, dict)
        assert result["name"] == "John"
        assert result["age"] == 30
        assert result["city"] == "New York"

        mock_completion.assert_called_once_with(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=TestSchema,
            api_key=api_key,
            api_base=None,
            api_version=None,
            extra_headers={"Connection": "close"},
            timeout=300,
        )

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_generate_with_schema_invalid_response(self, mock_completion):
        """Test generate method with schema raises error for invalid response"""

        # Define a test schema
        class TestSchema(BaseModel):
            name: str
            age: int

        # Mock the completion response with invalid JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"name": "John"}'  # Missing age field
        mock_completion.return_value = mock_response

        model_name = "provider/model"
        llm = LiteLLM(model_name=model_name)
        prompt = "Generate a person's information"

        with pytest.raises(Exception):  # Should raise validation error
            llm.generate(prompt, schema=TestSchema)

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_generate_with_additional_kwargs(self, mock_completion):
        """Test generate method passes additional kwargs to completion"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response

        model_name = "provider/model"
        llm = LiteLLM(model_name=model_name)
        prompt = "Test prompt"

        llm.generate(prompt, temperature=0.7, max_tokens=100)

        mock_completion.assert_called_once_with(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=None,
            api_key=None,
            api_base=None,
            api_version=None,
            extra_headers={"Connection": "close"},
            timeout=300,
            temperature=0.7,
            max_tokens=100,
        )

    # Tests for generate_batch method

    @patch("rhesis.sdk.models.providers.litellm.batch_completion")
    def test_generate_batch_without_schema(self, mock_batch_completion):
        """Test generate_batch method without schema returns list of string responses"""
        # Mock the batch completion response
        mock_response1 = Mock()
        mock_response1.choices = [Mock()]
        mock_response1.choices[0].message.content = "Response 1"

        mock_response2 = Mock()
        mock_response2.choices = [Mock()]
        mock_response2.choices[0].message.content = "Response 2"

        mock_batch_completion.return_value = [mock_response1, mock_response2]

        model_name = "provider/model"
        llm = LiteLLM(model_name)
        prompts = ["Prompt 1", "Prompt 2"]

        result = llm.generate_batch(prompts)

        assert result == ["Response 1", "Response 2"]
        mock_batch_completion.assert_called_once_with(
            model=model_name,
            messages=[
                [{"role": "user", "content": "Prompt 1"}],
                [{"role": "user", "content": "Prompt 2"}],
            ],
            response_format=None,
            api_key=None,
            api_base=None,
            api_version=None,
            n=1,
            timeout=300,
        )

    @patch("rhesis.sdk.models.providers.litellm.batch_completion")
    def test_generate_batch_with_api_key(self, mock_batch_completion):
        """Test generate_batch method passes api_key correctly"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_batch_completion.return_value = [mock_response]

        model_name = "provider/model"
        api_key = "test_api_key"
        llm = LiteLLM(model_name, api_key=api_key)
        prompts = ["Test prompt"]

        result = llm.generate_batch(prompts)

        assert result == ["Response"]
        mock_batch_completion.assert_called_once_with(
            model=model_name,
            messages=[[{"role": "user", "content": "Test prompt"}]],
            response_format=None,
            api_key=api_key,
            api_base=None,
            api_version=None,
            n=1,
            timeout=300,
        )

    @patch("rhesis.sdk.models.providers.litellm.batch_completion")
    def test_generate_batch_with_system_prompt(self, mock_batch_completion):
        """Test generate_batch method with system prompt"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_batch_completion.return_value = [mock_response]

        model_name = "provider/model"
        llm = LiteLLM(model_name)
        prompts = ["User prompt"]
        system_prompt = "You are a helpful assistant."

        result = llm.generate_batch(prompts, system_prompt=system_prompt)

        assert result == ["Response"]
        mock_batch_completion.assert_called_once_with(
            model=model_name,
            messages=[
                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "User prompt"},
                ]
            ],
            response_format=None,
            api_key=None,
            api_base=None,
            api_version=None,
            n=1,
            timeout=300,
        )

    @patch("rhesis.sdk.models.providers.litellm.batch_completion")
    def test_generate_batch_with_schema(self, mock_batch_completion):
        """Test generate_batch method with schema returns list of validated dicts"""

        class TestSchema(BaseModel):
            name: str
            value: int

        mock_response1 = Mock()
        mock_response1.choices = [Mock()]
        mock_response1.choices[0].message.content = '{"name": "Alice", "value": 10}'

        mock_response2 = Mock()
        mock_response2.choices = [Mock()]
        mock_response2.choices[0].message.content = '{"name": "Bob", "value": 20}'

        mock_batch_completion.return_value = [mock_response1, mock_response2]

        model_name = "provider/model"
        llm = LiteLLM(model_name)
        prompts = ["Generate Alice", "Generate Bob"]

        result = llm.generate_batch(prompts, schema=TestSchema)

        assert len(result) == 2
        assert result[0] == {"name": "Alice", "value": 10}
        assert result[1] == {"name": "Bob", "value": 20}

        mock_batch_completion.assert_called_once_with(
            model=model_name,
            messages=[
                [{"role": "user", "content": "Generate Alice"}],
                [{"role": "user", "content": "Generate Bob"}],
            ],
            response_format=TestSchema,
            api_key=None,
            api_base=None,
            api_version=None,
            n=1,
            timeout=300,
        )

    @patch("rhesis.sdk.models.providers.litellm.batch_completion")
    def test_generate_batch_with_n_greater_than_one(self, mock_batch_completion):
        """Test generate_batch method with n > 1 returns multiple responses per prompt"""
        # Each response has multiple choices when n > 1
        mock_response = Mock()
        mock_choice1 = Mock()
        mock_choice1.message.content = "Response A"
        mock_choice2 = Mock()
        mock_choice2.message.content = "Response B"
        mock_response.choices = [mock_choice1, mock_choice2]

        mock_batch_completion.return_value = [mock_response]

        model_name = "provider/model"
        llm = LiteLLM(model_name)
        prompts = ["Test prompt"]

        result = llm.generate_batch(prompts, n=2)

        assert len(result) == 2
        assert result == ["Response A", "Response B"]
        mock_batch_completion.assert_called_once_with(
            model=model_name,
            messages=[[{"role": "user", "content": "Test prompt"}]],
            response_format=None,
            api_key=None,
            api_base=None,
            api_version=None,
            n=2,
            timeout=300,
        )

    @patch("rhesis.sdk.models.providers.litellm.batch_completion")
    def test_generate_batch_multiple_prompts_with_n(self, mock_batch_completion):
        """Test generate_batch with multiple prompts and n > 1"""
        mock_response1 = Mock()
        mock_choice1a = Mock()
        mock_choice1a.message.content = "Response 1a"
        mock_choice1b = Mock()
        mock_choice1b.message.content = "Response 1b"
        mock_response1.choices = [mock_choice1a, mock_choice1b]

        mock_response2 = Mock()
        mock_choice2a = Mock()
        mock_choice2a.message.content = "Response 2a"
        mock_choice2b = Mock()
        mock_choice2b.message.content = "Response 2b"
        mock_response2.choices = [mock_choice2a, mock_choice2b]

        mock_batch_completion.return_value = [mock_response1, mock_response2]

        model_name = "provider/model"
        llm = LiteLLM(model_name)
        prompts = ["Prompt 1", "Prompt 2"]

        result = llm.generate_batch(prompts, n=2)

        # Should have 2 prompts * 2 responses each = 4 total responses
        assert len(result) == 4
        assert result == ["Response 1a", "Response 1b", "Response 2a", "Response 2b"]

    @patch("rhesis.sdk.models.providers.litellm.batch_completion")
    def test_generate_batch_with_schema_invalid_response(self, mock_batch_completion):
        """Test generate_batch with schema raises error for invalid response"""

        class TestSchema(BaseModel):
            name: str
            value: int

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"name": "Alice"}'  # Missing value

        mock_batch_completion.return_value = [mock_response]

        model_name = "provider/model"
        llm = LiteLLM(model_name)
        prompts = ["Generate data"]

        with pytest.raises(Exception):  # Should raise validation error
            llm.generate_batch(prompts, schema=TestSchema)

    @patch("rhesis.sdk.models.providers.litellm.batch_completion")
    def test_generate_batch_with_additional_kwargs(self, mock_batch_completion):
        """Test generate_batch method passes additional kwargs to batch_completion"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_batch_completion.return_value = [mock_response]

        model_name = "provider/model"
        llm = LiteLLM(model_name)
        prompts = ["Test prompt"]

        llm.generate_batch(prompts, temperature=0.7, max_tokens=100)

        mock_batch_completion.assert_called_once_with(
            model=model_name,
            messages=[[{"role": "user", "content": "Test prompt"}]],
            response_format=None,
            api_key=None,
            api_base=None,
            api_version=None,
            n=1,
            timeout=300,
            temperature=0.7,
            max_tokens=100,
        )

    @patch("rhesis.sdk.models.providers.litellm.batch_completion")
    def test_generate_batch_empty_prompts(self, mock_batch_completion):
        """Test generate_batch with empty prompts list"""
        mock_batch_completion.return_value = []

        model_name = "provider/model"
        llm = LiteLLM(model_name)
        prompts = []

        result = llm.generate_batch(prompts)

        assert result == []
        mock_batch_completion.assert_called_once_with(
            model=model_name,
            messages=[],
            response_format=None,
            api_key=None,
            api_base=None,
            api_version=None,
            n=1,
            timeout=300,
        )

    # Tests for Connection: close injection in async paths

    @pytest.mark.asyncio
    @patch("rhesis.sdk.models.providers.litellm.acompletion", new_callable=AsyncMock)
    async def test_a_generate_injects_connection_close(self, mock_acompletion):
        """a_generate must always include Connection: close in extra_headers."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "ok"
        mock_acompletion.return_value = mock_response

        llm = LiteLLM("provider/model")
        await llm.a_generate(prompt="hello")

        _, kwargs = mock_acompletion.call_args
        assert kwargs.get("extra_headers", {}).get("Connection") == "close"

    @pytest.mark.asyncio
    @patch("rhesis.sdk.models.providers.litellm.acompletion", new_callable=AsyncMock)
    async def test_a_generate_preserves_caller_extra_headers(self, mock_acompletion):
        """Caller-supplied extra_headers survive alongside the injected Connection header."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "ok"
        mock_acompletion.return_value = mock_response

        llm = LiteLLM("provider/model")
        await llm.a_generate(prompt="hello", extra_headers={"X-Custom": "value"})

        _, kwargs = mock_acompletion.call_args
        headers = kwargs.get("extra_headers", {})
        assert headers.get("Connection") == "close"
        assert headers.get("X-Custom") == "value"

    @pytest.mark.asyncio
    @patch("rhesis.sdk.models.providers.litellm.acompletion", new_callable=AsyncMock)
    async def test_a_generate_stream_injects_connection_close(self, mock_acompletion):
        """_a_generate_stream (streaming path) must include Connection: close."""

        async def _fake_stream(*args, **kwargs):
            yield Mock(choices=[Mock(delta=Mock(content="tok"))])

        mock_acompletion.return_value = _fake_stream()

        llm = LiteLLM("provider/model")
        chunks = []
        async for chunk in await llm.a_generate(prompt="hello", stream=True):
            chunks.append(chunk)

        _, kwargs = mock_acompletion.call_args
        assert kwargs.get("extra_headers", {}).get("Connection") == "close"

    @pytest.mark.asyncio
    @patch("rhesis.sdk.models.providers.litellm.acompletion", new_callable=AsyncMock)
    async def test_a_generate_caller_connection_header_not_overwritten(self, mock_acompletion):
        """A caller-supplied Connection header value is kept unchanged (setdefault semantics)."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "ok"
        mock_acompletion.return_value = mock_response

        llm = LiteLLM("provider/model")
        await llm.a_generate(prompt="hello", extra_headers={"Connection": "keep-alive"})

        _, kwargs = mock_acompletion.call_args
        assert kwargs.get("extra_headers", {}).get("Connection") == "keep-alive"

    @patch("rhesis.sdk.models.providers.litellm.batch_completion")
    def test_generate_batch_with_schema_and_system_prompt(self, mock_batch_completion):
        """Test generate_batch with both schema and system prompt"""

        class TestSchema(BaseModel):
            result: str

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"result": "success"}'
        mock_batch_completion.return_value = [mock_response]

        model_name = "provider/model"
        llm = LiteLLM(model_name)
        prompts = ["Do something"]
        system_prompt = "You are an assistant."

        result = llm.generate_batch(prompts, system_prompt=system_prompt, schema=TestSchema)

        assert result == [{"result": "success"}]
        mock_batch_completion.assert_called_once_with(
            model=model_name,
            messages=[
                [
                    {"role": "system", "content": "You are an assistant."},
                    {"role": "user", "content": "Do something"},
                ]
            ],
            response_format=TestSchema,
            api_key=None,
            api_base=None,
            api_version=None,
            n=1,
            timeout=300,
        )


class TestLiteLLMTimeout:
    """A hung upstream call must not block a worker thread forever: every LiteLLM call
    carries a request timeout (default DEFAULT_LLM_TIMEOUT), overridable per instance
    and per call."""

    def test_default_timeout(self):
        assert LiteLLM("provider/model").timeout == DEFAULT_LLM_TIMEOUT

    def test_explicit_instance_timeout(self):
        assert LiteLLM("provider/model", timeout=5).timeout == 5

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_default_timeout_passed_to_acompletion(self, mock_completion):
        mock_completion.return_value = Mock(choices=[Mock(message=Mock(content="ok"))])
        LiteLLM("provider/model").generate("hi")
        assert mock_completion.call_args.kwargs["timeout"] == DEFAULT_LLM_TIMEOUT

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_instance_timeout_passed_to_acompletion(self, mock_completion):
        mock_completion.return_value = Mock(choices=[Mock(message=Mock(content="ok"))])
        LiteLLM("provider/model", timeout=7).generate("hi")
        assert mock_completion.call_args.kwargs["timeout"] == 7

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_per_call_timeout_overrides_instance(self, mock_completion):
        mock_completion.return_value = Mock(choices=[Mock(message=Mock(content="ok"))])
        LiteLLM("provider/model", timeout=7).generate("hi", timeout=1)
        assert mock_completion.call_args.kwargs["timeout"] == 1

    @patch("rhesis.sdk.models.providers.litellm.batch_completion")
    def test_timeout_passed_to_batch_completion(self, mock_batch):
        mock_batch.return_value = [Mock(choices=[Mock(message=Mock(content="ok"))])]
        LiteLLM("provider/model", timeout=8).generate_batch(["hi"])
        assert mock_batch.call_args.kwargs["timeout"] == 8

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_subclass_enforces_default_timeout(self, mock_completion):
        """Thin LiteLLM subclasses (OpenAI, Gemini, …) inherit the default timeout on
        every call, so a hung upstream call can never block indefinitely."""
        from rhesis.sdk.models.providers.openai import OpenAILLM

        mock_completion.return_value = Mock(choices=[Mock(message=Mock(content="ok"))])
        OpenAILLM("gpt-4o", api_key="x").generate("hi")
        assert mock_completion.call_args.kwargs["timeout"] == DEFAULT_LLM_TIMEOUT

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_subclass_per_call_timeout_override(self, mock_completion):
        """A per-call timeout overrides the default on any provider, including subclasses."""
        from rhesis.sdk.models.providers.openai import OpenAILLM

        mock_completion.return_value = Mock(choices=[Mock(message=Mock(content="ok"))])
        OpenAILLM("gpt-4o", api_key="x").generate("hi", timeout=2)
        assert mock_completion.call_args.kwargs["timeout"] == 2


class TestLiteLLMEmbedderTimeout:
    def test_default_timeout(self):
        assert LiteLLMEmbedder("provider/embed").timeout == DEFAULT_LLM_TIMEOUT

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_timeout_passed_to_embedding(self, mock_embedding):
        mock_embedding.return_value = {"data": [{"embedding": [0.1, 0.2]}]}
        LiteLLMEmbedder("provider/embed", timeout=9).generate_batch(["hi"])
        assert mock_embedding.call_args.kwargs["timeout"] == 9

    @pytest.mark.asyncio
    @patch("rhesis.sdk.models.providers.litellm.aembedding", new_callable=AsyncMock)
    async def test_timeout_passed_to_aembedding(self, mock_aembedding):
        mock_aembedding.return_value = {"data": [{"embedding": [0.1, 0.2]}]}
        await LiteLLMEmbedder("provider/embed", timeout=4).a_generate("hi")
        assert mock_aembedding.call_args.kwargs["timeout"] == 4
