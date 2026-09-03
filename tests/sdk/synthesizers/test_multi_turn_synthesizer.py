import os
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.multi_turn.base import (
    FlatTests,
    GenerationConfig,
    MultiTurnSynthesizer,
)

os.environ["RHESIS_API_KEY"] = "test"


# --- Initialization tests ---


def test_init_with_minimal_args():
    """Test initialization with only required arguments."""
    mock_model = Mock(spec=BaseLLM)
    config = GenerationConfig(generation_prompt="Generate multi-turn tests")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model)

    assert synthesizer.config == config
    assert synthesizer.batch_size == 10
    assert synthesizer.model is mock_model


def test_init_with_custom_batch_size():
    """Test initialization with a custom batch_size."""
    mock_model = Mock(spec=BaseLLM)
    config = GenerationConfig(generation_prompt="Generate tests")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=25)

    assert synthesizer.batch_size == 25


@patch("rhesis.sdk.synthesizers.multi_turn.base.get_model")
def test_init_with_none_model(mock_get_model):
    """Test that model=None triggers get_model(None)."""
    mock_model = Mock(spec=BaseLLM)
    mock_get_model.return_value = mock_model
    config = GenerationConfig(generation_prompt="Test")

    synthesizer = MultiTurnSynthesizer(config=config, model=None)

    mock_get_model.assert_called_once_with(None)
    assert synthesizer.model is mock_model


@patch("rhesis.sdk.synthesizers.multi_turn.base.get_model")
def test_init_with_string_model(mock_get_model):
    """Test that a string model name triggers get_model(name)."""
    mock_model = Mock(spec=BaseLLM)
    mock_get_model.return_value = mock_model
    config = GenerationConfig(generation_prompt="Test")

    synthesizer = MultiTurnSynthesizer(config=config, model="gpt-4")

    mock_get_model.assert_called_once_with("gpt-4")
    assert synthesizer.model is mock_model


def test_init_with_model_instance():
    """Test initialization with a BaseLLM instance."""
    mock_model = Mock(spec=BaseLLM)
    config = GenerationConfig(generation_prompt="Test")

    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model)

    assert synthesizer.model is mock_model


def test_generation_config_with_all_fields():
    """Test GenerationConfig accepts all optional fields."""
    config = GenerationConfig(
        generation_prompt="Generate tests",
        requirements=["Compliance", "Reliability"],
        categories=["Harmful", "Harmless"],
        topics=["healthcare", "finance"],
        additional_context="Extra context here",
    )

    assert config.generation_prompt == "Generate tests"
    assert config.requirements == ["Compliance", "Reliability"]
    assert config.categories == ["Harmful", "Harmless"]
    assert config.topics == ["healthcare", "finance"]
    assert config.additional_context == "Extra context here"


# --- Template loading tests ---


def test_load_prompt_template():
    """Test that prompt template is loaded successfully."""
    mock_model = Mock(spec=BaseLLM)
    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model)

    template = synthesizer.load_prompt_template("base.jinja")

    assert template is not None


def test_prompt_template_renders_config():
    """Test that the template renders with config values."""
    mock_model = Mock(spec=BaseLLM)
    config = GenerationConfig(generation_prompt="Test multi-turn scenario")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model)

    template = synthesizer.load_prompt_template("base.jinja")
    rendered = template.render(
        {
            "num_tests": 42,
            **config.model_dump(),
        }
    )

    assert "Test multi-turn scenario" in rendered
    assert "42" in rendered


def test_prompt_template_includes_turn_configuration():
    """Test that the template includes turn configuration guidance."""
    mock_model = Mock(spec=BaseLLM)
    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model)

    template = synthesizer.load_prompt_template("base.jinja")
    rendered = template.render(
        {
            "num_tests": 5,
            **config.model_dump(),
        }
    )

    assert "min_turns" in rendered
    assert "max_turns" in rendered
    assert "Turn Configuration" in rendered


# --- _generate_batch tests ---


