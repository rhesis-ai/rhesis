from tests.mocks import MockChatGenerator, make_components
from visit_prep.pipeline import build_intent_pipeline, run_turn
from visit_prep.state import Phase, Slots, VisitPrepState


def test_greeting_turn_increments_counter():
    components = make_components(['{"intent": "greeting"}'])
    pipeline = build_intent_pipeline(components)
    result = run_turn("hello", VisitPrepState(), pipeline=pipeline, components=components)
    assert result["state"].turn == 1
    assert "visit" in result["response"].lower()


def test_emergency_escalates():
    components = make_components(['{"intent": "emergency"}'])
    pipeline = build_intent_pipeline(components)
    result = run_turn(
        "chest pain and can't breathe",
        VisitPrepState(),
        pipeline=pipeline,
        components=components,
    )
    assert result["state"].phase == Phase.ESCALATED


def test_out_of_scope_redirects():
    components = make_components(['{"intent": "out_of_scope"}'])
    pipeline = build_intent_pipeline(components)
    result = run_turn(
        "What do I have?",
        VisitPrepState(),
        pipeline=pipeline,
        components=components,
    )
    assert "diagnos" in result["response"].lower() or "prescrib" in result["response"].lower()


def test_health_concern_asks_one_question():
    components = make_components(
        [
            '{"intent": "health_concern"}',
            '{"chief_complaint": "headache", "onset": "2 days ago"}',
            '{"target_slot": "location", "question": "Where is the pain located?"}',
        ]
    )
    pipeline = build_intent_pipeline(components)
    result = run_turn(
        "I have a headache",
        VisitPrepState(),
        pipeline=pipeline,
        components=components,
    )
    assert result["state"].phase == Phase.GATHERING
    assert result["state"].slots.onset == "2 days ago"
    assert "?" in result["response"]


def test_red_flag_mid_gathering_escalates():
    components = make_components(
        [
            '{"intent": "health_concern"}',
            '{"chief_complaint": "headache"}',
            '{"target_slot": "onset", "question": "When did it start?"}',
            '{"intent": "health_concern"}',
            '{"onset": "suddenly", "associated": "worst headache of my life"}',
        ]
    )
    pipeline = build_intent_pipeline(components)
    state = VisitPrepState()
    first = run_turn("headache", state, pipeline=pipeline, components=components)
    result = run_turn(
        "worst headache of my life with slurred speech",
        first["state"],
        pipeline=pipeline,
        components=components,
    )
    assert result["state"].phase == Phase.ESCALATED


def test_complete_history_produces_summary():
    filled = VisitPrepState(
        chief_complaint="headache",
        slots=Slots(
            onset="3 days",
            location="temples",
            character="pressure",
            severity="4/10",
            timing="intermittent",
            aggravating="screens",
            relieving="rest",
            associated="neck stiffness",
        ),
        phase=Phase.GATHERING,
        turn=8,
        history=[{"role": "user", "content": "final detail"}],
    )
    components = make_components(
        [
            '{"intent": "health_concern"}',
            "{}",
            '{"approved": true, "feedback": ""}',
        ]
    )
    # Patch summary to avoid extra LLM call — gathering won't ask when complete
    components.summary._generator = MockChatGenerator(  # type: ignore[attr-defined]
        [
            "## Timeline\n- Headache for 3 days\n\n## Questions\n- Could this relate to tension?",
        ]
    )
    pipeline = build_intent_pipeline(components)
    result = run_turn("that's all", filled, pipeline=pipeline, components=components)
    assert result["state"].phase == Phase.DONE
    assert "Timeline" in result["response"] or "headache" in result["response"].lower()
