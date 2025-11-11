import os
from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.extractor import SourceSpecification, SourceType
from rhesis.sdk.synthesizers.prompt_synthesizer import PromptSynthesizer

os.environ["RHESIS_API_KEY"] = "test"


# Initialization tests
def test_init_with_minimal_args():
    """Test initialization with only required arguments."""
    synthesizer = PromptSynthesizer(prompt="Generate test cases")

    assert synthesizer.prompt == "Generate test cases"
    assert synthesizer.batch_size == 20
    assert synthesizer.sources is None
    assert synthesizer.model is not None


def test_init_with_model_instance():
    """Test initialization with BaseLLM instance."""
    mock_model = Mock(spec=BaseLLM)
    synthesizer = PromptSynthesizer(prompt="Test prompt", model=mock_model)

    assert synthesizer.model == mock_model


def test_init_with_sources():
    """Test initialization with sources."""
    sources = [
        SourceSpecification(
            type=SourceType.TEXT,
            name="test_source",
            description="A test source",
            metadata={"content": "Test content"},
        )
    ]
    synthesizer = PromptSynthesizer(prompt="Test prompt", sources=sources)

    assert synthesizer.sources == sources


# Template context tests
def test_get_template_context_basic():
    """Test template context with no additional kwargs."""
    synthesizer = PromptSynthesizer(prompt="Generate tests for API")

    context = synthesizer._get_template_context()

    assert context == {"generation_prompt": "Generate tests for API"}


def test_get_template_context_with_kwargs():
    """Test template context with additional kwargs."""
    synthesizer = PromptSynthesizer(prompt="Generate tests")

    context = synthesizer._get_template_context(num_tests=10, custom_param="value")

    assert context["generation_prompt"] == "Generate tests"
    assert context["num_tests"] == 10
    assert context["custom_param"] == "value"


# Metadata tests
def test_get_synthesizer_name():
    """Test that synthesizer returns correct class name."""
    synthesizer = PromptSynthesizer(prompt="Test")

    name = synthesizer._get_synthesizer_name()

    assert name == "PromptSynthesizer"


# Generation tests
@patch.object(PromptSynthesizer, "_generate_batch")
def test_generate_without_sources_small_batch(mock_generate_batch):
    """Test generation without sources for small number of tests."""
    mock_generate_batch.return_value = [
        {
            "prompt": {
                "content": "Test prompt 1",
                "expected_response": "Response 1",
                "language_code": "en",
            },
            "behavior": "test behavior",
            "category": "test category",
            "topic": "test topic",
            "metadata": {"generated_by": "PromptSynthesizer"},
        }
    ]

    synthesizer = PromptSynthesizer(prompt="Generate tests")
    result = synthesizer._generate_without_sources(num_tests=1)

    assert len(result) == 1
    assert mock_generate_batch.called
    assert result[0]["prompt"]["content"] == "Test prompt 1"


@patch.object(PromptSynthesizer, "_generate_batch")
def test_generate_without_sources_large_batch(mock_generate_batch):
    """Test generation without sources for large number of tests (chunking)."""
    # Mock returns 20 tests per call
    mock_generate_batch.return_value = [
        {
            "prompt": {
                "content": f"Test {i}",
                "expected_response": f"Response {i}",
                "language_code": "en",
            },
            "behavior": "behavior",
            "category": "category",
            "topic": "topic",
            "metadata": {"generated_by": "PromptSynthesizer"},
        }
        for i in range(20)
    ]

    synthesizer = PromptSynthesizer(prompt="Generate tests", batch_size=20)
    result = synthesizer._generate_without_sources(num_tests=40)

    # Should be called twice (40 tests / 20 batch size)
    assert mock_generate_batch.call_count == 2
    assert len(result) == 40


def test_generate_without_sources_invalid_num_tests():
    """Test that invalid num_tests raises TypeError."""
    synthesizer = PromptSynthesizer(prompt="Test")

    with pytest.raises(TypeError, match="num_tests must be an integer"):
        synthesizer._generate_without_sources(num_tests="5")  # type: ignore


@patch("rhesis.sdk.synthesizers.base.get_model")
def test_model_initialization_with_none(mock_get_model):
    """Test that model is initialized with None (default model)."""
    mock_model = Mock(spec=BaseLLM)
    mock_get_model.return_value = mock_model

    synthesizer = PromptSynthesizer(prompt="Test")

    mock_get_model.assert_called_once_with(None)
    assert synthesizer.model == mock_model


def test_prompt_template():
    synthesizer = PromptSynthesizer(prompt="Test prompt")
    context = synthesizer._get_template_context()
    context = {**context, "num_tests": 1500100900}
    prompt = synthesizer.prompt_template.render(**context)
    assert "Test prompt" in prompt
    assert "1500100900" in prompt
