import os
from unittest.mock import Mock, patch

from rhesis.sdk.enums import TestType
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.owasp_extractor import ReportSection
from rhesis.sdk.synthesizers.owasp_synthesizer import OWASPSynthesizer

os.environ["RHESIS_API_KEY"] = "test"

_SECTIONS = [ReportSection(id="llm01", name="Prompt Injection", content="report content")]


def _flat_multiturn_test(i: int) -> dict:
    """A flat multi-turn test dict matching multi_turn.base.FlatTest (reused
    directly by OWASPSynthesizer instead of a duplicate schema)."""
    return {
        "test_configuration_goal": f"Goal {i}",
        "test_configuration_instructions": "Step 1\nStep 2",
        "test_configuration_restrictions": "",
        "test_configuration_scenario": "Scenario",
        "test_configuration_min_turns": 3,
        "test_configuration_max_turns": 7,
        "behavior": "Robustness",
        "category": "Harmful",
        "topic": "prompt injection",
    }


# --- Consolidated multi-turn path: naming/stamping ---


@patch("rhesis.sdk.synthesizers.owasp_synthesizer.fetch_owasp_sections", return_value=_SECTIONS)
def test_multi_turn_generate_stamps_and_names_tests(_mock_fetch):
    """generate() with test_type=MULTI_TURN should route through the
    consolidated path (shared FlatTest/FlatTests schema + stamp_multi_turn)
    and produce correctly nested, stamped, named tests."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {"tests": [_flat_multiturn_test(i) for i in range(2)]}

    synthesizer = OWASPSynthesizer(
        purpose="Customer support chatbot",
        model=mock_model,
        test_type=TestType.MULTI_TURN,
        batch_size=10,
    )

    test_set = synthesizer.generate(num_tests=2)

    assert test_set.test_set_type == TestType.MULTI_TURN
    assert test_set.name is not None and test_set.name.endswith("(Multi-Turn)")
    assert len(test_set.tests) == 2
    for test in test_set.tests:
        assert test.test_type == TestType.MULTI_TURN
        assert test.test_configuration is not None
        assert test.test_configuration.goal.startswith("Goal")
        assert test.test_configuration.min_turns == 3
        assert test.test_configuration.max_turns == 7
        assert test.metadata["owasp_category"] == "llm01"
        assert test.metadata["owasp_name"] == "Prompt Injection"


# --- Correctness: flaky multi-turn LLM calls now retry instead of dropping tests ---


@patch("rhesis.sdk.synthesizers.owasp_synthesizer.fetch_owasp_sections", return_value=_SECTIONS)
def test_multi_turn_flaky_llm_call_retries_with_smaller_batches(_mock_fetch):
    """A single malformed multi-turn LLM response must no longer silently
    drop the whole section's tests. Before the consolidation, the bespoke
    while-loop in _generate_multiturn_tests would `break` on the first bad
    response. Now _generate_batch is a plain override plugged into the
    inherited TestSetSynthesizer._generate_with_retry, so the same failure
    triggers a batch-size-reduction retry instead."""
    mock_model = Mock(spec=BaseLLM)
    bad_response = {"unexpected": "shape"}  # missing "tests" key -> treated as a failure
    good_response = {"tests": [_flat_multiturn_test(i) for i in range(10)]}

    mock_model.generate.side_effect = [bad_response, good_response, good_response]

    synthesizer = OWASPSynthesizer(
        purpose="Customer support chatbot",
        model=mock_model,
        test_type=TestType.MULTI_TURN,
        batch_size=10,
    )

    tests = synthesizer._generate_without_sources(num_tests=10)

    # Nothing was silently dropped: the retry recovered all 10 requested tests.
    assert len(tests) == 10
    assert mock_model.generate.call_count == 3

    prompts = [call.kwargs["prompt"] for call in mock_model.generate.call_args_list]
    # First attempt requests the full batch; after the failure, batch size is
    # halved (10 -> 5) for the retries, mirroring _generate_with_retry's
    # single-turn behavior.
    assert "EXACTLY 10" in prompts[0]
    assert "EXACTLY 5" in prompts[1]
    assert "EXACTLY 5" in prompts[2]


# --- Regression guard: single-turn behavior is untouched ---


@patch("rhesis.sdk.synthesizers.owasp_synthesizer.fetch_owasp_sections", return_value=_SECTIONS)
def test_single_turn_generation_still_uses_prompt_schema(_mock_fetch):
    """Default (SINGLE_TURN) generation must keep using the inherited
    prompt-based flat schema/repack, unaffected by the multi-turn override."""
    mock_model = Mock(spec=BaseLLM)
    mock_model.generate.return_value = {
        "tests": [
            {
                "prompt_content": "Attack prompt",
                "prompt_expected_response": "Refusal",
                "prompt_language_code": "en",
                "behavior": "OWASP LLM Top 10",
                "category": "Harmful",
                "topic": "prompt injection",
            }
        ]
    }

    synthesizer = OWASPSynthesizer(purpose="Customer support chatbot", model=mock_model)

    tests = synthesizer._generate_without_sources(num_tests=1)

    assert len(tests) == 1
    assert tests[0]["prompt"]["content"] == "Attack prompt"
    assert tests[0]["test_type"] == TestType.SINGLE_TURN.value
