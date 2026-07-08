import pytest

from dr_rhesis.pipeline import build_intent_pipeline, run_turn
from dr_rhesis.state import DrRhesisState
from tests.mocks import make_components


def test_numeric_message_stays_string_through_pipeline():
    """ConditionalRouter must not coerce '9' to int via Jinja unsafe mode."""
    components = make_components(
        [
            '{"intent": "health_concern"}',
            '{"severity": 9}',
            '{"target_slot": "timing", "question": "Is it constant or intermittent?"}',
        ]
    )
    pipeline = build_intent_pipeline(components)
    result = run_turn("9", DrRhesisState(chief_complaint="nausea"), pipeline=pipeline, components=components)
    assert result["state"].slots.severity == "9"
    assert "?" in result["response"]


SPECIAL_MESSAGES = [
    "I'm in pain",
    "It's a 9/10 and I can't cope",
    'she said "it hurts"',
    "line one\nline two",
    "it's \"really\" bad\nand it's spreading",
]


@pytest.mark.parametrize("message", SPECIAL_MESSAGES)
def test_router_preserves_messages_with_special_chars(message: str):
    """The intent router must emit apostrophe/quote/newline messages as intact str.

    Regression for manual single-quoting ("'{{ message }}'") which produced an
    invalid literal (e.g. 'I'm in pain') and crashed the pipeline under unsafe
    native evaluation.
    """
    from dr_rhesis.pipeline import _build_intent_conditional_router

    router = _build_intent_conditional_router()
    out = router.run(intent="health_concern", message=message, state=DrRhesisState())
    assert out["health_message"] == message
    assert isinstance(out["health_message"], str)


@pytest.mark.parametrize("message", SPECIAL_MESSAGES)
def test_special_char_message_completes_turn(message: str):
    """A full turn with special characters must not crash and stays a string."""
    components = make_components(
        [
            '{"intent": "health_concern"}',
            "{}",
            '{"target_slot": "onset", "question": "When did it start?"}',
        ]
    )
    pipeline = build_intent_pipeline(components)
    result = run_turn(message, DrRhesisState(), pipeline=pipeline, components=components)
    user_turns = [h for h in result["state"].history if h["role"] == "user"]
    assert user_turns[-1]["content"] == message
    assert "?" in result["response"]
