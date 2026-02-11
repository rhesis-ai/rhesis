import os
from unittest.mock import Mock, patch

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.multi_turn.base import (
    GenerationConfig,
    MultiTurnSynthesizer,
    Tests,
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
        behaviors=["Compliance", "Reliability"],
        categories=["Harmful", "Harmless"],
        topics=["healthcare", "finance"],
        additional_context="Extra context here",
    )

    assert config.generation_prompt == "Generate tests"
    assert config.behaviors == ["Compliance", "Reliability"]
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


# --- _generate_batch tests ---


def test_generate_batch_returns_correct_structure():
    """Test that _generate_batch returns list of dicts with nested structure."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {
        "tests": [
            {
                "test_configuration": {
                    "goal": "Test goal A",
                    "instructions": "Step 1, Step 2",
                    "restrictions": "No PII",
                    "scenario": "Customer support",
                },
                "behavior": "Compliance",
                "category": "Harmful",
                "topic": "data privacy",
            },
            {
                "test_configuration": {
                    "goal": "Test goal B",
                    "instructions": "",
                    "restrictions": "",
                    "scenario": "",
                },
                "behavior": "Reliability",
                "category": "Harmless",
                "topic": "product info",
            },
        ]
    }

    config = GenerationConfig(generation_prompt="Generate tests")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=2)
    result = synthesizer._generate_batch()

    assert len(result) == 2

    # First test
    assert result[0]["test_configuration"]["goal"] == "Test goal A"
    assert result[0]["test_configuration"]["instructions"] == "Step 1, Step 2"
    assert result[0]["test_configuration"]["restrictions"] == "No PII"
    assert result[0]["test_configuration"]["scenario"] == "Customer support"
    assert result[0]["behavior"] == "Compliance"
    assert result[0]["category"] == "Harmful"
    assert result[0]["topic"] == "data privacy"
    assert result[0]["test_type"] == "Multi-Turn"

    # Second test
    assert result[1]["test_configuration"]["goal"] == "Test goal B"
    assert result[1]["behavior"] == "Reliability"
    assert result[1]["category"] == "Harmless"
    assert result[1]["topic"] == "product info"
    assert result[1]["test_type"] == "Multi-Turn"


def test_generate_batch_sets_multi_turn_type():
    """Test that _generate_batch always sets test_type to Multi-Turn."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {
        "tests": [
            {
                "test_configuration": {
                    "goal": "Goal",
                    "instructions": "",
                    "restrictions": "",
                    "scenario": "",
                },
                "behavior": "Robustness",
                "category": "Harmful",
                "topic": "security",
            },
        ]
    }

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=1)
    result = synthesizer._generate_batch()

    assert result[0]["test_type"] == "Multi-Turn"


def test_generate_batch_passes_schema_to_model():
    """Test that _generate_batch passes the Tests schema to the model."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {"tests": []}

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=1)
    synthesizer._generate_batch()

    call_args = mock_model.generate.call_args
    assert call_args.kwargs.get("schema") is Tests or (
        len(call_args.args) > 1 and call_args.args[1] is Tests
    )


def test_generate_batch_passes_config_to_template():
    """Test that _generate_batch renders the template with config values."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {"tests": []}

    config = GenerationConfig(
        generation_prompt="My custom prompt",
        behaviors=["Compliance"],
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
            "behavior": "Compliance",
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
            "behavior": "Reliability",
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


@patch.object(MultiTurnSynthesizer, "_generate_batch")
@patch("rhesis.sdk.synthesizers.multi_turn.base.create_test_set")
def test_generate_sets_test_set_type(mock_create_test_set, mock_generate_batch):
    """Test that generate() sets test_set_type to MULTI_TURN."""
    mock_model = Mock(spec=BaseLLM)
    mock_generate_batch.return_value = []

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
    mock_generate_batch.return_value = []

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
    mock_generate_batch.return_value = []

    mock_test_set = Mock()
    mock_test_set.name = ""
    mock_create_test_set.return_value = mock_test_set

    config = GenerationConfig(generation_prompt="Test")
    synthesizer = MultiTurnSynthesizer(config=config, model=mock_model, batch_size=10)
    synthesizer.generate(num_tests=5)

    # Name should remain empty
    assert mock_test_set.name == ""
