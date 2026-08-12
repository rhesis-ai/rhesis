"""Tests for MetricSynthesizer."""

import os
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

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
    "reasoning": "Cite the specific claims that drove the score.",
    "explanation": "A failing score means the endpoint states unsupported facts.",
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
    "evaluation_steps": "1. Read the response.\n2. Pick the closest category.",
    "reasoning": "Quote the phrasing that determined the category.",
    "explanation": "An inappropriate result means the tone breaches brand guidance.",
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


# ── Descriptive-field completeness ───────────────────────────────

_RICH_FIELDS = ("description", "evaluation_steps", "reasoning", "explanation")


def test_generated_metric_requires_descriptive_fields():
    """These are required so a generated metric is never threadbare."""
    for field in _RICH_FIELDS:
        assert field in GeneratedMetric.model_fields, f"{field} missing from schema"
        assert GeneratedMetric.model_fields[field].is_required(), (
            f"{field} is optional — the LLM will skip it and the metric lands with an empty field"
        )


def test_generated_metric_descriptive_fields_guide_the_llm():
    for field in _RICH_FIELDS:
        text = GeneratedMetric.model_fields[field].description or ""
        assert len(text.strip()) > 40, f"{field} needs a real description, got {text!r}"


def test_omitting_a_descriptive_field_is_a_validation_error():
    for field in _RICH_FIELDS:
        payload = {k: v for k, v in _NUMERIC_RESPONSE.items() if k != field}
        with pytest.raises(ValidationError):
            GeneratedMetric(**payload)


def test_generate_template_asks_for_descriptive_fields():
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    rendered = synth.prompt_template.render(prompt="test")
    for field in _RICH_FIELDS:
        assert field in rendered, f"generation template never mentions {field}"


def test_generate_template_asks_for_the_stored_step_format():
    """A plain '1. 2. 3.' list lands as one step in the UI, so the format is spelled out."""
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    rendered = synth.prompt_template.render(prompt="test")
    assert "Step 1:" in rendered
    assert "Step 2:" in rendered
    assert "\n---\n" in rendered


def test_step_format_reaches_the_llm_through_the_schema_too():
    """The template is only half the signal — the field description carries it as well."""
    steps = GeneratedMetric.model_fields["evaluation_steps"].description or ""
    assert "Step N:" in steps
    assert "---" in steps


def test_improve_template_asks_for_the_stored_step_format():
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    rendered = synth.improve_template.render(
        existing_metric=_NUMERIC_RESPONSE,
        prompt="make the threshold stricter",
    )
    assert "Step N:" in rendered
    assert "---" in rendered


def test_improve_template_shows_all_descriptive_fields():
    """Rule 2 says preserve unmentioned fields — impossible if unshown."""
    mock_model = Mock(spec=BaseLLM)
    synth = MetricSynthesizer(model=mock_model)
    rendered = synth.improve_template.render(
        existing_metric=_NUMERIC_RESPONSE,
        prompt="make the threshold stricter",
    )
    for field in _RICH_FIELDS:
        assert f"**{field}**" in rendered, f"improve template hides {field}"
    # The actual current values must be visible, not just the labels.
    assert _NUMERIC_RESPONSE["reasoning"] in rendered
    assert _NUMERIC_RESPONSE["explanation"] in rendered


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
