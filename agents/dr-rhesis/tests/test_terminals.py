from dr_rhesis.state import Phase
from dr_rhesis.terminals import escalate, greet_and_explain, redirect_to_scope, terminal_reply


def test_greet():
    text = greet_and_explain()
    assert "visit" in text.lower()
    assert "diagnos" in text.lower()


def test_redirect():
    text = redirect_to_scope()
    assert "diagnos" in text.lower() or "prescrib" in text.lower()


def test_escalate():
    text = escalate()
    assert "emergency" in text.lower() or "911" in text


def test_emergency_terminal_sets_phase():
    from dr_rhesis.state import DrRhesisState

    reply, state = terminal_reply("emergency", DrRhesisState())
    assert state.phase == Phase.ESCALATED
    assert state.red_flag is True
    assert "emergency" in reply.lower() or "911" in reply
