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
def test_generate_without_sources_small_batch():
    """Test generation without sources for small number of tests."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate_batch.return_value = [
        {
            "tests": [
                {
                    "prompt_content": f"Test prompt {i + 1}",
                    "prompt_expected_response": f"Response {i + 1}",
                    "prompt_language_code": "en",
                    "behavior": f"test behavior {i + 1}",
                    "category": f"test category {i + 1}",
                    "topic": f"test topic {i + 1}",
                }
                for i in range(3)
            ]
        }
    ]

    synthesizer = PromptSynthesizer(prompt="Generate tests", model=mock_model)
    result = synthesizer._generate_without_sources(num_tests=3)

    assert len(result) == 3
    assert mock_model.generate_batch.call_count == 1

    item0 = result[0]
    assert item0["prompt"]["content"] == "Test prompt 1"
    assert item0["prompt"]["expected_response"] == "Response 1"
    assert item0["prompt"]["language_code"] == "en"
    assert item0["behavior"] == "test behavior 1"
    assert item0["category"] == "test category 1"
    assert item0["topic"] == "test topic 1"
    assert item0["metadata"]["generated_by"] == "PromptSynthesizer"


def test_generate_without_sources_large_batch():
    """Test that large requests use model.generate_batch for parallel execution."""
    mock_model = Mock(spec=BaseLLM)
    batch_response = {
        "tests": [
            {
                "prompt_content": f"Test {i}",
                "prompt_expected_response": f"Response {i}",
                "prompt_language_code": "en",
                "behavior": "behavior",
                "category": "category",
                "topic": "topic",
            }
            for i in range(20)
        ]
    }
    mock_model.generate_batch.return_value = [batch_response, batch_response]

    synthesizer = PromptSynthesizer(prompt="Generate tests", model=mock_model, batch_size=20)
    result = synthesizer._generate_without_sources(num_tests=40)

    assert mock_model.generate_batch.call_count == 1
    assert len(result) == 40


def test_generate_without_sources_large_batch_with_remainder():
    """Test large request where num_tests is not evenly divisible by batch_size."""
    mock_model = Mock(spec=BaseLLM)
    full_batch = {
        "tests": [
            {
                "prompt_content": f"Test {i}",
                "prompt_expected_response": f"Response {i}",
                "prompt_language_code": "en",
                "behavior": "behavior",
                "category": "category",
                "topic": "topic",
            }
            for i in range(5)
        ]
    }
    remainder_batch = {
        "tests": [
            {
                "prompt_content": f"Test r{i}",
                "prompt_expected_response": f"Response r{i}",
                "prompt_language_code": "en",
                "behavior": "behavior",
                "category": "category",
                "topic": "topic",
            }
            for i in range(3)
        ]
    }
    mock_model.generate_batch.return_value = [
        full_batch,
        full_batch,
        remainder_batch,
    ]

    synthesizer = PromptSynthesizer(
        prompt="Generate tests", model=mock_model, batch_size=5
    )
    result = synthesizer._generate_without_sources(num_tests=13)

    assert mock_model.generate_batch.call_count == 1
    assert len(result) == 13


def test_large_batch_partial_failure_falls_back():
    """Test that partial failures in generate_batch trigger sequential fallback."""
    mock_model = Mock(spec=BaseLLM)
    flat_tests_5 = {
        "tests": [
            {
                "prompt_content": f"Test {i}",
                "prompt_expected_response": f"Response {i}",
                "prompt_language_code": "en",
                "behavior": "behavior",
                "category": "category",
                "topic": "topic",
            }
            for i in range(5)
        ]
    }
    mock_model.generate_batch.return_value = [
        flat_tests_5,
        {"error": "LLM failed"},
    ]
    mock_model.generate.return_value = flat_tests_5

    synthesizer = PromptSynthesizer(prompt="Generate tests", model=mock_model, batch_size=5)
    result = synthesizer._generate_without_sources(num_tests=10)

    assert mock_model.generate_batch.call_count == 1
    assert mock_model.generate.call_count == 1
    assert len(result) == 10


def test_large_batch_exception_falls_back():
    """Test that generate_batch exception triggers full sequential fallback."""
    mock_model = Mock(spec=BaseLLM)
    flat_tests_5 = {
        "tests": [
            {
                "prompt_content": f"Test {i}",
                "prompt_expected_response": f"Response {i}",
                "prompt_language_code": "en",
                "behavior": "behavior",
                "category": "category",
                "topic": "topic",
            }
            for i in range(5)
        ]
    }
    mock_model.generate_batch.side_effect = RuntimeError("batch failed")
    mock_model.generate.return_value = flat_tests_5

    synthesizer = PromptSynthesizer(prompt="Generate tests", model=mock_model, batch_size=5)
    result = synthesizer._generate_without_sources(num_tests=10)

    assert mock_model.generate_batch.call_count == 1
    assert mock_model.generate.call_count == 2
    assert len(result) == 10


@patch.object(PromptSynthesizer, "_generate_parallel_batches", return_value=[])
@patch.object(PromptSynthesizer, "_generate_batch")
def test_batch_size_reduction_on_failure(mock_generate_batch, _mock_parallel):
    """Test that batch size is halved when a batch fails and retries succeed."""
    small_batch = [
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
        for i in range(5)
    ]
    mock_generate_batch.side_effect = [
        [],  # batch_size=10 fails
        small_batch,  # retry with batch_size=5, succeeds
        small_batch,  # remaining 5, succeeds
    ]

    synthesizer = PromptSynthesizer(prompt="Generate tests", batch_size=10)
    result = synthesizer._generate_without_sources(num_tests=10)

    assert len(result) == 10
    assert mock_generate_batch.call_count == 3
    assert mock_generate_batch.call_args_list[0][0][0] == 10
    assert mock_generate_batch.call_args_list[1][0][0] == 5
    assert mock_generate_batch.call_args_list[2][0][0] == 5


@patch.object(PromptSynthesizer, "_generate_parallel_batches", return_value=[])
@patch.object(PromptSynthesizer, "_generate_batch")
def test_max_consecutive_failures_raises(mock_generate_batch, _mock_parallel):
    """Test that generation stops after max consecutive failures."""
    mock_generate_batch.return_value = []

    synthesizer = PromptSynthesizer(prompt="Generate tests", batch_size=10)

    with pytest.raises(ValueError, match="Failed to generate any valid test cases"):
        synthesizer._generate_without_sources(num_tests=10)

    # 10 -> 5 -> 2 (3 failures = _MAX_CONSECUTIVE_FAILURES)
    assert mock_generate_batch.call_count == 3


@patch.object(PromptSynthesizer, "_generate_parallel_batches", return_value=[])
@patch.object(PromptSynthesizer, "_generate_batch")
def test_batch_size_reduction_on_exception(mock_generate_batch, _mock_parallel):
    """Test that exceptions in _generate_batch trigger batch size reduction."""
    small_batch = [
        {
            "prompt": {
                "content": "Test 0",
                "expected_response": "Response 0",
                "language_code": "en",
            },
            "behavior": "behavior",
            "category": "category",
            "topic": "topic",
            "metadata": {"generated_by": "PromptSynthesizer"},
        }
    ]
    mock_generate_batch.side_effect = [
        RuntimeError("LLM timeout"),
        small_batch,
    ]

    synthesizer = PromptSynthesizer(prompt="Generate tests", batch_size=2)
    result = synthesizer._generate_without_sources(num_tests=1)

    assert len(result) == 1
    assert mock_generate_batch.call_count == 2
    assert mock_generate_batch.call_args_list[0][0][0] == 1
    assert mock_generate_batch.call_args_list[1][0][0] == 1


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