def test_generate_batch_returns_nested_structure():
    """Test that _generate_batch returns list of dicts with nested structure.

    The LLM is given a flat schema (test_configuration_goal, etc.);
    the synthesizer repacks the response into the nested structure.
    """
    mock_model = Mock(spec=BaseLLM)
    # Simulate LLM returning flat structure (FlatTests schema)
    mock_model.generate.return_value = {
        "tests": [
            {
                "test_configuration_goal": "Test goal A",
                "test_configuration_instructions": "Step 1, Step 2",
                "test_configuration_restrictions": "No PII",
                "test_configuration_scenario": "Customer support",
                "test_configuration_min_turns": 3,
                "test_configuration_max_turns": 7,
                "requirement": "Compliance",
                "category": "Harmful",
                "topic": "data privacy",
            },
            {
                "test_configuration_goal": "Test goal B",
                "test_configuration_instructions": "",
                "test_configuration_restrictions": "",
                "test_configuration_scenario": "",
                "test_configuration_min_turns": 5,
                "test_configuration_max_turns": 12,
                "requirement": "Reliability",
                "category": "Harmless",
                "topic": "product info",
            },
        ]
    }

    config = GenerationConfig(generation_prompt="Generate tests")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=2)
    result = synthesizer._generate_batch()

    assert len(result) == 2

    # First test — nested structure preserved
    assert result[0]["test_configuration"]["goal"] == "Test goal A"
    assert result[0]["test_configuration"]["instructions"] == "Step 1, Step 2"
    assert result[0]["test_configuration"]["restrictions"] == "No PII"
    assert result[0]["test_configuration"]["scenario"] == "Customer support"
    assert result[0]["test_configuration"]["min_turns"] == 3
    assert result[0]["test_configuration"]["max_turns"] == 7
    assert result[0]["requirement"] == "Compliance"
    assert result[0]["category"] == "Harmful"
    assert result[0]["topic"] == "data privacy"
    assert result[0]["test_type"] == "Multi-Turn"

    # Second test
    assert result[1]["test_configuration"]["goal"] == "Test goal B"
    assert result[1]["test_configuration"]["instructions"] == ""
    assert result[1]["test_configuration"]["restrictions"] == ""
    assert result[1]["test_configuration"]["scenario"] == ""
    assert result[1]["test_configuration"]["min_turns"] == 5
    assert result[1]["test_configuration"]["max_turns"] == 12
    assert result[1]["requirement"] == "Reliability"
    assert result[1]["category"] == "Harmless"
    assert result[1]["topic"] == "product info"
    assert result[1]["test_type"] == "Multi-Turn"


def test_generate_batch_sets_multi_turn_type():
    """Test that _generate_batch always sets test_type to Multi-Turn."""
    mock_model = Mock(spec=BaseLLM)
    # Simulate LLM returning flat structure
    mock_model.generate.return_value = {
        "tests": [
            {
                "test_configuration_goal": "Goal",
                "test_configuration_instructions": "",
                "test_configuration_restrictions": "",
                "test_configuration_scenario": "",
                "test_configuration_min_turns": 3,
                "test_configuration_max_turns": 7,
                "requirement": "Robustness",
                "category": "Harmful",
                "topic": "security",
            },
        ]
    }

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=1)
    result = synthesizer._generate_batch()

    assert result[0]["test_type"] == "Multi-Turn"


# --- _flat_test_to_nested tests ---


def test_flat_test_to_nested_includes_turn_config():
    """Test that _flat_test_to_nested repacks min_turns and max_turns."""
    mock_model = Mock(spec=BaseLLM)
    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model)

    flat = {
        "test_configuration_goal": "Goal",
        "test_configuration_instructions": "Steps",
        "test_configuration_restrictions": "None",
        "test_configuration_scenario": "Context",
        "test_configuration_min_turns": 4,
        "test_configuration_max_turns": 15,
        "requirement": "Reliability",
        "category": "Harmless",
        "topic": "general",
    }
    result = synthesizer._flat_test_to_nested(flat)

    assert result["test_configuration"]["min_turns"] == 4
    assert result["test_configuration"]["max_turns"] == 15
    assert result["test_configuration"]["goal"] == "Goal"


def test_flat_test_to_nested_omits_none_turn_config():
    """Test that _flat_test_to_nested omits turn fields when None."""
    mock_model = Mock(spec=BaseLLM)
    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model)

    flat = {
        "test_configuration_goal": "Goal",
        "test_configuration_instructions": "",
        "test_configuration_restrictions": "",
        "test_configuration_scenario": "",
        "requirement": "Compliance",
        "category": "Harmful",
        "topic": "security",
    }
    result = synthesizer._flat_test_to_nested(flat)

    assert "min_turns" not in result["test_configuration"]
    assert "max_turns" not in result["test_configuration"]


