"""Expectations: what a metric compares the trace with."""

import pytest
from pydantic import ValidationError

from rhesis.sdk.metrics import Expectations


def test_a_string_is_the_expected_response():
    assert Expectations.coerce("Paris") == Expectations(response="Paris")


def test_a_dict_sets_the_fields_it_names():
    expectations = Expectations.coerce({"goal": "Book a room", "instructions": "Be brief"})

    assert expectations == Expectations(goal="Book a room", instructions="Be brief")
    assert expectations.response is None


def test_none_stays_none():
    """Production traces have no expectations."""
    assert Expectations.coerce(None) is None


def test_expectations_pass_through_unchanged():
    expectations = Expectations(response="Paris", contract={"required_criteria": ["x"]})

    assert Expectations.coerce(expectations) is expectations


@pytest.mark.parametrize("value", [42, ["Paris"], object()])
def test_anything_else_is_refused(value):
    with pytest.raises(TypeError, match="Expectations, a string or a dict"):
        Expectations.coerce(value)


def test_expectations_cannot_be_changed_once_made():
    expectations = Expectations(response="Paris")

    with pytest.raises(ValidationError):
        expectations.response = "Rome"
