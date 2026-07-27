from visit_prep.safety import has_red_flag, text_suggests_red_flag
from visit_prep.state import Slots, VisitPrepState


def test_chest_pain_red_flag():
    assert text_suggests_red_flag("I have crushing chest pain")


def test_mild_headache_not_red_flag():
    assert not text_suggests_red_flag("I have a mild headache")


def test_has_red_flag_from_history():
    state = VisitPrepState(
        history=[
            {"role": "user", "content": "I've been fine"},
            {"role": "user", "content": "Now I can't breathe and have chest pain"},
        ]
    )
    assert has_red_flag(state)


def test_has_red_flag_from_slots():
    state = VisitPrepState(slots=Slots(associated="worst headache of my life"))
    assert has_red_flag(state)