def test_generate_batch_passes_flat_schema_to_model():
    """Test that _generate_batch passes the FlatTests schema to the model."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {"tests": []}

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=1)
    synthesizer._generate_batch()

    call_args = mock_model.generate.call_args
    assert call_args.kwargs.get("schema") is FlatTests or (
        len(call_args.args) > 1 and call_args.args[1] is FlatTests
    )


def test_generate_batch_passes_config_to_template():
    """Test that _generate_batch renders the template with config values."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {"tests": []}

    config = GenerationConfig(
        generation_prompt="My custom prompt",
        requirements=["Compliance"],
    )
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=5)
    synthesizer._generate_batch()

    # Verify model.generate was called with a prompt containing config values
    prompt_arg = mock_model.generate.call_args.args[0]
    assert "My custom prompt" in prompt_arg
    assert "5" in prompt_arg  # num_tests = batch_size


# --- generate tests ---


@patch.object(MultiTurnSynthesizer, "_generate_batch")
@patch("rhesis.sdk.synthesizers.multi_turn.base.create_test_set")
def test_generate_single_batch(mock_create_test_set, mock_generate_batch):
    """Test generate() with num_tests <= batch_size (single batch)."""
    mock_model = Mock(spec=BaseLLM)
    batch_data = [
        {
            "test_configuration": {
                "goal": "Goal 1",
                "instructions": "",
                "restrictions": "",
                "scenario": "",
            },
            "requirement": "Compliance",
            "category": "Harmful",
            "topic": "topic1",
            "test_type": "Multi-Turn",
        },
    ]
    mock_generate_batch.return_value = batch_data

    mock_test_set = Mock()
    mock_test_set.name = "Generated Test Set"
    mock_create_test_set.return_value = mock_test_set

    config = GenerationConfig(generation_prompt="Generate tests")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=10)
    synthesizer.generate(num_tests=1)

    # batch_size should be adjusted to num_tests when num_tests < batch_size
    assert mock_generate_batch.call_count == 1
    mock_create_test_set.assert_called_once()

    # Verify create_test_set kwargs
    call_kwargs = mock_create_test_set.call_args.kwargs
    assert call_kwargs["synthesizer_name"] == "MultiTurnSynthesizer"
    assert call_kwargs["requested_tests"] == 1


@patch.object(MultiTurnSynthesizer, "_generate_batch")
@patch("rhesis.sdk.synthesizers.multi_turn.base.create_test_set")
def test_generate_multiple_batches(mock_create_test_set, mock_generate_batch):
    """Test generate() with num_tests > batch_size (multiple batches)."""
    mock_model = Mock(spec=BaseLLM)
    batch_data = [
        {
            "test_configuration": {
                "goal": f"Goal {i}",
                "instructions": "",
                "restrictions": "",
                "scenario": "",
            },
            "requirement": "Reliability",
            "category": "Harmless",
            "topic": "topic",
            "test_type": "Multi-Turn",
        }
        for i in range(5)
    ]
    mock_generate_batch.return_value = batch_data

    mock_test_set = Mock()
    mock_test_set.name = "Generated Test Set"
    mock_create_test_set.return_value = mock_test_set

    config = GenerationConfig(generation_prompt="Generate tests")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=5)
    synthesizer.generate(num_tests=15)

    # 15 // 5 = 3 batches
    assert mock_generate_batch.call_count == 3


_SAMPLE_BATCH = [
    {
        "test_configuration": {
            "goal": "Goal 1",
            "instructions": "",
            "restrictions": "",
            "scenario": "",
        },
        "requirement": "Compliance",
        "category": "Harmful",
        "topic": "topic1",
        "test_type": "Multi-Turn",
    },
]


@patch.object(MultiTurnSynthesizer, "_generate_batch")
@patch("rhesis.sdk.synthesizers.multi_turn.base.create_test_set")
def test_generate_sets_test_set_type(mock_create_test_set, mock_generate_batch):
    """Test that generate() sets test_set_type to MULTI_TURN."""
    mock_model = Mock(spec=BaseLLM)
    mock_generate_batch.return_value = _SAMPLE_BATCH

    mock_test_set = Mock()
    mock_test_set.name = "Test Set"
    mock_create_test_set.return_value = mock_test_set

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=10)
    synthesizer.generate(num_tests=5)

    from rhesis.sdk.enums import TestType

    assert mock_test_set.test_set_type == TestType.MULTI_TURN


