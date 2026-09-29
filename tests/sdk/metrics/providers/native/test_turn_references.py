"""Judges scoring a conversation return the turns their verdict rests on; single-turn ones don't."""

from unittest.mock import AsyncMock, patch

import pytest

from rhesis.sdk.metrics.conversational.types import ConversationHistory
from rhesis.sdk.metrics.providers.native.categorical_judge import CategoricalJudge
from rhesis.sdk.metrics.providers.native.conversational_judge import ConversationalJudge
from rhesis.sdk.metrics.providers.native.numeric_judge import NumericJudge
from rhesis.sdk.metrics.providers.native.turn_references import TURN_REFERENCE_INSTRUCTION

_CONVERSATION = ConversationHistory.from_messages(
    [
        {"role": "user", "content": "My chest hurts."},
        {"role": "assistant", "content": "I can help you prepare for a visit."},
        {"role": "user", "content": "It is getting worse."},
        {"role": "assistant", "content": "Please call emergency services now."},
    ]
)
_TRANSCRIPT = _CONVERSATION.format_conversation()


@pytest.fixture
def numeric():
    return NumericJudge(
        evaluation_prompt="Judge escalation", min_score=0, max_score=1, threshold=0.5
    )


@pytest.fixture
def categorical():
    return CategoricalJudge(
        evaluation_prompt="Judge escalation",
        categories=["Escalated", "Ignored"],
        passing_categories="Escalated",
    )


def _evaluate(metric, response, **kwargs):
    with patch.object(metric.model, "a_generate", new_callable=AsyncMock) as a_generate:
        a_generate.return_value = response
        result = metric.evaluate(
            input="Escalate chest pain", output=_TRANSCRIPT, expected_output="", **kwargs
        )
    return result, a_generate.call_args


class TestNumericJudge:
    def test_cites_turns_when_scoring_a_conversation(self, numeric):
        result, call = _evaluate(
            numeric,
            {"score": 0.0, "reason": "Ignored turn 1", "relevant_turns": [1]},
            conversation_history=_CONVERSATION,
        )

        assert result.details["relevant_turns"] == [1]
        assert TURN_REFERENCE_INSTRUCTION in call.args[0]
        assert "relevant_turns" in call.kwargs["schema"].model_fields

    def test_single_turn_prompt_and_schema_are_unchanged(self, numeric):
        result, call = _evaluate(numeric, {"score": 1.0, "reason": "Fine"})

        assert "relevant_turns" not in result.details
        assert TURN_REFERENCE_INSTRUCTION not in call.args[0]
        assert "relevant_turns" not in call.kwargs["schema"].model_fields


class TestCategoricalJudge:
    def test_cites_turns_when_scoring_a_conversation(self, categorical):
        result, call = _evaluate(
            categorical,
            {"score": "Ignored", "reason": "Ignored turn 1", "relevant_turns": [1]},
            conversation_history=_CONVERSATION,
        )

        assert result.details["is_successful"] is False
        assert result.details["relevant_turns"] == [1]
        assert TURN_REFERENCE_INSTRUCTION in call.args[0]

    def test_single_turn_prompt_and_schema_are_unchanged(self, categorical):
        result, call = _evaluate(categorical, {"score": "Escalated", "reason": "Fine"})

        assert "relevant_turns" not in result.details
        assert TURN_REFERENCE_INSTRUCTION not in call.args[0]
        assert "relevant_turns" not in call.kwargs["schema"].model_fields


def test_conversational_judge_always_cites_turns():
    metric = ConversationalJudge(
        evaluation_prompt="Judge escalation", min_score=0, max_score=1, threshold=0.5
    )
    with patch.object(metric.model, "a_generate", new_callable=AsyncMock) as a_generate:
        a_generate.return_value = {"score": 0.0, "reason": "Ignored", "relevant_turns": [1]}
        result = metric.evaluate(conversation_history=_CONVERSATION)

    assert result.details["relevant_turns"] == [1]
    assert TURN_REFERENCE_INSTRUCTION in a_generate.call_args.args[0]
