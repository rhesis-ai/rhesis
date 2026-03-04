import os
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from rhesis.sdk.models.providers.azure_openai import (
    DEFAULT_MODEL_NAME,
    AzureOpenAILLM,
)


def test_azure_openai_defaults():
    assert AzureOpenAILLM.PROVIDER == "azure"
    assert DEFAULT_MODEL_NAME is not None
    assert DEFAULT_MODEL_NAME != ""


class TestAzureOpenAILLMInit:
    def test_init_with_explicit_credentials(self):
        llm = AzureOpenAILLM(
            api_key="test_key",
            api_base="https://my-resource.openai.azure.com/",
        )
        assert llm.api_key == "test_key"
        assert llm.api_base == "https://my-resource.openai.azure.com/"
        assert llm.model_name == f"azure/{DEFAULT_MODEL_NAME}"
        assert llm.api_version is None

    def test_init_with_api_version(self):
        llm = AzureOpenAILLM(
            api_key="test_key",
            api_base="https://my-resource.openai.azure.com/",
            api_version="2024-08-01-preview",
        )
        assert llm.api_version == "2024-08-01-preview"

    def test_init_with_env_vars(self):
        env = {
            "AZURE_API_KEY": "env_key",
            "AZURE_API_BASE": "https://env-resource.openai.azure.com/",
            "AZURE_API_VERSION": "2024-08-01-preview",
        }
        with patch.dict(os.environ, env):
            llm = AzureOpenAILLM()
            assert llm.api_key == "env_key"
            assert llm.api_base == "https://env-resource.openai.azure.com/"
            assert llm.api_version == "2024-08-01-preview"

    def test_init_explicit_overrides_env(self):
        env = {
            "AZURE_API_KEY": "env_key",
            "AZURE_API_BASE": "https://env.openai.azure.com/",
            "AZURE_API_VERSION": "2023-05-15",
        }
        with patch.dict(os.environ, env):
            llm = AzureOpenAILLM(
                api_key="explicit_key",
                api_base="https://explicit.openai.azure.com/",
                api_version="2024-08-01-preview",
            )
            assert llm.api_key == "explicit_key"
            assert llm.api_base == "https://explicit.openai.azure.com/"
            assert llm.api_version == "2024-08-01-preview"

    def test_init_without_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="AZURE_API_KEY is not set"):
                AzureOpenAILLM(api_base="https://resource.openai.azure.com/")

    def test_init_without_api_base_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="AZURE_API_BASE is not set"):
                AzureOpenAILLM(api_key="test_key")

    def test_init_without_api_version_is_ok(self):
        with patch.dict(os.environ, {}, clear=True):
            llm = AzureOpenAILLM(
                api_key="test_key",
                api_base="https://resource.openai.azure.com/",
            )
            assert llm.api_version is None

    def test_init_with_custom_model(self):
        llm = AzureOpenAILLM(
            model_name="my-gpt4-deployment",
            api_key="test_key",
            api_base="https://resource.openai.azure.com/",
        )
        assert llm.model_name == "azure/my-gpt4-deployment"

    def test_provider_attribute(self):
        assert AzureOpenAILLM.PROVIDER == "azure"


class TestAzureOpenAILLMGenerate:
    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_without_schema(self, mock_completion):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello from Azure!"
        mock_completion.return_value = mock_response

        llm = AzureOpenAILLM(
            api_key="test_key",
            api_base="https://resource.openai.azure.com/",
        )
        result = llm.generate("Hello")

        assert result == "Hello from Azure!"
        mock_completion.assert_called_once_with(
            model=f"azure/{DEFAULT_MODEL_NAME}",
            messages=[{"role": "user", "content": "Hello"}],
            response_format=None,
            api_key="test_key",
            api_base="https://resource.openai.azure.com/",
            api_version=None,
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_system_prompt(self, mock_completion):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response

        llm = AzureOpenAILLM(
            api_key="test_key",
            api_base="https://resource.openai.azure.com/",
        )
        llm.generate("Test", system_prompt="You are helpful")

        mock_completion.assert_called_once_with(
            model=f"azure/{DEFAULT_MODEL_NAME}",
            messages=[
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Test"},
            ],
            response_format=None,
            api_key="test_key",
            api_base="https://resource.openai.azure.com/",
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

        llm = AzureOpenAILLM(
            api_key="test_key",
            api_base="https://resource.openai.azure.com/",
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

        llm = AzureOpenAILLM(
            api_key="test_key",
            api_base="https://resource.openai.azure.com/",
        )
        with pytest.raises(Exception):
            llm.generate("test", schema=StrictSchema)

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_custom_deployment(self, mock_completion):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_completion.return_value = mock_response

        llm = AzureOpenAILLM(
            model_name="my-gpt4-deployment",
            api_key="test_key",
            api_base="https://resource.openai.azure.com/",
        )
        llm.generate("Test")

        mock_completion.assert_called_once_with(
            model="azure/my-gpt4-deployment",
            messages=[{"role": "user", "content": "Test"}],
            response_format=None,
            api_key="test_key",
            api_base="https://resource.openai.azure.com/",
            api_version=None,
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_additional_kwargs(self, mock_completion):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_completion.return_value = mock_response

        llm = AzureOpenAILLM(
            api_key="test_key",
            api_base="https://resource.openai.azure.com/",
        )
        llm.generate("Test", temperature=0.7, max_tokens=100)

        mock_completion.assert_called_once_with(
            model=f"azure/{DEFAULT_MODEL_NAME}",
            messages=[{"role": "user", "content": "Test"}],
            response_format=None,
            api_key="test_key",
            api_base="https://resource.openai.azure.com/",
            api_version=None,
            temperature=0.7,
            max_tokens=100,
        )
