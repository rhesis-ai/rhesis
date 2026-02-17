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


# Batch generation tests (structure of _generate_batch output)
def test_generate_batch_returns_nested_structure():
    """Test that _generate_batch returns list of dicts with nested prompt structure.

    The LLM is given a flat schema (prompt_content, prompt_expected_response, etc.);
    the synthesizer repacks the response into the nested structure (prompt.content, etc.).
    """
    mock_model = Mock(spec=BaseLLM)
    # Simulate LLM returning flat structure (FlatTests schema)
    mock_model.generate.return_value = {
        "tests": [
            {
                "prompt_content": "User query A",
                "prompt_expected_response": "Expected A",
                "prompt_language_code": "en",
                "behavior": "behavior one",
                "category": "category one",
                "topic": "topic one",
            },
            {
                "prompt_content": "User query B",
                "prompt_expected_response": "Expected B",
                "prompt_language_code": "pl",
                "behavior": "behavior two",
                "category": "category two",
                "topic": "topic two",
            },
        ]
    }

    synthesizer = PromptSynthesizer(prompt="Generate tests", model=mock_model)
    result = synthesizer._generate_batch(2, generation_prompt="Generate tests")

    assert len(result) == 2
    # Nested prompt structure preserved
    assert result[0]["prompt"]["content"] == "User query A"
    assert result[0]["prompt"]["expected_response"] == "Expected A"
    assert result[0]["prompt"]["language_code"] == "en"
    assert result[0]["behavior"] == "behavior one"
    assert result[0]["category"] == "category one"
    assert result[0]["topic"] == "topic one"
    assert result[0]["test_type"] == "Single-Turn"
    assert result[0]["metadata"]["generated_by"] == "PromptSynthesizer"

    assert result[1]["prompt"]["content"] == "User query B"
    assert result[1]["prompt"]["expected_response"] == "Expected B"
    assert result[1]["prompt"]["language_code"] == "pl"
    assert result[1]["behavior"] == "behavior two"
    assert result[1]["category"] == "category two"
    assert result[1]["topic"] == "topic two"
    assert result[1]["test_type"] == "Single-Turn"
    assert result[1]["metadata"]["generated_by"] == "PromptSynthesizer"


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
            "behavior": "test behavior 1",
            "category": "test category 1",
            "topic": "test topic 1",
            "metadata": {"generated_by": "PromptSynthesizer"},
        },
        {
            "prompt": {
                "content": "Test prompt 2",
                "expected_response": "Response 2",
                "language_code": "en",
            },
            "behavior": "test behavior 2",
            "category": "test category 2",
            "topic": "test topic 2",
            "metadata": {"generated_by": "PromptSynthesizer"},
        },
        {
            "prompt": {
                "content": "Test prompt 3",
                "expected_response": "Response 3",
                "language_code": "en",
            },
            "behavior": "test behavior 3",
            "category": "test category 3",
            "topic": "test topic 3",
            "metadata": {"generated_by": "PromptSynthesizer"},
        },
    ]

    synthesizer = PromptSynthesizer(prompt="Generate tests")
    result = synthesizer._generate_without_sources(num_tests=3)

    assert len(result) == 3
    assert mock_generate_batch.called

    item0 = result[0]
    assert item0["prompt"]["content"] == "Test prompt 1"
    assert item0["prompt"]["expected_response"] == "Response 1"
    assert item0["prompt"]["language_code"] == "en"
    assert item0["behavior"] == "test behavior 1"
    assert item0["category"] == "test category 1"
    assert item0["topic"] == "test topic 1"
    assert item0["metadata"] == {"generated_by": "PromptSynthesizer"}

    item1 = result[1]
    assert item1["prompt"]["content"] == "Test prompt 2"
    assert item1["prompt"]["expected_response"] == "Response 2"
    assert item1["prompt"]["language_code"] == "en"
    assert item1["behavior"] == "test behavior 2"
    assert item1["category"] == "test category 2"
    assert item1["topic"] == "test topic 2"
    assert item1["metadata"] == {"generated_by": "PromptSynthesizer"}

    item2 = result[2]
    assert item2["prompt"]["content"] == "Test prompt 3"
    assert item2["prompt"]["expected_response"] == "Response 3"
    assert item2["prompt"]["language_code"] == "en"
    assert item2["behavior"] == "test behavior 3"
    assert item2["category"] == "test category 3"
    assert item2["topic"] == "test topic 3"
    assert item2["metadata"] == {"generated_by": "PromptSynthesizer"}


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
