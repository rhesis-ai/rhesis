"""Templated terminal responses."""

from visit_prep.terminals import escalate, greet_and_explain, redirect_to_scope


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
