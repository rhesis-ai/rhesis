"""Experiment parameters map onto the agent config, and bad values fall back to defaults."""

from __future__ import annotations

import dataclasses
import uuid

import pytest

import visit_prep.config as config_mod
import visit_prep.session as session_mod
from rhesis.sdk.decorators._state import _parameters_context
from rhesis.sdk.models.parameters import (
    BooleanValue,
    NumberValue,
    ResolvedParameters,
    StringValue,
    TextValue,
)
from tests.mocks import MockChatGenerator, greeting_script
from visit_prep.agents.coordinator import COORDINATOR_SYSTEM_PROMPT
from visit_prep.client import build_chat_generator
from visit_prep.config import (
    PARAMETER_NAMES,
    VisitPrepConfig,
    parameter_schema,
    resolve_config,
)
from visit_prep.pipeline import build_coordinator_pipeline, run_turn

GATHERING_PROMPT = "Coordinate the visit.\n\n{{ slot_status }}"


def resolved(**values) -> ResolvedParameters:
    """ResolvedParameters as a connector test run would hand them to the endpoint."""

    def typed(value):
        if isinstance(value, bool):
            return BooleanValue(value=value)
        if isinstance(value, int | float):
            return NumberValue(value=value)
        return (TextValue if "\n" in value else StringValue)(value=value)

    return ResolvedParameters(
        values={name: typed(value) for name, value in values.items()},
        experiment_id=uuid.uuid4(),
        version="v1",
        source="experiment_id",
    )


@pytest.fixture
def experiment():
    """Set the connector's experiment parameters for the duration of a test."""
    tokens = []

    def set_params(**values):
        tokens.append(_parameters_context.set(resolved(**values)))

    yield set_params
    for token in reversed(tokens):
        _parameters_context.reset(token)


def test_no_parameters_means_defaults():
    assert VisitPrepConfig.from_parameters(None) == VisitPrepConfig()
    assert VisitPrepConfig.from_parameters(resolved()) == VisitPrepConfig()


def test_experiment_values_override_defaults():
    config = VisitPrepConfig.from_parameters(
        resolved(
            model=" gemini-exp ",
            temperature=0,
            coordinator_prompt=GATHERING_PROMPT,
            critic_prompt="Be strict.",
        )
    )

    assert config.model == "gemini-exp"
    assert config.temperature == 0.0
    assert config.coordinator_prompt == GATHERING_PROMPT
    assert config.critic_prompt == "Be strict."
    assert config.summary_prompt == VisitPrepConfig().summary_prompt


@pytest.mark.parametrize(
    "values",
    [
        {"model": "  "},
        {"temperature": True},
        {"temperature": "hot"},
        {"summary_prompt": ""},
        {"unknown_knob": "x"},
    ],
    ids=["blank-model", "bool-temperature", "text-temperature", "blank-prompt", "unknown"],
)
def test_unusable_values_are_ignored(values):
    assert VisitPrepConfig.from_parameters(resolved(**values)) == VisitPrepConfig()


@pytest.mark.parametrize(
    "prompt",
    [
        "Coordinate the visit.",
        "Coordinate the visit. {{ slot_status }} {{ extra }}",
        "Coordinate the visit. {{ slot_status",
    ],
    ids=["missing-variable", "extra-variable", "broken-template"],
)
def test_prompt_with_wrong_variables_keeps_the_default(prompt):
    config = VisitPrepConfig.from_parameters(resolved(coordinator_prompt=prompt))

    assert config.coordinator_prompt == COORDINATOR_SYSTEM_PROMPT


def test_accepted_prompts_run_a_turn():
    """The variable check is what keeps an experiment prompt from failing pipeline validation."""
    config = VisitPrepConfig.from_parameters(
        resolved(coordinator_prompt=GATHERING_PROMPT, history_prompt=GATHERING_PROMPT)
    )
    pipe = build_coordinator_pipeline(MockChatGenerator(greeting_script()), config)

    assert pipe.get_component("coordinator").system_prompt == GATHERING_PROMPT
    assert "visit-preparation assistant" in run_turn("Hello!", pipeline=pipe)["response"]


def test_resolve_config_reads_the_test_run_experiment(experiment):
    experiment(model="gemini-exp")

    assert resolve_config().model == "gemini-exp"


def test_resolve_config_skips_the_api_unless_an_environment_is_pinned(monkeypatch):
    monkeypatch.delenv("RHESIS_PARAMETERS_ENVIRONMENT", raising=False)

    def fail(**_kwargs):
        raise AssertionError("Parameters.get must not be called")

    monkeypatch.setattr(config_mod.Parameters, "get", fail)

    assert resolve_config() == VisitPrepConfig()


def test_resolve_config_uses_the_pinned_environment(monkeypatch):
    monkeypatch.setenv("RHESIS_PARAMETERS_ENVIRONMENT", "staging")
    monkeypatch.setenv("RHESIS_PROJECT_ID", "p1")
    calls = []

    def fake_get(**kwargs):
        calls.append(kwargs)
        return resolved(temperature=0.3)

    monkeypatch.setattr(config_mod.Parameters, "get", fake_get)

    assert resolve_config().temperature == 0.3
    assert calls == [{"project_id": "p1"}]


def test_resolve_config_falls_back_when_the_api_fails(monkeypatch):
    monkeypatch.setenv("RHESIS_PARAMETERS_ENVIRONMENT", "staging")

    def boom(**_kwargs):
        raise RuntimeError("404 no experiment")

    monkeypatch.setattr(config_mod.Parameters, "get", boom)

    assert resolve_config() == VisitPrepConfig()


def test_schema_matches_the_config():
    schema = parameter_schema()
    config_fields = {f.name for f in dataclasses.fields(VisitPrepConfig)}

    assert tuple(f.name for f in schema.fields) == PARAMETER_NAMES
    assert set(PARAMETER_NAMES) == config_fields
    # Every prompt default must pass its own variable check, or pushing it would be a trap.
    defaults = {f.name: f.default.value for f in schema.fields if f.default is not None}
    assert VisitPrepConfig.from_parameters(resolved(**defaults)) == VisitPrepConfig()


def test_generator_takes_model_and_temperature(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    generator = build_chat_generator("gemini-exp", 0.2)

    assert generator._model == "gemini-exp"
    assert generator._generation_kwargs == {"temperature": 0.2}


def test_pipelines_are_cached_per_config(monkeypatch):
    monkeypatch.setattr(session_mod, "_pipelines", {})
    monkeypatch.setattr(session_mod, "build_coordinator_pipeline", lambda config: object())
    monkeypatch.setattr(session_mod, "MAX_CACHED_PIPELINES", 2)

    default = session_mod.get_pipeline()
    assert session_mod.get_pipeline(VisitPrepConfig()) is default

    cold = session_mod.get_pipeline(VisitPrepConfig(temperature=0.0))
    assert cold is not default

    session_mod.get_pipeline(VisitPrepConfig(temperature=1.0))
    assert len(session_mod._pipelines) == 2
    assert session_mod.get_pipeline() is not default, "oldest entry should have been evicted"
