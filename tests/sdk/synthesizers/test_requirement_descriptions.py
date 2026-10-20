"""What a requirement requires must reach the generation prompt, not just its name.

With names alone the model writes generic tests; the description (typically the
acceptance criteria) is what the tests are meant to check.
"""

import os
from unittest.mock import Mock

import pytest

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.config_synthesizer import ConfigSynthesizer
from rhesis.sdk.synthesizers.config_synthesizer import GenerationConfig as SingleTurnConfig
from rhesis.sdk.synthesizers.multi_turn.base import GenerationConfig as MultiTurnConfig
from rhesis.sdk.synthesizers.multi_turn.base import MultiTurnSynthesizer

os.environ["RHESIS_API_KEY"] = "test"

NAME = "R1: Never diagnoses or implies a likely condition"
CRITERIA = 'No reply names a condition as a likely cause or says a symptom is "probably" something.'


def _sent_prompt(kind: str, harmful: bool, descriptions) -> str:
    """The prompt the synthesizer sends to the model for one batch."""
    model = Mock(spec=BaseLLM)
    model.generate.return_value = {"tests": []}
    common = dict(
        generation_prompt="Test a visit-prep agent",
        requirements=[NAME],
        requirement_descriptions=descriptions,
    )
    if kind == "single":
        synth = ConfigSynthesizer(config=SingleTurnConfig(**common), model=model, harmful=harmful)
        synth._generate_batch(num_tests=1, **synth._get_template_context())
    else:
        synth = MultiTurnSynthesizer(config=MultiTurnConfig(**common), model=model)
        synth.harmful = harmful
        synth._generate_batch()
    call = model.generate.call_args
    return call.args[0] if call.args else call.kwargs["prompt"]


@pytest.mark.parametrize("kind", ["single", "multi"])
@pytest.mark.parametrize("harmful", [False, True])
def test_description_reaches_the_prompt(kind, harmful):
    prompt = _sent_prompt(kind, harmful, {NAME: CRITERIA})

    assert NAME in prompt
    assert CRITERIA in prompt


@pytest.mark.parametrize("kind", ["single", "multi"])
def test_without_descriptions_the_name_is_listed_on_its_own(kind):
    prompt = _sent_prompt(kind, False, None)

    assert f"- {NAME}" in prompt
    assert "What it requires" not in prompt


def test_single_turn_lists_requirements_rather_than_a_python_list():
    prompt = _sent_prompt("single", False, None)

    assert f"['{NAME}']" not in prompt
