"""The generation job passes the requirement descriptions it was given to the synthesizer.

The router reads them under the test set's project and puts them in the job's config.
The job hands the backend's own ``GenerationConfig`` to the SDK synthesizers, so these
tests also render the real SDK prompt from what the job passed, for both test types.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from rhesis.backend.jobs.test_set import generate_and_save_test_set
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers import ConfigSynthesizer, MultiTurnSynthesizer

NAME = "R3: Escalates genuine red flags immediately"
CRITERIA = "Chest pain with arm numbness gets the fixed escalation reply."


def _fake_db_test_set():
    row = MagicMock()
    row.id = "ts-1"
    row.name = "Test Set"
    row.attributes = {"metadata": {}}
    return row


def _config_passed_to_synthesizer(test_type: str):
    synthesizer = MagicMock()
    synthesizer.generate.return_value.tests = []
    target = "ConfigSynthesizer" if test_type == "Single-Turn" else "MultiTurnSynthesizer"

    with (
        patch.object(
            generate_and_save_test_set,
            "get_tenant_context",
            return_value=("org-1", "user-1", "proj-1"),
        ),
        patch.object(generate_and_save_test_set, "update_state"),
        patch.object(generate_and_save_test_set, "emit"),
        patch.object(generate_and_save_test_set, "set_progress"),
        patch("rhesis.backend.jobs.test_set._resolve_generation_model", return_value="m"),
        patch(f"rhesis.sdk.synthesizers.{target}", return_value=synthesizer) as synth_cls,
        patch(
            "rhesis.backend.jobs.test_set._save_test_set_to_database",
            return_value=_fake_db_test_set(),
        ),
        patch("rhesis.backend.jobs.test_set.dispatch_accrual"),
    ):
        generate_and_save_test_set(
            config={
                "generation_prompt": "Test a visit-prep agent",
                "requirements": [NAME],
                "requirement_descriptions": {NAME: CRITERIA},
            },
            num_tests=1,
            test_type=test_type,
        )

    return synth_cls.call_args.kwargs["config"]


def _prompt(synthesizer_cls, config) -> str:
    model = Mock(spec=BaseLLM)
    model.generate.return_value = {"tests": []}
    synth = synthesizer_cls(config=config, model=model)
    if synthesizer_cls is ConfigSynthesizer:
        synth._generate_batch(num_tests=1, **synth._get_template_context())
    else:
        synth._generate_batch()
    call = model.generate.call_args
    return call.args[0] if call.args else call.kwargs["prompt"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "test_type, synthesizer_cls",
    [("Single-Turn", ConfigSynthesizer), ("Multi-Turn", MultiTurnSynthesizer)],
)
def test_descriptions_reach_the_generation_prompt(test_type, synthesizer_cls):
    config = _config_passed_to_synthesizer(test_type)

    assert config.requirement_descriptions == {NAME: CRITERIA}
    assert CRITERIA in _prompt(synthesizer_cls, config)