@patch.object(MultiTurnSynthesizer, "_generate_batch")
@patch("rhesis.sdk.synthesizers.multi_turn.base.create_test_set")
def test_generate_appends_multi_turn_to_name(mock_create_test_set, mock_generate_batch):
    """Test that generate() appends '(Multi-Turn)' to test set name."""
    mock_model = Mock(spec=BaseLLM)
    mock_generate_batch.return_value = _SAMPLE_BATCH

    mock_test_set = Mock()
    mock_test_set.name = "My Test Set"
    mock_create_test_set.return_value = mock_test_set

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=10)
    synthesizer.generate(num_tests=5)

    assert mock_test_set.name == "My Test Set (Multi-Turn)"


@patch.object(MultiTurnSynthesizer, "_generate_batch")
@patch("rhesis.sdk.synthesizers.multi_turn.base.create_test_set")
def test_generate_skips_name_suffix_when_empty(mock_create_test_set, mock_generate_batch):
    """Test that generate() does not modify name when it is empty/falsy."""
    mock_model = Mock(spec=BaseLLM)
    mock_generate_batch.return_value = _SAMPLE_BATCH

    mock_test_set = Mock()
    mock_test_set.name = ""
    mock_create_test_set.return_value = mock_test_set

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=10)
    synthesizer.generate(num_tests=5)

    # Name should remain empty
    assert mock_test_set.name == ""


# --- Error handling: a failed/malformed LLM response must not crash generation ---


def test_generate_batch_returns_empty_on_error_response():
    """A model response shaped like {"error": ...} must not raise KeyError.

    Regression test: Polyphemus (and other providers) return this shape when
    generation fails -- e.g. mid scale-up-from-zero -- and _generate_batch
    used to blow up with a bare `KeyError: 'tests'` instead of degrading
    gracefully.
    """
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {"error": "Polyphemus did not respond in time."}

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=2)

    result = synthesizer._generate_batch()

    assert result == []
    assert synthesizer.last_error == "Polyphemus did not respond in time."


