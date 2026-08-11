"""Templated terminal responses."""

from __future__ import annotations

import pytest

from reg_advisor.knowledge import DISCLAIMER, get_knowledge_base
from reg_advisor.terminals import greet_and_explain, redirect_to_scope, refer_to_expert

TERMINALS = [greet_and_explain, redirect_to_scope, refer_to_expert]


@pytest.mark.parametrize("terminal", TERMINALS, ids=lambda f: f.__name__)
def test_every_terminal_carries_the_disclaimer(terminal) -> None:
    """Appended in Python, so it cannot go missing on a turn the model is distracted."""
    assert terminal().endswith(DISCLAIMER)


def test_greeting_states_the_limits_and_the_verification_date() -> None:
    text = greet_and_explain()
    assert "legal advice" in text
    assert "compliant" in text
    assert get_knowledge_base().verified_on in text


def test_redirect_names_what_is_in_scope() -> None:
    text = redirect_to_scope()
    assert "EU and US" in text
    assert "medical devices" in text


def test_referral_names_the_real_routes() -> None:
    text = refer_to_expert()
    for route in ("notified body", "counsel", "Q-Submission", "competent authority"):
        assert route in text, route


def test_referral_names_what_it_will_not_do() -> None:
    text = refer_to_expert()
    assert "compliance determination" in text
    assert "clinical advice" in text
