"""Tests for provider-agnostic provider identification utilities."""

from rhesis.sdk.telemetry.utils.provider_detection import (
    identify_provider,
    identify_provider_from_class_name,
    identify_provider_from_model_name,
)


class TestIdentifyProviderFromModelName:
    """Tests for identify_provider_from_model_name function."""

    def test_openai_models(self):
        """Should identify OpenAI models."""
        assert identify_provider_from_model_name("gpt-4") == "openai"
        assert identify_provider_from_model_name("gpt-4-turbo") == "openai"
        assert identify_provider_from_model_name("gpt-3.5-turbo") == "openai"
        assert identify_provider_from_model_name("text-davinci-003") == "openai"

    def test_anthropic_models(self):
        """Should identify Anthropic models."""
        assert identify_provider_from_model_name("claude-3-opus-20240229") == "anthropic"
        assert identify_provider_from_model_name("claude-3-sonnet") == "anthropic"
        assert identify_provider_from_model_name("claude-2.1") == "anthropic"

    def test_google_models(self):
        """Should identify Google models."""
        assert identify_provider_from_model_name("gemini-1.5-pro") == "google"
        assert identify_provider_from_model_name("gemini-pro") == "google"
        assert identify_provider_from_model_name("palm-2") == "google"
        assert identify_provider_from_model_name("bard") == "google"

    def test_cohere_models(self):
        """Should identify Cohere models."""
        assert identify_provider_from_model_name("command-r-plus") == "cohere"
        assert identify_provider_from_model_name("command-light") == "cohere"

    def test_meta_models(self):
        """Should identify Meta/Llama models."""
        assert identify_provider_from_model_name("llama-3-70b") == "meta"
        assert identify_provider_from_model_name("meta-llama-2") == "meta"

    def test_mistral_models(self):
        """Should identify Mistral models."""
        assert identify_provider_from_model_name("mistral-large") == "mistralai"
        assert identify_provider_from_model_name("mixtral-8x7b") == "mistralai"

    def test_aws_models(self):
        """Should identify AWS Bedrock models."""
        assert identify_provider_from_model_name("amazon.titan-text-express-v1") == "aws"
        assert identify_provider_from_model_name("bedrock-claude") == "aws"

    def test_azure_models(self):
        """Should identify Azure models."""
        assert identify_provider_from_model_name("azure-gpt-4") == "azure"

    def test_case_insensitive(self):
        """Should be case insensitive."""
        assert identify_provider_from_model_name("GPT-4") == "openai"
        assert identify_provider_from_model_name("Claude-3-Opus") == "anthropic"
        assert identify_provider_from_model_name("GEMINI-PRO") == "google"

    def test_unknown_model(self):
        """Should return None for unknown models."""
        assert identify_provider_from_model_name("unknown-model-xyz") is None
        assert identify_provider_from_model_name("custom-model") is None

    def test_empty_model(self):
        """Should return None for empty model name."""
        assert identify_provider_from_model_name("") is None
        assert identify_provider_from_model_name(None) is None


class TestIdentifyProviderFromClassName:
    """Tests for identify_provider_from_class_name function."""

    def test_langchain_class_names(self):
        """Should identify LangChain class names."""
        assert identify_provider_from_class_name("ChatOpenAI") == "openai"
        assert identify_provider_from_class_name("ChatAnthropic") == "anthropic"
        assert identify_provider_from_class_name("ChatGoogleGenerativeAI") == "google"
        assert identify_provider_from_class_name("ChatCohere") == "cohere"

    def test_direct_api_class_names(self):
        """Should identify direct API client class names."""
        assert identify_provider_from_class_name("OpenAI") == "openai"
        assert identify_provider_from_class_name("Anthropic") == "anthropic"
        assert identify_provider_from_class_name("GoogleGenerativeAI") == "google"

    def test_huggingface_class_names(self):
        """Should identify HuggingFace class names."""
        assert identify_provider_from_class_name("HuggingFaceHub") == "huggingface"
        assert identify_provider_from_class_name("HuggingFaceEndpoint") == "huggingface"

    def test_bedrock_class_names(self):
        """Should identify AWS Bedrock class names."""
        assert identify_provider_from_class_name("BedrockLLM") == "aws"
        assert identify_provider_from_class_name("ChatBedrock") == "aws"

    def test_case_insensitive(self):
        """Should be case insensitive."""
        assert identify_provider_from_class_name("chatopenai") == "openai"
        assert identify_provider_from_class_name("CHATANTHROPIC") == "anthropic"

    def test_unknown_class(self):
        """Should return None for unknown class names."""
        assert identify_provider_from_class_name("CustomLLM") is None
        assert identify_provider_from_class_name("MyModel") is None

    def test_empty_class(self):
        """Should return None for empty class name."""
        assert identify_provider_from_class_name("") is None
        assert identify_provider_from_class_name(None) is None


class TestIdentifyProvider:
    """Tests for identify_provider function (main entry point)."""

    def test_explicit_provider_kwarg(self):
        """Should use explicit provider kwarg when provided."""
        result = identify_provider(
            model_name="unknown-model", class_name="UnknownClass", provider="custom"
        )
        assert result == "custom"

    def test_model_name_priority(self):
        """Should prioritize model name matching."""
        result = identify_provider(model_name="gpt-4", class_name="CustomClass")
        assert result == "openai"

    def test_class_name_fallback(self):
        """Should fall back to class name when model name fails."""
        result = identify_provider(model_name="custom-model", class_name="ChatAnthropic")
        assert result == "anthropic"

    def test_kwargs_model_parameter(self):
        """Should check kwargs for model parameter."""
        result = identify_provider(class_name="UnknownClass", model="gemini-pro")
        assert result == "google"

    def test_alternative_model_keys(self):
        """Should check alternative model keys in kwargs."""
        assert identify_provider(model_id="gpt-4") == "openai"
        assert identify_provider(engine="claude-3") == "anthropic"

    def test_returns_unknown_when_all_fail(self):
        """Should return 'unknown' when all strategies fail."""
        result = identify_provider(
            model_name="custom-model", class_name="CustomClass", other_param="value"
        )
        assert result == "unknown"

    def test_no_parameters(self):
        """Should return 'unknown' when no parameters provided."""
        result = identify_provider()
        assert result == "unknown"

    def test_combined_hints(self):
        """Should work with combined hints from different sources."""
        # Model name takes priority
        result = identify_provider(model_name="gpt-4", model="claude-3")
        assert result == "openai"

        # Class name used when model name doesn't match
        result = identify_provider(model_name="custom", class_name="ChatAnthropic")
        assert result == "anthropic"
