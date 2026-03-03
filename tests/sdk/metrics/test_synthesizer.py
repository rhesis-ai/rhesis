"""Tests for MetricSynthesizer."""

import os
from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.metrics.synthesizer import GeneratedMetric, MetricSynthesizer
from rhesis.sdk.models.base import BaseLLM

os.environ["RHESIS_API_KEY"] = "test"


# ── Initialization ────────────────────────────────────────────────


def test_init_with_model_instance():
    """MetricSynthesizer accepts a BaseLLM instance."""
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    assert synth.model is mock_model


@patch("rhesis.sdk.metrics.synthesizer.get_model")
def test_init_with_none_model(mock_get_model):
    """model=None falls back to get_model(None)."""
    mock_model = Mock(spec=BaseLLM)
    mock_get_model.return_value = mock_model

    synth = MetricSynthesizer(model=None)

    mock_get_model.assert_called_once_with(None)
    assert synth.model is mock_model


@patch("rhesis.sdk.metrics.synthesizer.get_model")
def test_init_with_string_model(mock_get_model):
    """A string model name is resolved via get_model()."""
    mock_model = Mock(spec=BaseLLM)
    mock_get_model.return_value = mock_model

    synth = MetricSynthesizer(model="vertex_ai/gemini-2.0-flash")

    mock_get_model.assert_called_once_with("vertex_ai/gemini-2.0-flash")
    assert synth.model is mock_model


# ── Template ──────────────────────────────────────────────────────


def test_prompt_template_loads():
    """The Jinja template loads without errors."""
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    assert synth.prompt_template is not None


def test_prompt_template_renders_user_prompt():
    """The template includes the user-supplied prompt text."""
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    rendered = synth.prompt_template.render(prompt="Check for hallucinations")
    assert "Check for hallucinations" in rendered


def test_prompt_template_contains_naming_convention():
    """The template instructs the LLM to use Title Case names."""
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    rendered = synth.prompt_template.render(prompt="test")
    assert "Title Case" in rendered


# ── generate() ────────────────────────────────────────────────────

_NUMERIC_RESPONSE = {
    "name": "Factual Accuracy",
    "description": "Measures factual accuracy of the response.",
    "evaluation_prompt": "Evaluate {{response}} for factual accuracy.",
    "evaluation_steps": "1. Read the response.\n2. Assign a score.",
    "score_type": "numeric",
    "min_score": 1.0,
    "max_score": 5.0,
    "threshold": 3.0,
    "threshold_operator": ">=",
    "categories": None,
    "passing_categories": None,
    "metric_scope": ["Single-Turn", "Multi-Turn"],
}

_CATEGORICAL_RESPONSE = {
    "name": "Tone Appropriateness",
    "description": "Checks if the response tone is appropriate.",
    "evaluation_prompt": "Classify the tone of {{response}}.",
    "evaluation_steps": None,
    "score_type": "categorical",
    "min_score": None,
    "max_score": None,
    "threshold": None,
    "threshold_operator": None,
    "categories": ["appropriate", "inappropriate"],
    "passing_categories": ["appropriate"],
    "metric_scope": ["Single-Turn"],
}


def test_generate_returns_dict_from_dict_response():
    """When model.generate returns a dict, generate() returns it directly."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = dict(_NUMERIC_RESPONSE)

    synth = MetricSynthesizer(model=mock_model)
    result = synth.generate("Measure factual accuracy on a 1-5 scale")

    assert isinstance(result, dict)
    assert result["name"] == "Factual Accuracy"
    assert result["score_type"] == "numeric"
    assert result["threshold"] == 3.0


def test_generate_returns_dict_from_pydantic_response():
    """When model.generate returns a Pydantic model, generate() returns its dict."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = GeneratedMetric(**_CATEGORICAL_RESPONSE)

    synth = MetricSynthesizer(model=mock_model)
    result = synth.generate("Check if response tone is appropriate")

    assert isinstance(result, dict)
    assert result["name"] == "Tone Appropriateness"
    assert result["score_type"] == "categorical"
    assert result["categories"] == ["appropriate", "inappropriate"]
    assert result["passing_categories"] == ["appropriate"]


