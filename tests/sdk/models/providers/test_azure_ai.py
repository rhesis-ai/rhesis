import os
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from rhesis.sdk.models.providers.azure_ai import (
    DEFAULT_MODEL_NAME,
    AzureAILLM,
)


def test_azure_ai_defaults():
    assert AzureAILLM.PROVIDER == "azure_ai"
    assert DEFAULT_MODEL_NAME is not None
    assert DEFAULT_MODEL_NAME != ""


class TestAzureAILLMInit:
    def test_init_with_explicit_credentials(self):
        llm = AzureAILLM(
            api_key="test_key",
            api_base="https://my-endpoint.inference.ai.azure.com/",
        )
        assert llm.api_key == "test_key"
        assert llm.api_base == "https://my-endpoint.inference.ai.azure.com/"
        assert llm.model_name == f"azure_ai/{DEFAULT_MODEL_NAME}"

    def test_init_with_env_vars(self):
        env = {
            "AZURE_AI_API_KEY": "env_key",
            "AZURE_AI_API_BASE": "https://env-endpoint.inference.ai.azure.com/",
        }
        with patch.dict(os.environ, env):
            llm = AzureAILLM()
            assert llm.api_key == "env_key"
            assert llm.api_base == "https://env-endpoint.inference.ai.azure.com/"

    def test_init_explicit_overrides_env(self):
        env = {
            "AZURE_AI_API_KEY": "env_key",
            "AZURE_AI_API_BASE": "https://env.inference.ai.azure.com/",
        }
        with patch.dict(os.environ, env):
            llm = AzureAILLM(
                api_key="explicit_key",
                api_base="https://explicit.inference.ai.azure.com/",
            )
            assert llm.api_key == "explicit_key"
            assert llm.api_base == "https://explicit.inference.ai.azure.com/"

    def test_init_without_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="AZURE_AI_API_KEY is not set"):
                AzureAILLM(api_base="https://endpoint.inference.ai.azure.com/")

    def test_init_without_api_base_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="AZURE_AI_API_BASE is not set"):
                AzureAILLM(api_key="test_key")

    def test_init_with_custom_model(self):
        llm = AzureAILLM(
            model_name="mistral-large-latest",
            api_key="test_key",
            api_base="https://endpoint.inference.ai.azure.com/",
        )
        assert llm.model_name == "azure_ai/mistral-large-latest"

    def test_provider_attribute(self):
        assert AzureAILLM.PROVIDER == "azure_ai"


class TestAzureAILLMGenerate:
    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_without_schema(self, mock_completion):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello from Azure AI!"
        mock_completion.return_value = mock_response

        llm = AzureAILLM(
            api_key="test_key",
            api_base="https://endpoint.inference.ai.azure.com/",
        )
        result = llm.generate("Hello")

        assert result == "Hello from Azure AI!"
        mock_completion.assert_called_once_with(
            model=f"azure_ai/{DEFAULT_MODEL_NAME}",
            messages=[{"role": "user", "content": "Hello"}],
            response_format=None,
            api_key="test_key",
            api_base="https://endpoint.inference.ai.azure.com/",
            api_version=None,
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_system_prompt(self, mock_completion):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response

        llm = AzureAILLM(
            api_key="test_key",
            api_base="https://endpoint.inference.ai.azure.com/",
        )
        llm.generate("Test", system_prompt="You are helpful")

        mock_completion.assert_called_once_with(
            model=f"azure_ai/{DEFAULT_MODEL_NAME}",
            messages=[
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Test"},
            ],
            response_format=None,
            api_key="test_key",
            api_base="https://endpoint.inference.ai.azure.com/",
            api_version=None,
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_schema(self, mock_completion):
        class PersonInfo(BaseModel):
            name: str
            age: int

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"name": "Alice", "age": 30}'
        mock_completion.return_value = mock_response

        llm = AzureAILLM(
            api_key="test_key",
            api_base="https://endpoint.inference.ai.azure.com/",
        )
        result = llm.generate("Tell me about Alice", schema=PersonInfo)

        assert isinstance(result, dict)
        assert result == {"name": "Alice", "age": 30}

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_schema_invalid_response(self, mock_completion):
        class StrictSchema(BaseModel):
            name: str
            age: int

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"name": "Alice"}'
        mock_completion.return_value = mock_response

        llm = AzureAILLM(
            api_key="test_key",
            api_base="https://endpoint.inference.ai.azure.com/",
        )
        with pytest.raises(Exception):
            llm.generate("test", schema=StrictSchema)

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_custom_model(self, mock_completion):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_completion.return_value = mock_response

        llm = AzureAILLM(
            model_name="mistral-large-latest",
            api_key="test_key",
            api_base="https://endpoint.inference.ai.azure.com/",
        )
        llm.generate("Test")

        mock_completion.assert_called_once_with(
            model="azure_ai/mistral-large-latest",
            messages=[{"role": "user", "content": "Test"}],
            response_format=None,
            api_key="test_key",
            api_base="https://endpoint.inference.ai.azure.com/",
            api_version=None,
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_additional_kwargs(self, mock_completion):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_completion.return_value = mock_response

        llm = AzureAILLM(
            api_key="test_key",
            api_base="https://endpoint.inference.ai.azure.com/",
        )
        llm.generate("Test", temperature=0.7, max_tokens=100)

        mock_completion.assert_called_once_with(
            model=f"azure_ai/{DEFAULT_MODEL_NAME}",
            messages=[{"role": "user", "content": "Test"}],
            response_format=None,
            api_key="test_key",
            api_base="https://endpoint.inference.ai.azure.com/",
            api_version=None,
            temperature=0.7,
            max_tokens=100,
        )
