from dr_rhesis.pipeline import PrepareTurn, build_intent_pipeline, run_turn
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