def test_generate_batch_returns_empty_on_unexpected_response():
    """A non-dict / dict-without-tests response also degrades to []."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = "not a dict"

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=2)

    result = synthesizer._generate_batch()

    assert result == []
    assert synthesizer.last_error is not None


@patch.object(MultiTurnSynthesizer, "_generate_batch")
@patch("rhesis.sdk.synthesizers.multi_turn.base.create_test_set")
def test_generate_retries_failed_batch(mock_create_test_set, mock_generate_batch):
    """A batch that fails once should be retried before giving up."""
    mock_model = Mock(spec=BaseLLM)
    mock_generate_batch.side_effect = [[], _SAMPLE_BATCH]
    mock_test_set = Mock()
    mock_test_set.name = "Test Set"
    mock_create_test_set.return_value = mock_test_set

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=10)
    synthesizer.generate(num_tests=5)

    assert mock_generate_batch.call_count == 2
    assert mock_create_test_set.call_args.kwargs["tests"] == _SAMPLE_BATCH


@patch.object(MultiTurnSynthesizer, "_generate_batch")
def test_generate_raises_with_reason_when_all_batches_fail(mock_generate_batch):
    """When every attempt fails, generate() raises a ValueError carrying the reason
    instead of silently returning an empty test set."""
    mock_model = Mock(spec=BaseLLM)
    mock_generate_batch.return_value = []

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=10)
    synthesizer.last_error = "Polyphemus did not respond in time."

    with pytest.raises(ValueError, match="Polyphemus did not respond in time."):
        synthesizer.generate(num_tests=5)


# --- Requirement attribution tests ---
#
# Multi-turn generation used to attach the seeded default requirements
# (Compliance / Reliability / Robustness) instead of the ones the caller asked for.
# Two things caused it: the prompt named the defaults dozens of times regardless of
# what was passed, and nothing validated the model's answer. These lock both shut.

DEFAULT_REQUIREMENTS = ("Compliance", "Reliability", "Robustness")


def _flat_test(requirement: str) -> dict:
    return {
        "test_configuration_goal": "goal",
        "test_configuration_instructions": "instructions",
        "test_configuration_restrictions": "restrictions",
        "test_configuration_scenario": "scenario",
        "test_configuration_min_turns": 3,
        "test_configuration_max_turns": 7,
        "requirement": requirement,
        "category": "Harmless",
        "topic": "topic",
    }


def _render(config: GenerationConfig) -> str:
    synthesizer = MultiTurnSynthesizer(config=config, model=Mock(spec=BaseLLM))
    template = synthesizer.load_prompt_template("base.jinja")
    return template.render({"num_tests": 5, "harmful": False, **config.model_dump()})


def test_prompt_does_not_name_default_requirements_when_caller_supplies_them():
    """The rendered prompt must not mention the seeded defaults when the caller
    passed requirements — that is what made the model emit them instead."""
    rendered = _render(
        GenerationConfig(
            generation_prompt="Test the triage agent",
            requirements=["Summary Grounding", "Red-Flag Escalation"],
        )
    )

    for default in DEFAULT_REQUIREMENTS:
        assert default not in rendered, f"prompt still instructs the default {default!r}"
    assert "- Summary Grounding" in rendered
    assert "- Red-Flag Escalation" in rendered


def test_prompt_renders_requirements_as_list_not_python_repr():
    """Requirements used to render as a bare list repr, which read as noise next to
    the prose instructions around it."""
    rendered = _render(
        GenerationConfig(generation_prompt="x", requirements=["Summary Grounding"])
    )

    assert "['Summary Grounding']" not in rendered
    assert "- Summary Grounding" in rendered


def test_prompt_still_offers_defaults_when_no_requirements_given():
    """With nothing passed, the defaults are the correct instruction."""
    rendered = _render(GenerationConfig(generation_prompt="x"))

    assert "Use the following default requirements" in rendered
    for default in DEFAULT_REQUIREMENTS:
        assert default in rendered


def test_harmful_prompt_uses_supplied_requirements():
    """The adversarial branch never rendered requirements at all and hardcoded
    Robustness/Compliance."""
    config = GenerationConfig(generation_prompt="x", requirements=["Resists Memory Poisoning"])
    synthesizer = MultiTurnSynthesizer(config=config, model=Mock(spec=BaseLLM))
    template = synthesizer.load_prompt_template("base.jinja")
    rendered = template.render({"num_tests": 5, "harmful": True, **config.model_dump()})

    assert "- Resists Memory Poisoning" in rendered
    for default in DEFAULT_REQUIREMENTS:
        assert default not in rendered


@pytest.mark.parametrize(
    "emitted,expected",
    [
        ("Summary Grounding", "Summary Grounding"),
        ("  summary grounding  ", "Summary Grounding"),
        ("SUMMARY GROUNDING", "Summary Grounding"),
        ("Compliance", None),
        ("", None),
        (None, None),
    ],
)
def test_canonical_requirement(emitted, expected):
    """Casing and whitespace are corrected; anything not requested is rejected."""
    config = GenerationConfig(generation_prompt="x", requirements=["Summary Grounding"])
    synthesizer = MultiTurnSynthesizer(config=config, model=Mock(spec=BaseLLM))

    assert synthesizer._canonical_requirement(emitted) == expected


def test_canonical_requirement_passes_through_when_none_configured():
    """With no configured requirements there is nothing to validate against."""
    synthesizer = MultiTurnSynthesizer(
        config=GenerationConfig(generation_prompt="x"), model=Mock(spec=BaseLLM)
    )

    assert synthesizer._canonical_requirement("Compliance") == "Compliance"


def test_generate_batch_drops_tests_with_unrequested_requirement():
    """A model that ignores the prompt must not produce mis-attributed tests."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {
        "tests": [
            _flat_test("Summary Grounding"),
            _flat_test("Compliance"),
            _flat_test("summary grounding"),
        ]
    }
    config = GenerationConfig(generation_prompt="x", requirements=["Summary Grounding"])
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model)

    tests = synthesizer._generate_batch()

    assert [t["requirement"] for t in tests] == ["Summary Grounding", "Summary Grounding"]


# --- Config field-naming tests ---


def test_generation_config_accepts_singular_aliases():
    """The singular spellings were the pre-existing shape; they must keep working
    rather than being dropped."""
    config = GenerationConfig(
        generation_prompt="x",
        requirement=["Summary Grounding"],
        category=["Harmless"],
        topic=["triage"],
    )

    assert config.requirements == ["Summary Grounding"]
    assert config.categories == ["Harmless"]
    assert config.topics == ["triage"]


def test_generation_config_rejects_unknown_field():
    """An unrecognised field name must raise instead of being silently ignored —
    silent dropping is what attached the wrong requirements in the first place."""
    with pytest.raises(ValidationError):
        GenerationConfig(generation_prompt="x", requirementz=["Summary Grounding"])
