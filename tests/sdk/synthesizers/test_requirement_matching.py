"""Generated tests keep to the requirements the caller asked for."""

import os
from unittest.mock import Mock

import pytest

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.config_synthesizer import ConfigSynthesizer, GenerationConfig
from rhesis.sdk.synthesizers.synthesizer import Synthesizer
from rhesis.sdk.synthesizers.utils import canonical_requirement

os.environ["RHESIS_API_KEY"] = "test"


def _flat(requirement):
    return {
        "prompt_content": "How do I file a claim?",
        "prompt_expected_response": "Explain the steps.",
        "prompt_language_code": "en",
        "requirement": requirement,
        "category": "Harmless",
        "topic": "Claims",
    }


@pytest.mark.parametrize(
    "value, expected",
    [("Compliance", "Compliance"), ("  compliance ", "Compliance"), ("Something else", None)],
)
def test_canonical_requirement(value, expected):
    assert canonical_requirement(value, ["Compliance", "Robustness"]) == expected


def test_with_nothing_requested_any_requirement_passes():
    assert canonical_requirement("Anything", None) == "Anything"


def test_single_turn_maps_a_recased_requirement_and_drops_an_unrequested_one():
    config = GenerationConfig(generation_prompt="p", requirements=["Compliance"])
    synthesizer = ConfigSynthesizer(config=config, model=Mock(spec=BaseLLM))

    tests = synthesizer._single_turn_tests([_flat("compliance"), _flat("Made up")])

    assert [t["requirement"] for t in tests] == ["Compliance"]


def test_single_turn_without_requested_requirements_keeps_what_the_model_wrote():
    config = GenerationConfig(generation_prompt="p")
    synthesizer = ConfigSynthesizer(config=config, model=Mock(spec=BaseLLM))

    tests = synthesizer._single_turn_tests([_flat("Its own")])

    assert [t["requirement"] for t in tests] == ["Its own"]


def test_the_prompt_synthesizer_keeps_to_its_requirements_too():
    synthesizer = Synthesizer(prompt="p", requirements=["Compliance"], model=Mock(spec=BaseLLM))

    tests = synthesizer._single_turn_tests([_flat("COMPLIANCE"), _flat("Other")])

    assert [t["requirement"] for t in tests] == ["Compliance"]


def test_when_every_test_is_dropped_the_reason_is_kept():
    config = GenerationConfig(generation_prompt="p", requirements=["Compliance"])
    synthesizer = ConfigSynthesizer(config=config, model=Mock(spec=BaseLLM))

    synthesizer._single_turn_tests([_flat("Other")])

    assert "Other" in synthesizer.last_error
