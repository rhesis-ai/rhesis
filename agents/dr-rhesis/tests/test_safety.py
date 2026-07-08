from dr_rhesis.safety import has_red_flag, text_suggests_red_flag
from dr_rhesis.state import Slots, DrRhesisState


def test_chest_pain_red_flag():
    assert text_suggests_red_flag("I have crushing chest pain")


def test_mild_headache_not_red_flag():
    assert not text_suggests_red_flag("I have a mild headache")


def test_has_red_flag_from_history():
    state = DrRhesisState(
        history=[
            {"role": "user", "content": "I've been fine"},
            {"role": "user", "content": "Now I can't breathe and have chest pain"},
        ]
    )
    assert has_red_flag(state)


def test_has_red_flag_from_slots():
    state = DrRhesisState(slots=Slots(associated="worst headache of my life"))
    assert has_red_flag(state)
