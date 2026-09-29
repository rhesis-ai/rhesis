"""Which judge details the local strategy keeps with a stored metric result."""

from rhesis.backend.metrics.strategies.local import _extract_extra_details


def test_keeps_cited_turns_and_the_criteria_breakdown():
    details = {
        "prompt": "rendered judge prompt",
        "relevant_turns": [2, 3],
        "criteria_evaluations": [{"criterion": "Escalate", "met": False}],
        "criteria_failed": 1,
    }

    assert _extract_extra_details(details) == {
        "relevant_turns": [2, 3],
        "criteria_evaluations": [{"criterion": "Escalate", "met": False}],
        "criteria_failed": 1,
    }


def test_returns_none_when_nothing_is_worth_keeping():
    assert _extract_extra_details({"prompt": "rendered judge prompt"}) is None
