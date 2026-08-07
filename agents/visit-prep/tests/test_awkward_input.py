"""Awkward user text must survive the turn, including Jinja rendering of the prompts.

Slot values are rendered into the coordinator's and the specialist's system prompts via
``{{ slot_status }}``, so odd characters travel through a template on every turn.

"Text" is also not guaranteed to be a ``str``. The platform renders an endpoint's
``request_mapping`` and then tries ``json.loads`` on the result, so a user who answers a
severity question with ``9`` has their message delivered as an ``int``; a model can answer a
``"type": "string"`` tool parameter with a JSON number for the same reason.
"""

import pytest

from tests.mocks import gather_script, make_pipeline
from visit_prep.pipeline import run_turn
from visit_prep.state import Slots, VisitPrepState


def test_numeric_severity_message():
    msg = "9"
    result = run_turn(
        msg,
        VisitPrepState(chief_complaint="pain"),
        pipeline=make_pipeline(
            gather_script(msg, slot_args={"severity": "9"}, question="What makes it worse?")
        ),
    )
    assert result["response"]
    assert result["state"].slots.severity == "9"


@pytest.mark.parametrize("msg", [9, 2.5, True, None])
def test_non_string_message_is_coerced_to_text(msg):
    """A message that arrives as an int/float/bool/None must not reach the red-flag regexes.

    Regression: the platform's request mapping JSON-parses the rendered message, so typing
    "9" delivered ``9`` and the whole coordinator run died with "expected string or
    bytes-like object, got 'int'".
    """
    result = run_turn(
        msg,
        VisitPrepState(chief_complaint="pain"),
        pipeline=make_pipeline(
            gather_script(str(msg), slot_args={"severity": "9"}, question="What makes it worse?")
        ),
    )
    assert result["response"] == "What makes it worse?"
    assert result["state"].history[-2] == {
        "role": "user",
        "content": "" if msg is None else str(msg),
    }


def test_numeric_slot_value_from_the_model_is_recorded():
    """A JSON number for a "type": "string" slot is kept as text, not silently dropped."""
    msg = "9 out of 10"
    result = run_turn(
        msg,
        VisitPrepState(chief_complaint="pain"),
        pipeline=make_pipeline(
            gather_script(msg, slot_args={"severity": 9}, question="What makes it worse?")
        ),
    )
    assert result["state"].slots.severity == "9"


def test_numeric_message_stored_in_history_survives_the_next_turn():
    """Stale history written before this fix must not break the turn that replays it."""
    state = VisitPrepState(chief_complaint="pain")
    # Assigned rather than passed to the constructor: Pydantic rejects a non-string here, but
    # it does not validate on assignment — which is how such an entry got stored to begin with.
    state.history = [{"role": "user", "content": 9}, {"role": "assistant", "content": "How long?"}]
    msg = "since Monday"
    result = run_turn(
        msg,
        state,
        pipeline=make_pipeline(
            gather_script(msg, slot_args={"onset": "since Monday"}, question="Where is it?")
        ),
    )
    assert result["response"] == "Where is it?"


def test_apostrophe_in_message():
    msg = "I'm in pain"
    result = run_turn(
        msg,
        VisitPrepState(),
        pipeline=make_pipeline(
            gather_script(msg, slot_args={"chief_complaint": "pain"}, question="Where is the pain?")
        ),
    )
    assert "?" in result["response"]


def test_template_looking_slot_value_is_not_re_rendered():
    """A slot value containing Jinja syntax must be passed through, not evaluated."""
    state = VisitPrepState(
        chief_complaint="{{ oops }}",
        slots=Slots(onset="{% raw %} 2 days"),
    )
    msg = "it's on my temples"
    result = run_turn(
        msg,
        state,
        pipeline=make_pipeline(
            gather_script(msg, slot_args={"location": "temples"}, question="How severe is it?")
        ),
    )
    assert result["response"]
    assert result["state"].chief_complaint == "{{ oops }}"