def test_generate_raises_on_error_response():
    """When the LLM returns an error dict, generate() raises RuntimeError."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {"error": "Rate limit exceeded"}

    synth = MetricSynthesizer(model=mock_model)

    with pytest.raises(RuntimeError, match="Rate limit exceeded"):
        synth.generate("anything")


def test_generate_passes_schema_to_model():
    """generate() passes GeneratedMetric as the schema to model.generate()."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = dict(_NUMERIC_RESPONSE)

    synth = MetricSynthesizer(model=mock_model)
    synth.generate("test prompt")

    call_kwargs = mock_model.generate.call_args
    assert call_kwargs.kwargs.get("schema") is GeneratedMetric


def test_generate_prompt_includes_user_text():
    """The rendered prompt sent to the model includes the user's text."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = dict(_NUMERIC_RESPONSE)

    synth = MetricSynthesizer(model=mock_model)
    synth.generate("measure hallucination rate")

    prompt_arg = mock_model.generate.call_args.args[0]
    assert "measure hallucination rate" in prompt_arg


def test_generate_numeric_metric_fields():
    """A numeric metric response includes all required numeric fields."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = dict(_NUMERIC_RESPONSE)

    synth = MetricSynthesizer(model=mock_model)
    result = synth.generate("numeric metric")

    assert result["min_score"] == 1.0
    assert result["max_score"] == 5.0
    assert result["threshold"] == 3.0
    assert result["threshold_operator"] == ">="
    assert result["categories"] is None


def test_generate_categorical_metric_fields():
    """A categorical metric response includes categories and passing_categories."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = dict(_CATEGORICAL_RESPONSE)

    synth = MetricSynthesizer(model=mock_model)
    result = synth.generate("categorical metric")

    assert result["categories"] == ["appropriate", "inappropriate"]
    assert result["passing_categories"] == ["appropriate"]
    assert result["min_score"] is None
    assert result["threshold"] is None


# ── Multi-turn awareness in generation template ──────────────────


def test_generate_template_contains_multi_turn_guidance():
    """The generation template includes multi-turn evaluation guidance."""
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    rendered = synth.prompt_template.render(prompt="test")
    assert "Goal achievement" in rendered
    assert "Turn progression" in rendered
    assert "Single-Turn" in rendered
    assert "Multi-Turn" in rendered


def test_generate_template_contains_single_turn_guidance():
    """The generation template includes single-turn evaluation guidance."""
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    rendered = synth.prompt_template.render(prompt="test")
    assert "Accuracy" in rendered
    assert "Relevance" in rendered
    assert "Safety" in rendered


# ── Improve template ─────────────────────────────────────────────


def test_improve_template_loads():
    """The improve Jinja template loads without errors."""
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    assert synth.improve_template is not None


def test_improve_template_renders_existing_metric():
    """The improve template includes existing metric fields."""
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    rendered = synth.improve_template.render(
        existing_metric=_NUMERIC_RESPONSE,
        prompt="make the threshold stricter",
    )
    assert "Factual Accuracy" in rendered
    assert "make the threshold stricter" in rendered


# ── improve() ────────────────────────────────────────────────────


def test_improve_returns_dict():
    """improve() returns a dict of updated metric fields."""
    mock_model = Mock(spec=BaseLLM)
    improved = dict(_NUMERIC_RESPONSE)
    improved["threshold"] = 4.0
    mock_model.generate.return_value = improved

    synth = MetricSynthesizer(model=mock_model)
    result = synth.improve(_NUMERIC_RESPONSE, "raise the threshold")

    assert isinstance(result, dict)
    assert result["threshold"] == 4.0


def test_improve_passes_schema_to_model():
    """improve() passes GeneratedMetric as the schema."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = dict(_NUMERIC_RESPONSE)

    synth = MetricSynthesizer(model=mock_model)
    synth.improve(_NUMERIC_RESPONSE, "any edit")

    call_kwargs = mock_model.generate.call_args
    assert call_kwargs.kwargs.get("schema") is GeneratedMetric


def test_improve_prompt_contains_existing_name_and_edit():
    """The rendered improve prompt contains the metric name and edit text."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = dict(_NUMERIC_RESPONSE)

    synth = MetricSynthesizer(model=mock_model)
    synth.improve(_NUMERIC_RESPONSE, "add multi-turn support")

    prompt_arg = mock_model.generate.call_args.args[0]
    assert "Factual Accuracy" in prompt_arg
    assert "add multi-turn support" in prompt_arg


def test_improve_raises_on_error_response():
    """improve() raises RuntimeError when the LLM returns an error."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {"error": "timeout"}

    synth = MetricSynthesizer(model=mock_model)

    with pytest.raises(RuntimeError, match="timeout"):
        synth.improve(_NUMERIC_RESPONSE, "anything")
